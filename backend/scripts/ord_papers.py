"""Build ord_papers.db: which papers' reactions in the Open Reaction Database use or make each molecule.

The ORD (https://open-reaction-database.org, data CC BY-SA 4.0) publishes its
datasets as Parquet files of reaction protobufs. The USPTO datasets are Lowe's
patent reactions, already in the reaction index, so they are skipped; the rest
are mostly high-throughput experiments and literature datasets, each citing the
paper it comes from (a paper linked to thousands of molecules is a compilation,
such as a machine-learning set drawn from patents, and is left out). For every compound in those reactions (reactants, reagents,
catalysts, solvents, products) the InChIKey is linked to the paper's DOI with its
roles and the number of reactions. Paper details (title, journal, year,
citations, open-access copy) are read from OpenAlex; a DOI OpenAlex does not
know (some datasets give a truncated one) is dropped.

`fetch` downloads the Parquet files from the ORD's Hugging Face mirror; `build`
writes the index. ord_schema and huggingface_hub run in a throwaway environment
so they never enter the project:

    ORD='uv run --isolated --no-project --python 3.12 --with ord-schema --with rdkit --with httpx --with huggingface_hub python scripts/ord_papers.py'
    $ORD fetch path/to/ord-raw
    $ORD build path/to/ord-raw            # writes backend/app/data/ord_papers.db
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAILTO = "chem-forge@users.noreply.github.com"
USPTO_DOI = "10.6084/m9.figshare.5104873"
# A paper linked to more molecules than this is a compilation (e.g. a machine-learning set drawn from
# patents), not a report of its own reactions; the largest real experiment in the ORD has about 1,000.
MAX_MOLECULES = 2000
_DOI = re.compile(r"10\.\d{4,9}/[^\s\"<>,;]+[^\s\"<>,;.)]")


def fetch(out_dir: str) -> None:
    from huggingface_hub import snapshot_download

    snapshot_download("open-reaction-database/ord-data", repo_type="dataset", allow_patterns=["data/*/*.parquet"],
                      local_dir=out_dir, max_workers=8)


def _doi(text: str) -> str:
    m = _DOI.search(text or "")
    return m.group(0).lower() if m else ""


def _links(raw_dir: str) -> tuple[dict, dict]:
    """({(inchikey, doi): [roles, reactions]}, {doi: dataset names})."""
    from ord_schema.datasets import load_dataset
    from ord_schema.proto import reaction_pb2
    from rdkit import Chem, RDLogger

    RDLogger.DisableLog("rdApp.*")
    smiles_type = reaction_pb2.CompoundIdentifier.SMILES
    inchi_type = reaction_pb2.CompoundIdentifier.INCHI
    roles_enum = reaction_pb2.ReactionRole.DESCRIPTOR.enum_types_by_name["ReactionRoleType"]

    def role_name(number: int) -> str:
        value = roles_enum.values_by_number.get(number)
        return value.name if value else "unspecified"
    keys: dict[str, str] = {}

    def inchikey(compound) -> str:
        for ident in compound.identifiers:
            if ident.type in (smiles_type, inchi_type) and ident.value:
                if ident.value not in keys:
                    mol = Chem.MolFromSmiles(ident.value) if ident.type == smiles_type else Chem.MolFromInchi(ident.value)
                    keys[ident.value] = Chem.MolToInchiKey(mol) if mol is not None else ""
                if keys[ident.value]:
                    return keys[ident.value]
        return ""

    links: dict[tuple[str, str], list] = defaultdict(lambda: [set(), 0])
    datasets: dict[str, set[str]] = defaultdict(set)
    for path in sorted(glob.glob(os.path.join(raw_dir, "data", "*", "*.parquet"))):
        ds = load_dataset(path)
        if ds.name.lower().startswith("uspto"):
            continue
        fallback = _doi(ds.description) or _doi(ds.name)
        n = 0
        for reaction in ds.reactions:
            doi = _doi(reaction.provenance.doi) or _doi(reaction.provenance.publication_url) or fallback
            if not doi or doi.startswith(USPTO_DOI):
                continue
            n += 1
            seen: dict[str, set[str]] = defaultdict(set)
            for inp in reaction.inputs.values():
                for c in inp.components:
                    key = inchikey(c)
                    if key:
                        seen[key].add(role_name(c.reaction_role).lower())
            for outcome in reaction.outcomes:
                for p in outcome.products:
                    key = inchikey(p)
                    if key:
                        seen[key].add("product")
            for key, roles in seen.items():
                entry = links[(key, doi)]
                entry[0] |= roles
                entry[1] += 1
            datasets[doi].add(ds.name)
        print(f"{ds.name[:60]:60s} {n:7d} reactions with a DOI", file=sys.stderr)
    return links, datasets


def _papers(dois: list[str]) -> dict[str, dict]:
    import httpx

    out: dict[str, dict] = {}
    key = os.environ.get("OPENALEX_API_KEY")
    with httpx.Client(timeout=60) as client:
        for i in range(0, len(dois), 40):
            chunk = dois[i:i + 40]
            params = {"filter": "doi:" + "|".join(chunk), "per_page": "50", "mailto": MAILTO,
                      "select": "doi,title,authorships,primary_location,publication_year,cited_by_count,open_access,type"}
            if key:
                params["api_key"] = key
            r = client.get("https://api.openalex.org/works", params=params)
            r.raise_for_status()
            for w in r.json().get("results", []):
                doi = (w.get("doi") or "").lower().removeprefix("https://doi.org/")
                names = [(a.get("author") or {}).get("display_name", "") for a in w.get("authorships") or []]
                oa = w.get("open_access") or {}
                out[doi] = {
                    "title": re.sub(r"<[^>]+>", "", w.get("title") or "").strip().removesuffix("."),
                    "authors": ", ".join(names[:3]) + (" et al." if len(names) > 3 else ""),
                    "journal": (((w.get("primary_location") or {}).get("source")) or {}).get("display_name") or "",
                    "year": w.get("publication_year"), "cited_by": w.get("cited_by_count") or 0,
                    "oa_url": (oa.get("oa_url") or "") if oa.get("is_oa") else "",
                    "type": "review" if w.get("type") == "review" else "article",
                }
            time.sleep(0.2)
    return out


def build(raw_dir: str, out: str) -> None:
    links, datasets = _links(raw_dir)
    per_doi: dict[str, int] = defaultdict(int)
    for _, doi in links:
        per_doi[doi] += 1
    compilations = sorted(d for d, n in per_doi.items() if n > MAX_MOLECULES)
    if compilations:
        print(f"Left out as compilations (more than {MAX_MOLECULES} molecules): {', '.join(compilations)}", file=sys.stderr)
        datasets = {d: v for d, v in datasets.items() if d not in compilations}
    # OpenAlex can answer a DOI with another of the work's DOIs; only the ones asked for join the links.
    papers = {doi: p for doi, p in _papers(sorted(datasets)).items() if doi in datasets}
    missing = sorted(set(datasets) - set(papers))
    if missing:
        print(f"{len(missing)} DOIs not in OpenAlex, dropped: {', '.join(missing)}", file=sys.stderr)
    tmp = out + ".tmp"
    if os.path.exists(tmp):
        os.unlink(tmp)
    con = sqlite3.connect(tmp)
    con.executescript("""
        CREATE TABLE papers (doi TEXT PRIMARY KEY, title TEXT, authors TEXT, journal TEXT, year INTEGER,
                             cited_by INTEGER, oa_url TEXT, type TEXT, datasets TEXT);
        CREATE TABLE links (inchikey TEXT, doi TEXT, roles TEXT, reactions INTEGER, PRIMARY KEY (inchikey, doi)) WITHOUT ROWID;
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
    """)
    con.executemany("INSERT INTO papers VALUES (?,?,?,?,?,?,?,?,?)",
                    [(doi, p["title"], p["authors"], p["journal"], p["year"], p["cited_by"], p["oa_url"], p["type"],
                      "; ".join(sorted(datasets[doi]))) for doi, p in papers.items()])
    rows = [(key, doi, ",".join(sorted(roles)), n) for (key, doi), (roles, n) in links.items() if doi in papers]
    con.executemany("INSERT INTO links VALUES (?,?,?,?)", rows)
    con.executemany("INSERT INTO meta VALUES (?,?)", [("built", date.today().isoformat()), ("papers", str(len(papers))),
                                                      ("links", str(len(rows))), ("molecules", str(len({r[0] for r in rows})))])
    con.commit()
    con.execute("VACUUM")
    con.close()
    os.replace(tmp, out)
    print(f"{out}: {len(papers)} papers, {len(rows)} links, {len({r[0] for r in rows})} molecules", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["fetch", "build"])
    ap.add_argument("raw_dir")
    ap.add_argument("--out", default=str(ROOT / "app" / "data" / "ord_papers.db"))
    args = ap.parse_args()
    if args.command == "fetch":
        fetch(args.raw_dir)
    else:
        build(args.raw_dir, args.out)


if __name__ == "__main__":
    main()
