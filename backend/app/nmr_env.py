"""1H and 13C shifts predicted locally from assigned spectra in nmrshiftdb2.

Each atom is described by its surroundings at radius 1 to 4 bonds (circular
atom environments, RDKit's Morgan invariants: element, neighbours, hydrogens,
charge, ring membership and bond orders). The same idea as HOSE codes: the
index (app/data/nmr_env.db, built by scripts/nmr_env.py from nmrshiftdb2's
assigned spectra) holds, for every environment seen, the median shift, the
spread and the number of atoms it comes from. A prediction uses the widest
environment that matches, so a common group is predicted from exact look-alikes
and a rare one from its nearer surroundings. Hydrogens are
predicted from the environment of the atom they sit on.

The index is a derivative of the nmrshiftdb2 database and is distributed under
the nmrshiftdb2 Database License (see THIRD_PARTY_NOTICES.md). Never raises.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path

from rdkit import Chem
from rdkit.Chem import rdFingerprintGenerator

DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "nmr_env.db"
RADII = (4, 3, 2, 1)
# The error bar is never smaller than the typical error at the radius that matched: the 68th percentile of
# |predicted - measured| over 4,355 molecules held out of the index (docs/spectra-benchmark.md).
TYPICAL_ERROR = {"C": {4: 0.7, 3: 1.6, 2: 3.2, 1: 8.0}, "H": {4: 0.1, 3: 0.2, 2: 0.33, 1: 0.75}}
_GEN = rdFingerprintGenerator.GetMorganGenerator(radius=max(RADII), includeRedundantEnvironments=True)
_LOCAL = threading.local()


def db_path() -> Path:
    return Path(os.environ.get("CHEM_NMR_ENV_DB", str(DEFAULT_PATH)))


def _signed(x: int) -> int:
    """SQLite integers are signed 64-bit; Morgan ids are unsigned."""
    return x - (1 << 64) if x >= (1 << 63) else x


def environments(mol: Chem.Mol) -> list[dict[int, int]]:
    """Per heavy atom of `mol` (no explicit hydrogens): {radius: environment id}."""
    ao = rdFingerprintGenerator.AdditionalOutput()
    ao.AllocateBitInfoMap()
    _GEN.GetSparseCountFingerprint(mol, additionalOutput=ao)
    out: list[dict[int, int]] = [{} for _ in range(mol.GetNumAtoms())]
    for env_id, hits in ao.GetBitInfoMap().items():
        for atom, radius in hits:
            out[atom][radius] = _signed(env_id)
    return out


def _connection() -> sqlite3.Connection | None:
    path = db_path()
    con = getattr(_LOCAL, "con", None)
    if con is not None and getattr(_LOCAL, "path", None) == path:
        return con
    if not path.exists():
        return None
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    except sqlite3.Error:
        return None
    _LOCAL.con, _LOCAL.path = con, path
    return con


def available() -> bool:
    return _connection() is not None


def predict(mol: Chem.Mol) -> dict[str, list[dict | None]]:
    """{"C": [...], "H": [...]} per heavy atom of `mol`: for carbons (C) and for the hydrogens
    on each atom (H), {shift, spread, n, radius}, or None when no environment matches.
    Empty lists when the index is not installed."""
    con = _connection()
    if con is None:
        return {"C": [], "H": []}
    envs = environments(mol)
    wanted = {"C": [a.GetIdx() for a in mol.GetAtoms() if a.GetAtomicNum() == 6],
              "H": [a.GetIdx() for a in mol.GetAtoms() if a.GetTotalNumHs() > 0]}
    keys = {(nuc, r, envs[i][r]) for nuc, atoms in wanted.items() for i in atoms for r in RADII if r in envs[i]}
    rows: dict[tuple[str, int, int], tuple[int, float, float]] = {}
    try:
        for nuc in ("C", "H"):
            for r in RADII:
                ids = [k[2] for k in keys if k[0] == nuc and k[1] == r]
                for start in range(0, len(ids), 500):
                    chunk = ids[start:start + 500]
                    q = f"SELECT id, n, median, spread FROM env WHERE nucleus = ? AND radius = ? AND id IN ({','.join('?' * len(chunk))})"
                    for env_id, n, median, spread in con.execute(q, (nuc, r, *chunk)):
                        rows[(nuc, r, env_id)] = (n, median, spread)
    except sqlite3.Error:
        return {"C": [], "H": []}
    out: dict[str, list[dict | None]] = {"C": [None] * mol.GetNumAtoms(), "H": [None] * mol.GetNumAtoms()}
    for nuc, atoms in wanted.items():
        for i in atoms:
            # The widest matching environment wins, even from one example: on held-out molecules this beats
            # waiting for more examples at a narrower radius (13C 2.5 vs 3.0 ppm mean error).
            r = next((r for r in RADII if r in envs[i] and (nuc, r, envs[i][r]) in rows), None)
            if r is not None:
                n, median, spread = rows[(nuc, r, envs[i][r])]
                out[nuc][i] = {"shift": median, "spread": max(spread, TYPICAL_ERROR[nuc][r]), "n": n, "radius": r}
    return out


def measured(mol: Chem.Mol) -> dict | None:
    """The compound's own assigned shifts when nmrshiftdb2 has it: {"C": [...], "H": [...], "solvent", "record"},
    per heavy atom of `mol` (None where the record assigns nothing), or None."""
    con = _connection()
    if con is None:
        return None
    try:
        key = Chem.MolToInchiKey(mol)
        row = con.execute("SELECT smiles, c, h, solvent, record FROM measured WHERE inchikey = ?", (key,)).fetchone() if key else None
    except (sqlite3.Error, ValueError):
        return None
    if row is None:
        return None
    smiles, c, h, solvent, record = row
    stored = Chem.MolFromSmiles(smiles)
    match = mol.GetSubstructMatch(stored) if stored is not None else ()
    if not match or len(match) != mol.GetNumAtoms():
        return None
    out: dict = {"C": [None] * mol.GetNumAtoms(), "H": [None] * mol.GetNumAtoms(), "solvent": solvent, "record": record}
    for nuc, values in (("C", json.loads(c)), ("H", json.loads(h))):
        for atom, shift in values.items():
            out[nuc][match[int(atom)]] = shift
    return out
