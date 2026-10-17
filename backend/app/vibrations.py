"""Calculated IR spectrum and normal modes from GFN2-xTB.

The structure is embedded with RDKit (ETKDG, then MMFF), optimised with the
semiempirical GFN2-xTB method and its Hessian computed (`xtb --ohess tight`).
xtb writes every normal mode's harmonic frequency, IR intensity and atomic
displacements (g98.out), which the card draws as a spectrum and animates in 3D.
Frequencies are scaled by SCALE, the median of experiment/calculation over the
strong bands of ten small molecules (C=O, C#N, O-H, N-H, C-H stretches); GFN2
bands are typically within about 50 cm-1, nitriles high by about 5 %.

xtb (LGPL-3.0, Grimme group) is a separate program: CHEM_XTB points at it,
else `xtb` on PATH or /opt/xtb/bin/xtb (the Docker image). Without it the card
keeps the band table and NIST's spectrum. Never raises.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from rdkit import Chem
from rdkit.Chem import AllChem

SCALE = 0.985
MAX_ATOMS = 80  # with hydrogens; the Hessian grows quickly beyond this
MIN_FREQ = 50.0  # cm-1: lower modes are rotations and floppy torsions left over from the optimisation
TIMEOUT = float(os.environ.get("CHEM_XTB_TIMEOUT", "90"))
# The server has two cores: one calculation at a time, the next waits its turn.
_SLOT = threading.BoundedSemaphore(int(os.environ.get("CHEM_XTB_JOBS", "1")))


def xtb_path() -> str | None:
    for candidate in (os.environ.get("CHEM_XTB"), shutil.which("xtb"), "/opt/xtb/bin/xtb"):
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def parse_g98(text: str) -> list[dict]:
    """[{freq, intensity, disp: [[dx, dy, dz] per atom]}] from xtb's Gaussian-style g98.out."""
    modes: list[dict] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("Frequencies --"):
            freqs = [float(x) for x in line.split("--")[1].split()]
            block = [{"freq": f, "intensity": 0.0, "disp": []} for f in freqs]
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("Atom"):
                if lines[j].strip().startswith("IR Inten"):
                    for m, v in zip(block, lines[j].split("--")[1].split()):
                        m["intensity"] = float(v)
                j += 1
            j += 1
            while j < len(lines):
                parts = lines[j].split()
                if len(parts) < 2 + 3 * len(block) or not parts[0].isdigit():
                    break
                vals = [float(x) for x in parts[2:2 + 3 * len(block)]]
                for k, m in enumerate(block):
                    m["disp"].append(vals[3 * k:3 * k + 3])
                j += 1
            modes += block
            i = j
            continue
        i += 1
    return modes


def _xyz(mol: Chem.Mol) -> Chem.Mol | None:
    mh = Chem.AddHs(mol)
    ps = AllChem.ETKDGv3()
    ps.randomSeed = 7
    if AllChem.EmbedMolecule(mh, ps) != 0:
        return None
    if AllChem.MMFFHasAllMoleculeParams(mh):
        AllChem.MMFFOptimizeMolecule(mh, maxIters=500)
    return mh


def _moving(mh: Chem.Mol, disp: list[list[float]]) -> list[int]:
    """Heavy atoms that move most in a mode (a hydrogen counts for the atom it sits on)."""
    amp = [sum(c * c for c in d) for d in disp]
    top = max(amp) or 1.0
    out = set()
    for idx, a in enumerate(amp):
        if a >= 0.25 * top:
            atom = mh.GetAtomWithIdx(idx)
            out.add(atom.GetNeighbors()[0].GetIdx() if atom.GetAtomicNum() == 1 and atom.GetDegree() else idx)
    return sorted(i for i in out if i < mh.GetNumHeavyAtoms())


def calculate(mol: Chem.Mol) -> tuple[dict | None, bool]:
    """(payload or None, complete). None with complete=True when xtb is not installed or the molecule is too
    big; complete=False when the calculation failed or the server was busy, so the result is not cached."""
    exe = xtb_path()
    if exe is None:
        return None, True
    mh = _xyz(mol)
    if mh is None or mh.GetNumAtoms() > MAX_ATOMS:
        return None, True
    if not _SLOT.acquire(timeout=TIMEOUT):
        return None, False
    try:
        charge = Chem.GetFormalCharge(mh)
        unpaired = sum(a.GetNumRadicalElectrons() for a in mh.GetAtoms())
        with tempfile.TemporaryDirectory(prefix="xtb-") as d:
            Path(d, "mol.xyz").write_text(Chem.MolToXYZBlock(mh))
            t = time.time()
            env = {**os.environ, "OMP_NUM_THREADS": "1", "OMP_STACKSIZE": "500M"}
            try:
                subprocess.run([exe, "mol.xyz", "--ohess", "tight", "--gfn", "2", "--chrg", str(charge), "--uhf", str(unpaired)],
                               cwd=d, capture_output=True, timeout=TIMEOUT, env=env, check=False)
            except (subprocess.TimeoutExpired, OSError):
                return None, False
            g98 = Path(d, "g98.out")
            opt = Path(d, "xtbopt.xyz")
            if not g98.exists() or not opt.exists():
                return None, False
            modes = parse_g98(g98.read_text())
            coords = [ln.split() for ln in opt.read_text().splitlines()[2:2 + mh.GetNumAtoms()]]
            seconds = time.time() - t
    finally:
        _SLOT.release()
    if len(coords) != mh.GetNumAtoms() or not modes:
        return None, False
    kept = [m for m in modes if m["freq"] >= MIN_FREQ and len(m["disp"]) == mh.GetNumAtoms()]
    return {
        "method": "GFN2-xTB",
        "scale": SCALE,
        "seconds": round(seconds, 1),
        "atoms": [{"el": c[0], "x": round(float(c[1]), 4), "y": round(float(c[2]), 4), "z": round(float(c[3]), 4)} for c in coords],
        "modes": [{"freq": round(m["freq"] * SCALE, 1), "intensity": round(m["intensity"], 2), "atoms": _moving(mh, m["disp"]),
                   "disp": [[round(v, 2) for v in d] for d in m["disp"]]} for m in kept],
    }, True

