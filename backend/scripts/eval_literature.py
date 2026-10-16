"""Benchmark the Literature card for coverage and for the quality of what it shows first.

The molecules are a fixed sample of the reaction benchmark's set (60 teaching
molecules and 20 drugs, docs/benchmark/molecules.tsv) plus building blocks,
natural products and two structures no database knows
(docs/benchmark/literature_extra.tsv). Each is run through
literature_card.collect(), the same function the site calls, against an empty
cache. For each list it records:

- coverage: share of molecules with at least 1 and at least 5 items;
- names it: share of the top 5 whose title names the molecule itself (any of its names, not as part of
  a bigger molecule's name);
- chemistry: share of the top 5 journal articles that OpenAlex files under
  Chemistry, Chemical Engineering or Materials Science;
- free full text: share of the top 5 journal articles with an open-access copy
  (from OpenAlex, so every run is judged the same way, whatever the card shows);
- for patents, the share of items from 2017 on (the reaction index stops in 2016);
- failures (a source not reachable) and the median time per molecule.

Results are appended to docs/literature-benchmark.md under --label, and the
items of every run are kept in docs/benchmark/literature_<label>.json.

Usage: PATH=/opt/homebrew/opt/openjdk/bin:$PATH uv run python scripts/eval_literature.py --label "L0 baseline" [-j 4]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import statistics
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["CHEM_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "bench.db")  # an empty cache: every source is asked

import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")
load_dotenv(ROOT / ".env")

from app import cache, chem, literature_card, reaction  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.literature import MAILTO, names_it  # noqa: E402

DOCS = ROOT.parent / "docs"
BENCH = DOCS / "benchmark"
REPORT = DOCS / "literature-benchmark.md"
SAMPLE = {"teaching": 60, "drugs": 20}
TOP = 5
CHEMISTRY_FIELDS = {"Chemistry", "Chemical Engineering", "Materials Science"}
LISTS = ("journals", "chemrxiv", "patents")


def molecule_set() -> list[dict]:
    rnd = random.Random(7)
    with open(BENCH / "molecules.tsv", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f, delimiter="\t") if r["smiles"] and "." not in r["smiles"]]
    out = []
    for subset, n in SAMPLE.items():
        pool = [r for r in rows if r["set"] == subset]
        out += sorted(rnd.sample(pool, min(n, len(pool))), key=lambda r: r["name"])
    with open(BENCH / "literature_extra.tsv", encoding="utf-8") as f:
        out += list(csv.DictReader(f, delimiter="\t"))
    return out


def run(row: dict) -> dict:
    t = time.time()
    with SessionLocal() as db:
        try:
            lit = literature_card.collect(db, row["smiles"], row["name"], budget=None)  # every source, however slow
        except chem.ChemError as e:
            return {"error": str(e), "seconds": 0}
        key = Chem.MolToInchiKey(chem.mol_from_smiles(row["smiles"]))
        n = cache.lookup_name(db, key)
        names = [x for x in (n.title, n.iupac) if x] if n.found else []
    names.append(row["name"])
    return {"lit": lit, "names": [x for x in names if x], "seconds": time.time() - t}


def openalex_facts(dois: list[str]) -> dict[str, dict]:
    """{doi: {field, oa}} for the DOIs OpenAlex knows, 50 per request."""
    out: dict[str, dict] = {}
    key = os.environ.get("OPENALEX_API_KEY")
    with httpx.Client(timeout=30) as client:
        for i in range(0, len(dois), 50):
            chunk = dois[i:i + 50]
            params = {"filter": "doi:" + "|".join(chunk), "per_page": "50", "mailto": MAILTO,
                      "select": "doi,primary_topic,open_access"}
            if key:
                params["api_key"] = key
            r = client.get("https://api.openalex.org/works", params=params)
            if r.status_code != 200:
                continue
            for w in r.json().get("results", []):
                doi = (w.get("doi") or "").lower().removeprefix("https://doi.org/")
                field = (((w.get("primary_topic") or {}).get("field")) or {}).get("display_name", "")
                out[doi] = {"field": field, "oa": bool((w.get("open_access") or {}).get("is_oa"))}
    return out


def _pct(n: float, d: float) -> str:
    return f"{100 * n / d:.1f}%" if d else "n/a"


def _year(item: dict) -> int:
    y = item.get("year") or (item.get("date") or "")[:4]
    try:
        return int(y)
    except (TypeError, ValueError):
        return 0


def summarise(rows: list[dict], res: list[dict], facts: dict[str, dict]) -> str:
    lines = []
    subsets = list(dict.fromkeys(r["set"] for r in rows)) + ["all"]
    for subset in subsets:
        idx = [i for i, r in enumerate(rows) if (subset == "all" or r["set"] == subset) and "lit" in res[i]]
        n = len(idx)
        if not n:
            continue
        lines.append(f"\n**{subset}** ({n} molecules)\n")
        lines.append("| list | at least 1 | at least 5 | top 5 name it | top 5 chemistry | top 5 free full text | from 2017 on | not reachable |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for kind in LISTS:
            lists = [res[i]["lit"][kind] for i in idx]
            items = [d.get("items", []) for d in lists]
            top = [(i, it) for i, its in zip(idx, items) for it in its[:TOP]]
            named = sum(names_it(it.get("title", ""), res[i]["names"]) for i, it in top)
            chemistry = free = recent = "–"
            if kind == "journals":
                known = [facts[(it.get("doi") or "").lower()] for _, it in top if (it.get("doi") or "").lower() in facts]
                chemistry = _pct(sum(f["field"] in CHEMISTRY_FIELDS for f in known), len(known))
                free = _pct(sum(f["oa"] for f in known), len(known))
            if kind == "patents":
                every = [it for its in items for it in its]
                recent = _pct(sum(_year(it) >= 2017 for it in every), len(every))
            down = sum(not d.get("available", True) for d in lists)
            lines.append(f"| {kind} | {_pct(sum(len(x) >= 1 for x in items), n)} | {_pct(sum(len(x) >= 5 for x in items), n)} | "
                         f"{_pct(named, len(top))} | {chemistry} | {free} | {recent} | {down} |")
    return "\n".join(lines)


def _kept(result: dict) -> dict:
    """The first 10 items of each list, for reading a run back later."""
    if "lit" not in result:
        return {"error": result.get("error")}
    fields = ("title", "doi", "number", "year", "date", "url", "sources", "match")
    return {k: {"available": result["lit"][k].get("available", True),
                "items": [{f: it.get(f) for f in fields} for it in result["lit"][k].get("items", [])[:10]]}
            for k in LISTS}


def _slug(label: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in label.lower()).strip("_")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", required=True, help="name of this run in the report, e.g. 'L0 baseline'")
    ap.add_argument("-j", "--jobs", type=int, default=4)
    args = ap.parse_args()

    reaction.draw_reaction = lambda *a, **k: ""  # drawings are not scored
    init_db()
    rows = molecule_set()
    with ThreadPoolExecutor(args.jobs) as pool:
        res = list(pool.map(run, rows))
    dois = sorted({(it.get("doi") or "").lower() for r in res if "lit" in r
                   for it in r["lit"]["journals"].get("items", [])[:TOP] if it.get("doi")})
    facts = openalex_facts(dois)
    secs = [r["seconds"] for r in res if "lit" in r]
    text = (
        f"\n## {args.label} ({date.today().isoformat()})\n\n"
        f"{len(rows)} molecules, median {statistics.median(secs):.1f} s each with an empty cache "
        f"(slowest {max(secs):.1f} s). OpenAlex facts for {len(facts)} of {len(dois)} top-5 journal DOIs.\n"
        + summarise(rows, res, facts) + "\n"
    )
    BENCH.mkdir(parents=True, exist_ok=True)
    (BENCH / f"literature_{_slug(args.label)}.json").write_text(
        json.dumps([{"name": r["name"], "set": r["set"], **_kept(x)} for r, x in zip(rows, res)], indent=1), encoding="utf-8")
    if not REPORT.exists():
        REPORT.write_text(
            "# Literature benchmark\n\n"
            "Coverage and top-5 quality of the Literature card, produced by `backend/scripts/eval_literature.py` "
            "over 60 teaching molecules, 20 drugs, 12 building blocks, 8 natural products and 2 unknown structures. "
            "Each run is appended below.\n",
            encoding="utf-8",
        )
    with open(REPORT, "a", encoding="utf-8") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
