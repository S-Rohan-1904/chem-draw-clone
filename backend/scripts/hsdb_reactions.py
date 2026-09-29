"""Routes to compounds from PubChem's "Methods of Manufacturing" (HSDB) text.

The Hazardous Substances Data Bank (U.S. National Library of Medicine, shown
in PubChem) describes how about 5,000 simple and industrial chemicals are made,
citing Ullmann's, Kirk-Othmer and the like. Every method is about making the
record's compound, and the compounds it names carry PubChem CIDs. As for the
Wikipedia sentences (wiki_reactions.py), a sentence becomes a reaction only
when some of the compounds it names, with small whole-number amounts, give the
compound plus at most two simple side products, atom for atom.

  uv run python scripts/hsdb_reactions.py fetch DIR     # the annotations, and SMILES of every CID in them
  uv run python scripts/hsdb_reactions.py extract DIR   # DIR/hsdb_reactions.tsv

The tsv has one reaction per line: reactants>>products, the compound's CID, the
reference the method cites, the sentence, and the compound's SMILES. Atom-map it with map_reactions.py
(source hsdb) before building the index.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wiki_reactions as wiki  # noqa: E402

UA = {"User-Agent": "ChemIllustrator/1.0 (https://github.com/S-Rohan-1904/chem-draw-clone; reaction index builder)"}
ANNOTATIONS = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/annotations/heading/JSON"
PROPERTIES = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/property/SMILES/JSON"
# Elements named in the text ("oxidized with chlorine") as they react: the gases as molecules.
ELEMENTS = {"Hydrogen": "[H][H]", "Nitrogen": "N#N", "Oxygen": "O=O", "Fluorine": "FF", "Chlorine": "ClCl",
            "Bromine": "BrBr", "Iodine": "II"}


def fetch(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(timeout=120, headers=UA)
    pages = out / "hsdb_annotations.json"
    if not pages.exists():
        records, page, total = [], 1, 1
        while page <= total:
            r = client.get(ANNOTATIONS, params={"heading": "Methods of Manufacturing", "heading_type": "Compound", "page": page})
            r.raise_for_status()
            a = r.json()["Annotations"]
            total = a.get("TotalPages", 1)
            records += [x for x in a["Annotation"] if "Hazardous Substances" in x.get("SourceName", "")]
            print(f"  page {page} of {total}", flush=True)
            page += 1
            time.sleep(0.5)
        pages.write_text(json.dumps(records), encoding="utf-8")
    records = json.loads(pages.read_text(encoding="utf-8"))
    cids = set()
    for rec in records:
        cids.update(rec.get("LinkedRecords", {}).get("CID", []))
        for d in rec.get("Data", []):
            for part in d.get("Value", {}).get("StringWithMarkup", []):
                for m in part.get("Markup", []):
                    if str(m.get("Extra", "")).startswith("CID-"):
                        cids.add(int(m["Extra"][4:]))
    smiles_file = out / "hsdb_smiles.json"
    smiles = json.loads(smiles_file.read_text()) if smiles_file.exists() else {}
    todo = sorted(c for c in cids if str(c) not in smiles)
    for i in range(0, len(todo), 300):
        r = client.post(PROPERTIES, data={"cid": ",".join(map(str, todo[i:i + 300]))})
        r.raise_for_status()
        for p in r.json()["PropertyTable"]["Properties"]:
            smiles[str(p["CID"])] = p.get("SMILES") or p.get("IsomericSMILES") or ""
        time.sleep(0.3)
    smiles_file.write_text(json.dumps(smiles), encoding="utf-8")
    print(f"{len(records)} compounds, {len(smiles)} structures")


def extract(folder: Path) -> None:
    records = json.loads((folder / "hsdb_annotations.json").read_text(encoding="utf-8"))
    smiles = json.loads((folder / "hsdb_smiles.json").read_text(encoding="utf-8"))
    st = wiki.Structures()
    side = wiki._side_combos(st)
    rows, seen, report = [], set(), Counter()
    for rec in records:
        linked = rec.get("LinkedRecords", {}).get("CID", [])
        if len(linked) != 1 or not smiles.get(str(linked[0])):
            continue  # a record for a mixture or several compounds
        cid, own = linked[0], smiles[str(linked[0])]
        for d in rec.get("Data", []):
            ref = "; ".join(d.get("Reference", []))[:200].replace("\t", " ")
            for part in d.get("Value", {}).get("StringWithMarkup", []):
                text = part.get("String", "")
                marks = part.get("Markup", [])
                for m in re.finditer(r"[^.;]+(?:[.;]|$)", text):
                    sent = m.group(0).strip()
                    if not sent or wiki.NEGATION.search(sent):
                        continue
                    named = []
                    for mk in marks:
                        start = mk.get("Start", -1)
                        if not (m.start() <= start < m.end()):
                            continue
                        extra = str(mk.get("Extra", ""))
                        if extra.startswith("CID-") and smiles.get(extra[4:]):
                            named.append(smiles[extra[4:]])
                        elif extra.startswith("Element-") and extra[8:] in ELEMENTS:
                            named.append(ELEMENTS[extra[8:]])
                    if not named:
                        continue
                    report["sentences with compounds"] += 1
                    for rxn in wiki.balance(own, named, sent, st, side):
                        if re.search(r"\[\d", rxn):
                            continue  # isotopes (plutonium-240): nuclear, not chemistry
                        if rxn in seen:
                            report["duplicate"] += 1
                            continue
                        seen.add(rxn)
                        report["kept"] += 1
                        rows.append((rxn, str(cid), ref, sent[:400], own))
    with open(folder / "hsdb_reactions.tsv", "w", encoding="utf-8") as f:
        for r in rows:
            f.write("\t".join(x.replace("\t", " ").replace("\n", " ") for x in r) + "\n")
    for k, v in report.most_common():
        print(f"  {k}: {v}")
    print(f"{len(rows)} reactions -> {folder / 'hsdb_reactions.tsv'}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["fetch", "extract"])
    ap.add_argument("dir", type=Path)
    args = ap.parse_args()
    (fetch if args.step == "fetch" else extract)(args.dir)


if __name__ == "__main__":
    sys.exit(main())
