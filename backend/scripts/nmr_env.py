"""Build app/data/nmr_env.db, the local 1H/13C shift index, from nmrshiftdb2's assigned spectra.

Input is nmrshiftdb2withsignals.sd from https://sourceforge.net/projects/nmrshiftdb2/files/data/
(nmrshiftdb2 Database License, an ODbL derivative: the index is shared under the same licence).
Every spectrum lists `shift;intensity;atom` entries with 0-based atom numbers; 1H entries name
the atom the hydrogen sits on. Spectra a program predicted (listed in the record's Program field)
are left out, so only measured shifts go in. Shifts of the same atom in several spectra of a molecule are
averaged first, so each molecule counts once per atom. For every carbon (13C) and every atom
carrying hydrogens (1H) the environment ids at radius 1 to 4 (app.nmr_env.environments) collect
the shift; the index keeps the median, a robust spread and the count per environment. It also keeps
each compound's own measured shifts (one record per InChIKey), shown instead of a prediction when
the built molecule is in nmrshiftdb2.

With --holdout N, molecules whose InChIKey hashes to 0 mod N are left out of the index and
written to a test file instead, for scripts/eval_spectra.py:

    uv run python scripts/nmr_env.py build path/to/nmrshiftdb2withsignals.sd                  # the shipped index
    uv run python scripts/nmr_env.py build path/to/nmrshiftdb2withsignals.sd --holdout 10 \\
        --out /tmp/nmr_env_train.db --test docs/benchmark/nmr_test.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import statistics
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rdkit import Chem, RDLogger  # noqa: E402

from app.nmr_env import RADII, environments  # noqa: E402

RDLogger.DisableLog("rdApp.*")
MAX_HEAVY = 80


def _peaks(text: str) -> list[tuple[float, int]]:
    out = []
    for part in text.strip().strip("|").split("|"):
        bits = part.split(";")
        if len(bits) >= 3:
            try:
                out.append((float(bits[0]), int(bits[2])))
            except ValueError:
                continue
    return out


_PREDICTORS = re.compile(r"HOSE|ACD/Labs|CSEARCH|predict", re.I)


def _predicted(text: str) -> set[str]:
    """Spectrum numbers a prediction program made: '6:ACD/Labs C+H NMR Predictors 7:HOSE code using nmrshiftdb2 data'
    -> {'6', '7'}. Some records carry predicted spectra next to the measured ones; they are left out."""
    parts = re.split(r"(?:^|\s)(\d+):", text)
    return {parts[i] for i in range(1, len(parts) - 1, 2) if _PREDICTORS.search(parts[i + 1])}


def _solvent(text: str) -> str:
    """'0:Chloroform-D1 (CDCl3)' -> 'CDCl3'; the first spectrum's solvent when there are several."""
    first = text.split("1:")[0].split(":", 1)[-1].strip()
    m = re.search(r"\(([^()]+)\)\s*$", first)
    return (m.group(1) if m else first)[:40]


def _smiles_order(hmol) -> tuple[str, dict[int, int]]:
    smiles = Chem.MolToSmiles(hmol)
    order = list(map(int, hmol.GetProp("_smilesAtomOutputOrder").strip("[]").split(",")))
    return smiles, {old: new for new, old in enumerate(order)}


def _held_out(key: str, every: int) -> bool:
    return every > 0 and int(hashlib.md5(key.encode()).hexdigest(), 16) % every == 0


def records(sd_path: str):
    """(heavy-atom mol, {atom: 13C shift}, {atom: 1H shift}, InChIKey) per usable molecule."""
    for mol in Chem.SDMolSupplier(sd_path, removeHs=False, sanitize=True):
        if mol is None:
            continue
        props = mol.GetPropsAsDict()
        c_lists: dict[int, list[float]] = defaultdict(list)
        h_lists: dict[int, list[float]] = defaultdict(list)
        # Heavy-atom numbering: RemoveAllHs keeps the other atoms in order.
        heavy = [a.GetIdx() for a in mol.GetAtoms() if a.GetAtomicNum() != 1]
        new_index = {old: new for new, old in enumerate(heavy)}
        predicted = _predicted(str(props.get("Program", "")))
        for name, value in props.items():
            if not name.startswith("Spectrum "):
                continue
            _, nucleus, number = (name.split() + ["", ""])[:3]
            if nucleus not in ("13C", "1H") or number in predicted:
                continue
            per_atom: dict[int, list[float]] = defaultdict(list)
            for shift, atom in _peaks(str(value)):
                if atom >= mol.GetNumAtoms():
                    continue
                a = mol.GetAtomWithIdx(atom)
                if a.GetAtomicNum() == 1:  # an explicit hydrogen: use the atom it sits on
                    nbrs = a.GetNeighbors()
                    if not nbrs:
                        continue
                    a = nbrs[0]
                if a.GetIdx() not in new_index:
                    continue
                if nucleus == "13C" and a.GetAtomicNum() != 6:
                    continue
                per_atom[new_index[a.GetIdx()]].append(shift)
            for atom, shifts in per_atom.items():
                (c_lists if nucleus == "13C" else h_lists)[atom].append(statistics.fmean(shifts))
        if not c_lists and not h_lists:
            continue
        try:
            hmol = Chem.RemoveAllHs(mol)
        except Exception:  # noqa: BLE001 - a record RDKit cannot clean is skipped
            continue
        if hmol.GetNumAtoms() != len(heavy) or hmol.GetNumAtoms() > MAX_HEAVY:
            continue
        key = props.get("INChI key") or Chem.MolToInchiKey(hmol)
        info = {"id": str(props.get("nmrshiftdb2 ID", "")).strip(), "solvent": _solvent(str(props.get("Solvent", "")))}
        yield (hmol, {a: statistics.fmean(v) for a, v in c_lists.items()},
               {a: statistics.fmean(v) for a, v in h_lists.items()}, str(key).strip(), info)


