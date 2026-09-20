"""Build every name in common_names.txt into a standalone cache database.

Run at image build time. At startup the app copies rows from this file into
the live database for any name or molecule not already cached, so first
visits are instant even on a slow CPU.

Usage: uv run python scripts/prewarm.py [-j 4] [--limit N] [--out backend/prewarm.db]
"""

import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _build(name: str):
    from app import chem
    from app.cache import _serialise, normalise

    try:
        resolved = chem.resolve_full(name)
        smiles = chem.canonical_smiles(resolved.smiles)
        data = _serialise(chem.build_from_smiles(smiles, input_text=name, source=resolved.source))
        return name, normalise(name), smiles, resolved, data
    except chem.ChemError as e:
        return name, None, None, None, str(e)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-j", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=str(ROOT / "prewarm.db"))
    args = ap.parse_args()

    os.environ["CHEM_DB_PATH"] = args.out
    if os.path.exists(args.out):
        os.unlink(args.out)
    import json

    from app.db import MoleculeCache, NameCache, SessionLocal, init_db
    from app.suggest import known_names

    init_db()
    names = known_names()
    if args.limit:
        names = names[: args.limit]
    t = time.time()
    ok = 0
    seen_smiles: set[str] = set()
    with ProcessPoolExecutor(args.j) as pool, SessionLocal() as db:
        for name, key, smiles, resolved, data in pool.map(_build, names, chunksize=4):
            if key is None:
                print(f"skip {name}: {data}", file=sys.stderr)
                continue
            db.merge(NameCache(key=key, smiles=smiles, source=resolved.source, warning=" ".join(resolved.warnings), normalised=resolved.normalised))
            if smiles not in seen_smiles:
                seen_smiles.add(smiles)
                db.add(MoleculeCache(smiles=smiles, result_json=json.dumps(data), inchikey=data["inchikey"]))
            ok += 1
        db.commit()
    print(f"prewarmed {ok}/{len(names)} names into {args.out} in {time.time() - t:.0f}s")


if __name__ == "__main__":
    main()
