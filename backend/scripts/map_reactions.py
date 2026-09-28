"""Atom-map the reaction sources that come without atom maps (Rhea, CRD).

The index builder needs atom maps to tell which molecules end up in the
product. Lowe's USPTO files are mapped already; these two are not, so this
script maps them once with RXNMapper (Schwaller et al., Sci. Adv. 2021, MIT)
and writes a tab-separated file the builder reads:

    mapped reaction SMILES (reactants>agents>products)  ref  year  yield  extra  confidence

Sources
- rhea: rhea-reaction-smiles.tsv, rhea-directions.tsv and rhea2ec.tsv from
  https://ftp.expasy.org/databases/rhea/tsv/ (CC BY 4.0). Only the
  left-to-right reaction of each entry, and none with generic R groups (*).
  ref is RHEA:<id>, extra is the EC number(s).
- crd: reactionSmilesFigShare2025.txt from the Chemical Reaction Database,
  van der Lingen, https://doi.org/10.5281/zenodo.18109268 (CC BY 4.0).
  Lines are reactants>agents>products; only reactants>>products is mapped and
  the agents are put back. ref is the line number in that file.

The output is appended to and the script skips inputs already written, so a
stopped run resumes where it left off. RXNMapper and torch are not project
dependencies; run it in a throwaway environment:

  uv run --isolated --no-project --python 3.12 --with rxnmapper --with "transformers>=4.40,<4.50" \\
      --with rdkit --with "setuptools<81" python scripts/map_reactions.py rhea DIR OUT.tsv
  ... python scripts/map_reactions.py crd reactionSmilesFigShare2025.txt OUT.tsv
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")

BATCH = 64
MAX_LEN = 1000  # characters; RXNMapper reads at most 512 tokens and fails on longer ones, which are skipped


def _canonical_side(side: str) -> str | None:
    out = []
    for s in side.split("."):
        if not s:
            continue
        m = Chem.MolFromSmiles(s)
        if m is None:
            return None
        out.append(Chem.MolToSmiles(m))  # also drops explicit [H] atoms
    return ".".join(out)


def rhea_inputs(folder: Path):
    """(reactants>>products, ref, year, yield, extra) for each left-to-right Rhea reaction."""
    with open(folder / "rhea-directions.tsv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    lr_to_master = {r["RHEA_ID_LR"]: r["RHEA_ID_MASTER"] for r in rows}
    ec: dict[str, list[str]] = {}
    ec_file = folder / "rhea2ec.tsv"
    if ec_file.exists():
        with open(ec_file, encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                ec.setdefault(r["MASTER_ID"], []).append(r["ID"])
    with open(folder / "rhea-reaction-smiles.tsv", encoding="utf-8") as f:
        for line in f:
            rid, _, smiles = line.rstrip("\n").partition("\t")
            if rid not in lr_to_master or "*" in smiles:
                continue
            left, _, right = smiles.partition(">>")
            left, right = _canonical_side(left), _canonical_side(right)
            if not left or not right:
                continue
            yield f"{left}>>{right}", "", f"RHEA:{rid}", "", "", " ".join(ec.get(lr_to_master[rid], []))


def crd_inputs(path: Path):
    with open(path, encoding="utf-8", errors="replace") as f:
        for n, line in enumerate(f, 1):
            parts = line.strip().split(">")
            if len(parts) != 3:
                continue
            left, right = _canonical_side(parts[0]), _canonical_side(parts[2])
            agents = _canonical_side(parts[1]) or ""
            if not left or not right:
                continue
            yield f"{left}>>{right}", agents, str(n), "", "", ""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", choices=["rhea", "crd"])
    ap.add_argument("input", type=Path, help="Rhea tsv folder, or the CRD text file")
    ap.add_argument("out", type=Path)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    import torch
    from rxnmapper import RXNMapper

    done: set[str] = set()
    if args.out.exists():
        with open(args.out, encoding="utf-8") as f:
            done = {line.split("\t")[1] for line in f if "\t" in line}
    inputs = rhea_inputs(args.input) if args.source == "rhea" else crd_inputs(args.input)
    mapper = RXNMapper()
    if torch.backends.mps.is_available():  # Apple GPU, several times faster than the CPU
        mapper.device = torch.device("mps")
        mapper.model.to(mapper.device)
    t0, n_done, n_skip = time.time(), 0, 0
    batch: list[tuple] = []

    def flush(out) -> None:
        nonlocal n_done, n_skip
        if not batch:
            return
        try:
            results = mapper.get_attention_guided_atom_maps([b[0] for b in batch], canonicalize_rxns=False)
        except Exception:  # noqa: BLE001 - one bad reaction fails the batch; retry one by one
            results = []
            for b in batch:
                try:
                    results += mapper.get_attention_guided_atom_maps([b[0]], canonicalize_rxns=False)
                except Exception:  # noqa: BLE001
                    results.append(None)
        for (rxn, agents, ref, year, yld, extra), res in zip(batch, results):
            if res is None:
                n_skip += 1
                out.write(f"\t{ref}\t\t\t\t\n")  # remembered as done
                continue
            left, _, right = res["mapped_rxn"].partition(">>")
            out.write(f"{left}>{agents}>{right}\t{ref}\t{year}\t{yld}\t{extra}\t{res['confidence']:.3f}\n")
            n_done += 1
        batch.clear()

    with open(args.out, "a", encoding="utf-8") as out:
        for i, item in enumerate(inputs):
            if args.limit and i >= args.limit:
                break
            if item[2] in done:
                continue
            if len(item[0]) > MAX_LEN:
                n_skip += 1
                out.write(f"\t{item[2]}\t\t\t\t\n")
                continue
            batch.append(item)
            if len(batch) >= BATCH:
                flush(out)
                if (n_done + n_skip) % (BATCH * 50) < BATCH:
                    out.flush()
                    rate = n_done / max(time.time() - t0, 1e-9)
                    print(f"  {n_done} mapped, {n_skip} skipped, {rate:.0f}/s", flush=True)
        flush(out)
    print(f"{n_done} mapped, {n_skip} skipped in {time.time() - t0:.0f} s -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
