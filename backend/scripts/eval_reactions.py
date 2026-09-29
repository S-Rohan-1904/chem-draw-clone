"""Benchmark the Reactions and Literature cards over a fixed set of molecules.

The set is the teaching names in app/data/common_names.txt plus 50 drugs,
resolved once to SMILES and kept in docs/benchmark/molecules.tsv so later runs
score exactly the same structures. For each molecule it records how many
"Used in" and "Made by" reaction types the card shows and, with --literature,
whether each literature
source finds anything. A fixed 40-molecule sheet with the top 5 rows in each
direction is written for grading by hand.

Results are appended to docs/reaction-benchmark.md under --label.

Usage: PATH=/opt/homebrew/opt/openjdk/bin:$PATH uv run python scripts/eval_reactions.py --label "M0 baseline" [--literature] [-j 4]
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402

from app import chem, reaction, reactiondb, resolver  # noqa: E402

RDLogger.DisableLog("rdApp.*")
load_dotenv(ROOT / ".env")  # OPENALEX_API_KEY, without which OpenAlex's shared free budget runs out

DOCS = ROOT.parent / "docs"
BENCH = DOCS / "benchmark"
MOLECULES = BENCH / "molecules.tsv"
REPORT = DOCS / "reaction-benchmark.md"
NAMES = ROOT / "app" / "data" / "common_names.txt"

DRUGS = [
    "aspirin", "ibuprofen", "paracetamol", "naproxen", "diclofenac", "atorvastatin", "simvastatin",
    "rosuvastatin", "metformin", "sitagliptin", "lisinopril", "enalapril", "losartan", "valsartan",
    "amlodipine", "nifedipine", "metoprolol", "propranolol", "atenolol", "warfarin", "clopidogrel",
    "apixaban", "rivaroxaban", "omeprazole", "esomeprazole", "ranitidine", "loratadine", "cetirizine",
    "fluoxetine", "sertraline", "citalopram", "venlafaxine", "diazepam", "alprazolam", "haloperidol",
    "olanzapine", "quetiapine", "sildenafil", "tadalafil", "imatinib", "gefitinib", "erlotinib",
    "tamoxifen", "oseltamivir", "acyclovir", "ciprofloxacin", "amoxicillin", "fluconazole",
    "morphine", "caffeine",
]
PRECISION_TEACHING = 30
PRECISION_DRUGS = 10


# --- molecule set ------------------------------------------------------------

def _resolve(name: str) -> str:
    try:
        smiles, _ = chem.resolve(name)
        return Chem.MolToSmiles(chem.mol_from_smiles(smiles))
    except Exception:  # noqa: BLE001 - an unresolved name is reported, not fatal
        return ""


def _single(rows: list[dict]) -> list[dict]:
    """One row per molecule. Some teaching entries name several molecules at once
    ("methanol ethanol propan-1-ol propan-2-ol") and resolve to a dotted SMILES that
    no index entry can match; score each molecule, once per set."""
    out, seen = [], set()
    for row in rows:
        parts = row["smiles"].split(".")
        names = row["name"].split(" ") if len(parts) > 1 else [row["name"]]
        if len(names) != len(parts):
            names = [f"{row['name']} ({i + 1})" for i in range(len(parts))]
        for name, smi in zip(names, parts):
            mol = Chem.MolFromSmiles(smi)
            if mol is None:
                continue
            key = (row["set"], Chem.MolToInchiKey(mol))
            if key not in seen:
                seen.add(key)
                out.append({"name": name, "set": row["set"], "smiles": smi})
    return out


def molecule_set(jobs: int) -> list[dict]:
    """[{name, set, smiles}], resolving and saving the set on first use."""
    if MOLECULES.exists():
        with open(MOLECULES, encoding="utf-8") as f:
            return _single([row for row in csv.DictReader(f, delimiter="\t") if row["smiles"]])
    names = [n.strip() for n in NAMES.read_text(encoding="utf-8").splitlines() if n.strip()]
    entries = [(n, "teaching") for n in names] + [(n, "drugs") for n in DRUGS]
    with ThreadPoolExecutor(jobs) as pool:
        smiles = list(pool.map(lambda e: _resolve(e[0]), entries))
    rows = [{"name": n, "set": s, "smiles": smi} for (n, s), smi in zip(entries, smiles)]
    BENCH.mkdir(parents=True, exist_ok=True)
    with open(MOLECULES, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["name", "set", "smiles"], delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    missing = [r["name"] for r in rows if not r["smiles"]]
    if missing:
        print(f"{len(missing)} names did not resolve and are left out: {', '.join(missing[:20])}")
    return _single([r for r in rows if r["smiles"]])


# --- scoring -------------------------------------------------------------------

def score_reactions(row: dict) -> dict:
    try:
        return reactiondb.lookup(row["smiles"])
    except Exception:  # noqa: BLE001
        return {"uses": [], "makes": []}


def score_literature(row: dict) -> dict:
    """Items found by each literature source, searched the way the /literature endpoint does."""
    from app import literature, literature_journals, literature_patents, manufacture, wikipedia

    key = Chem.MolToInchiKey(chem.mol_from_smiles(row["smiles"]))
    info = resolver.name_for_inchikey(key) or {}
    cid = info.get("cid")
    names = [n for n in (info.get("title", ""), row["name"], info.get("iupac", "")) if n]
    chemrxiv, _ = literature.search(names, more=lambda: [resolver.title_for_skeleton(key), *literature.synonyms(cid)])
    journals, _ = literature_journals.search(cid, names)
    patents, _ = literature_patents.search(reactiondb.lookup(row["smiles"], draw=False), cid)
    made, _ = manufacture.search(cid, key)
    wiki, _ = wikipedia.search(key)
    return {"chemrxiv": len(chemrxiv["items"]), "journals": len(journals["items"]), "patents": len(patents["items"]),
            "pubchem methods": len(made["methods"]), "wikipedia": len(wiki["paragraphs"])}


# --- report --------------------------------------------------------------------

def _pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}%" if d else "n/a"


def summarise(rows: list[dict], results: list[dict], lit: list[dict] | None) -> str:
    lines = []
    for subset in ("teaching", "drugs", "all"):
        idx = [i for i, r in enumerate(rows) if subset == "all" or r["set"] == subset]
        n = len(idx)
        if not n:
            continue
        lines.append(f"\n**{subset}** ({n} molecules)\n")
        lines.append("| | at least 1 type | at least 5 types |")
        lines.append("|---|---|---|")
        for d in ("uses", "makes"):
            counts = [len(results[i][d]) for i in idx]
            textbook = [len(results[i][d]) + len(results[i].get(f"textbook_{d}", [])) for i in idx]
            both = [x + len(results[i].get(f"enzyme_{d}", [])) for x, i in zip(textbook, idx)]
            name = "Used in" if d == "uses" else "Made by"
            lines.append(f"| {name} | {_pct(sum(x >= 1 for x in counts), n)} | {_pct(sum(x >= 5 for x in counts), n)} |")
            if any(results[i].get(f"textbook_{d}") for i in idx):
                lines.append(f"| {name}, with textbook routes | {_pct(sum(x >= 1 for x in textbook), n)} | "
                             f"{_pct(sum(x >= 5 for x in textbook), n)} |")
            lines.append(f"| {name}, with enzyme reactions too | {_pct(sum(x >= 1 for x in both), n)} | {_pct(sum(x >= 5 for x in both), n)} |")
        if lit:
            # Made by anything the card shows: a recorded reaction, a PubChem method or the Wikipedia section.
            made = sum(1 for i in idx if results[i]["makes"] or results[i].get("enzyme_makes") or results[i].get("textbook_makes")
                       or lit[i].get("pubchem methods") or lit[i].get("wikipedia"))
            lines.append(f"| Made by, with PubChem methods and Wikipedia | {_pct(made, n)} | |")
            sources = sorted({k for i in idx for k in lit[i]})
            lines.append("")
            lines.append("| literature source | at least 1 item |")
            lines.append("|---|---|")
            for s in sources:
                lines.append(f"| {s} | {_pct(sum(lit[i].get(s, 0) >= 1 for i in idx), n)} |")
    return "\n".join(lines)


def _slug(label: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in label.lower()).strip("_")


def precision_sheet(rows: list[dict], results: list[dict], label: str) -> Path:
    rnd = random.Random(40)
    teaching = [i for i, r in enumerate(rows) if r["set"] == "teaching"]
    drugs = [i for i, r in enumerate(rows) if r["set"] == "drugs"]
    chosen = sorted(rnd.sample(teaching, min(PRECISION_TEACHING, len(teaching)))) + sorted(rnd.sample(drugs, min(PRECISION_DRUGS, len(drugs))))
    path = BENCH / f"precision_{_slug(label)}.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "smiles", "direction", "source", "rank", "label", "count", "example", "reference", "right_chemistry", "right_example", "note"])
        for i in chosen:
            row, res = rows[i], results[i]
            for d in ("uses", "makes"):
                items = res[d]
                if not items:
                    w.writerow([row["name"], row["smiles"], d, "", "", "(none)", "", "", "", "", "", ""])
                for rank, r in enumerate(items, 1):
                    ref = r.get("ref") or r.get("patent") or ""
                    w.writerow([row["name"], row["smiles"], d, r.get("source", "uspto"), rank, r["label"], r.get("count", ""), r.get("smiles", ""), ref, "", "", ""])
    return path


def index_meta() -> dict:
    con = reactiondb._connect(str(reactiondb.db_path()))
    try:
        return dict(con.execute("SELECT key, value FROM meta").fetchall())
    except Exception:  # noqa: BLE001
        return {}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", required=True, help="name of this run in the report, e.g. 'M0 baseline'")
    ap.add_argument("--literature", action="store_true", help="also query the literature sources (network, a few minutes)")
    ap.add_argument("-j", "--jobs", type=int, default=4)
    args = ap.parse_args()

    reaction.draw_reaction = lambda *a, **k: ""  # drawings are not scored
    if not reactiondb.available():
        sys.exit(f"No reaction index at {reactiondb.db_path()}")
    t0 = time.time()
    rows = molecule_set(args.jobs)
    results = [score_reactions(r) for r in rows]
    t_rx = time.time() - t0
    lit = None
    if args.literature:
        with ThreadPoolExecutor(args.jobs) as pool:
            lit = list(pool.map(score_literature, rows))
        (BENCH / f"literature_{_slug(args.label)}.json").write_text(json.dumps([{"name": r["name"], **x} for r, x in zip(rows, lit)], indent=1))
    sheet = precision_sheet(rows, results, args.label)

    meta = index_meta()
    index = f"{meta.get('reactions', '?')} reactions, {meta.get('molecules', '?')} molecules, built {meta.get('built', '?')}"
    text = (
        f"\n## {args.label} ({date.today().isoformat()})\n\n"
        f"Index {index}. "
        f"Reactions scored in {t_rx:.0f} s. Precision sheet `{sheet.relative_to(ROOT.parent)}`.\n"
        + summarise(rows, results, lit) + "\n"
    )
    if not REPORT.exists():
        REPORT.write_text(
            "# Reaction and literature benchmark\n\n"
            "Coverage of the Reactions and Literature cards over the teaching set (app/data/common_names.txt) "
            "and 50 drugs, produced by `backend/scripts/eval_reactions.py`. Each run is appended below.\n",
            encoding="utf-8",
        )
    with open(REPORT, "a", encoding="utf-8") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