def _spread(values: list[float], median: float) -> float:
    if len(values) >= 3:
        return 1.4826 * statistics.median(abs(v - median) for v in values)
    if len(values) == 2:
        return abs(values[0] - values[1]) / 2
    return 0.0


def build(sd_path: str, out: str, holdout: int, test_path: str | None) -> None:
    shifts: dict[tuple[str, int, int], list[float]] = defaultdict(list)
    n_train = n_test = 0
    test = open(test_path, "w", encoding="utf-8") if test_path else None
    measured: dict[str, tuple] = {}
    for hmol, c, h, key, info in records(sd_path):
        if _held_out(key, holdout):
            if test is not None:
                smiles, to_smiles = _smiles_order(hmol)
                test.write(json.dumps({"key": key, "smiles": smiles,
                                       "c": {to_smiles[a]: round(s, 2) for a, s in c.items()},
                                       "h": {to_smiles[a]: round(s, 2) for a, s in h.items()}}) + "\n")
            n_test += 1
            continue
        n_train += 1
        # The measured shifts of the compound itself: the record with the most assigned atoms, CDCl3 on a tie.
        rank = (len(c) + len(h), info["solvent"] == "CDCl3")
        if key not in measured or rank > measured[key][0]:
            smiles, to_smiles = _smiles_order(hmol)
            measured[key] = (rank, smiles, {to_smiles[a]: round(v, 1) for a, v in c.items()},
                             {to_smiles[a]: round(v, 2) for a, v in h.items()}, info["solvent"], info["id"])
        envs = environments(hmol)
        for nucleus, values in (("C", c), ("H", h)):
            for atom, shift in values.items():
                for r in RADII:
                    if r in envs[atom]:
                        shifts[(nucleus, r, envs[atom][r])].append(shift)
    if test is not None:
        test.close()
    tmp = out + ".tmp"
    if os.path.exists(tmp):
        os.unlink(tmp)
    con = sqlite3.connect(tmp)
    con.executescript("""
        CREATE TABLE env (nucleus TEXT, radius INTEGER, id INTEGER, n INTEGER, median REAL, spread REAL,
                          PRIMARY KEY (nucleus, radius, id)) WITHOUT ROWID;
        CREATE TABLE measured (inchikey TEXT PRIMARY KEY, smiles TEXT, c TEXT, h TEXT, solvent TEXT, record TEXT) WITHOUT ROWID;
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
    """)
    con.executemany("INSERT INTO measured VALUES (?,?,?,?,?,?)",
                    [(key, smiles, json.dumps(c, separators=(",", ":")), json.dumps(h, separators=(",", ":")), solvent, record)
                     for key, (_, smiles, c, h, solvent, record) in measured.items()])
    rows = []
    for (nucleus, r, env_id), values in shifts.items():
        median = statistics.median(values)
        digits = 1 if nucleus == "C" else 2
        rows.append((nucleus, r, env_id, len(values), round(median, digits), round(_spread(values, median), digits)))
    con.executemany("INSERT INTO env VALUES (?,?,?,?,?,?)", rows)
    con.executemany("INSERT INTO meta VALUES (?,?)", [("built", date.today().isoformat()), ("molecules", str(n_train)),
                                                      ("held_out", str(n_test)), ("environments", str(len(rows))), ("measured", str(len(measured))),
                                                      ("source", "nmrshiftdb2withsignals.sd")])
    con.commit()
    con.execute("VACUUM")
    con.close()
    os.replace(tmp, out)
    print(f"{out}: {n_train} molecules, {len(rows)} environments; {n_test} held out", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["build"])
    ap.add_argument("sd")
    ap.add_argument("--out", default=str(ROOT / "app" / "data" / "nmr_env.db"))
    ap.add_argument("--holdout", type=int, default=0, help="leave out every Nth molecule (by InChIKey hash)")
    ap.add_argument("--test", help="write the held-out molecules here (JSON lines)")
    args = ap.parse_args()
    build(args.sd, args.out, args.holdout, args.test)


if __name__ == "__main__":
    main()
