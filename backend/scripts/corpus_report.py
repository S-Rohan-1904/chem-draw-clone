"""Run every corpus name through the pipeline and print a per-name verdict.

Usage: PATH=/opt/homebrew/opt/openjdk/bin:$PATH uv run python scripts/corpus_report.py [-j 8] [--only CATEGORY]
"""

import argparse
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rdkit import Chem  # noqa: E402

from app.chem import ChemError, _cip_labels, build, resolve  # noqa: E402
from tests.corpus import CORPUS  # noqa: E402


def check(entry):
    name, n_centers, n_bonds, category = entry
    t = time.time()
    try:
        r = build(name)
    except ChemError as e:
        kind = "OPSIN_FAIL" if "Could not interpret" in str(e) else "EMBED_FAIL"
        return name, category, kind, str(e)[:160], time.time() - t
    problems = []
    if r.stereo.unspecified:
        problems.append(f"UNSPECIFIED {[(c.atom_idx, c.label) for c in r.stereo.centers]} {[b.label for b in r.stereo.double_bonds]}")
    if n_centers is not None and len(r.stereo.centers) != n_centers:
        problems.append(f"CENTERS want {n_centers} got {[(c.atom_idx, c.label) for c in r.stereo.centers]}")
    if n_bonds is not None and len(r.stereo.double_bonds) != n_bonds:
        problems.append(f"BONDS want {n_bonds} got {[(b.atoms, b.label) for b in r.stereo.double_bonds]}")
    mol3d = Chem.MolFromMolBlock(r.molblock, removeHs=False)
    Chem.AssignStereochemistryFrom3D(mol3d, replaceExistingTags=True)
    got = _cip_labels(mol3d)
    expected = _cip_labels(Chem.MolFromSmiles(resolve(name)[0]))
    if not all(got.get(k) == v for k, v in expected.items()):
        problems.append(f"3D_MISMATCH {got} != {expected}")
    return name, category, "OK" if not problems else "FAIL", "; ".join(problems) + f" smiles={r.smiles}", time.time() - t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-j", type=int, default=8)
    ap.add_argument("--only")
    ap.add_argument("--all", action="store_true", help="print OK rows too")
    args = ap.parse_args()
    entries = [e for e in CORPUS if "skip" not in e[3] and (not args.only or e[3] == args.only)]
    counts: dict[str, int] = {}
    with ProcessPoolExecutor(args.j) as pool:
        for name, cat, kind, detail, dt in pool.map(check, entries):
            counts[kind] = counts.get(kind, 0) + 1
            if kind != "OK" or args.all:
                print(f"[{kind}] {cat} | {name} | {detail} ({dt:.1f}s)")
    print("\n" + " ".join(f"{k}={v}" for k, v in sorted(counts.items())), f"total={len(entries)}")


if __name__ == "__main__":
    main()
