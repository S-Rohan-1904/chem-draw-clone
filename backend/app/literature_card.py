"""The Literature card: every source searched for one molecule, each cached on its own,
then merged into three lists (ChemRxiv preprints, journal articles, patents).

Journal articles come from four sources, each finding them a different way:
PubMed links in PubChem and ChEMBL's curated papers (both by exact structure),
OpenAlex chemistry journals (by name in title or abstract) and Europe PMC's
chemical tagging (mentions anywhere in the text, by ChEBI entry). Articles found
by several are listed once with every source. Patents come from the reaction
index (US worked examples to 2016) and SureChEMBL (every country and year).

The router and the benchmark (scripts/eval_literature.py) both call collect(), so the
benchmark scores exactly what the site shows.
"""

from __future__ import annotations

import math
import os
import re
import threading
from concurrent.futures import Future, ThreadPoolExecutor, wait
from datetime import date
from functools import partial

from rdkit import Chem
from sqlalchemy.orm import Session

from . import (cache, chem, literature, literature_chembl, literature_journals, literature_mentions, literature_openalex,
               literature_patents, literature_surechembl, ord_papers, reactiondb, resolver)
from .db import SessionLocal
from .literature import _squash, names_it

KEEP = 40
# Seconds the card waits for its sources; slower ones (ChEMBL's API can take half a minute) finish in the
# background, are cached, and arrive when the page asks again.
BUDGET = float(os.environ.get("CHEM_LITERATURE_BUDGET", "10"))
_POOL = ThreadPoolExecutor(16, thread_name_prefix="literature")
_INFLIGHT: dict[tuple[str, str], Future] = {}
_LOCK = threading.Lock()
# Sources of journal articles: (cache kind, label shown on the card, how it matches).
JOURNAL_SOURCES = {"journals": ("PubMed", "structure"), "chembl": ("ChEMBL", "structure"),
                   "openalex": ("OpenAlex", "name"), "mentions": ("Europe PMC", "text"), "ord": ("ORD", "structure")}
_MAKING = re.compile(r"\b(synthe\w*|prepar\w*|route\w* to|production of|manufactur\w*|process for|scale-up)\b", re.I)
_MATCH_RANK = {"structure": 3, "title": 2, "abstract": 1, "text": 0}


def _key(item: dict) -> str:
    return item.get("doi") or (f"pmid:{item['pmid']}" if item.get("pmid") else "t:" + _squash(item.get("title", "")))


def _score(item: dict) -> float:
    s = math.log1p(item.get("cited_by") or 0)
    age = date.today().year - (item.get("year") or 1900)
    s += 2 if age <= 5 else 1 if age <= 10 else 0
    if item["about"]:
        s += 6  # the article is about this molecule, not one of many it mentions
    if item["making"]:
        s += 3 if item["about"] else 1
    if item.get("type") == "review":
        s += 1
    if item.get("oa_url"):
        s += 1  # readers can open it
    if item["match"] == "structure":
        s += 1
    elif item["match"] == "text" and not item["about"]:
        s -= 2  # a passing mention
    return s + len(item["sources"]) - 1


def merge_journals(found: dict[str, dict], names: list[str]) -> dict:
    """One ranked list from the journal sources' payloads {kind: payload}."""
    merged: dict[str, dict] = {}
    for kind, (label, how) in JOURNAL_SOURCES.items():
        for raw in found.get(kind, {}).get("items", []):
            match = raw.get("match") or how
            match = "structure" if how == "structure" else match
            key = _key(raw)
            item = merged.get(key)
            if item is None:
                item = merged[key] = {**raw, "sources": [], "match": match}
            else:
                for field in ("doi", "pmid", "journal", "authors", "oa_url", "snippet", "date", "ord"):
                    if not item.get(field) and raw.get(field):
                        item[field] = raw[field]
                item["cited_by"] = max(item.get("cited_by") or 0, raw.get("cited_by") or 0)
                if _MATCH_RANK.get(match, 0) > _MATCH_RANK.get(item["match"], 0):
                    item["match"] = match
            if label not in item["sources"]:
                item["sources"].append(label)
    items = list(merged.values())
    for it in items:
        it["about"] = names_it(it["title"], names)
        it["making"] = bool(_MAKING.search(it["title"]))
        it.setdefault("snippet", "")
    items.sort(key=lambda it: -_score(it))
    sources = {label: {"available": found[kind].get("available", True), "count": len(found[kind].get("items", [])),
                       "total": found[kind].get("total", 0), "reason": found[kind].get("reason", ""), "stale": bool(found[kind].get("stale")),
                       "pending": bool(found[kind].get("pending"))}
               for kind, (label, _) in JOURNAL_SOURCES.items() if kind in found}
    return {"available": any(s["available"] for s in sources.values()), "items": items[:KEEP], "total": len(items),
            "sources": sources, "query": names[0] if names else "",
            "reason": "None of the journal sources is reachable right now." if not any(s["available"] for s in sources.values()) else ""}


def merge_patents(index: dict, sure: dict, names: list[str]) -> dict:
    """The reaction index's patents (with their worked examples) and SureChEMBL's, listed once each."""
    by_id: dict[str, dict] = {}
    for it in index.get("items", []):
        ids = literature_patents.pubchem_ids(it["number"])
        by_id[ids[0] if ids else it["number"]] = {**it, "sources": ["Reaction records"], "making": False}
    for it in sure.get("items", []):
        known = by_id.get(it["number"])
        if known:
            known["sources"].append("SureChEMBL")
            for field in ("title", "date", "year", "assignee"):
                known[field] = known.get(field) or it.get(field)
        else:
            by_id[it["number"]] = {**it, "reactions": [], "sources": ["SureChEMBL"]}
    items = list(by_id.values())
    for it in items:
        it["about"] = names_it(it.get("title", ""), names)
        it["making"] = it.get("making") or bool(_MAKING.search(it.get("title", "")))
    items.sort(key=lambda it: (-(3 * bool(it["reactions"]) + 2 * it["about"] + 2 * it["making"]), -(it.get("year") or 0)))
    return {"available": True, "items": items, "cid": index.get("cid"), "pubchem_url": index.get("pubchem_url", ""),
            "pending": bool(index.get("pending")),
            "surechembl": {"available": sure.get("available", True), "total": sure.get("total", 0), "reason": sure.get("reason", ""),
                           "pending": bool(sure.get("pending"))}}


def _submit(key: str, kind: str, search) -> Future:
    """Start a search, or join the same one already running for another request."""
    with _LOCK:
        future = _INFLIGHT.get((key, kind))
        if future is not None:
            return future
        future = _INFLIGHT[(key, kind)] = _POOL.submit(search)
    # Outside the lock: a search that has already finished runs the callback right here.
    future.add_done_callback(lambda f: _forget(key, kind, f))
    return future


def _forget(key: str, kind: str, future: Future) -> None:
    with _LOCK:
        if _INFLIGHT.get((key, kind)) is future:
            del _INFLIGHT[(key, kind)]


def _store_later(key: str, kind: str, future: Future) -> None:
    """Cache a search that finished after the response went out."""
    try:
        data, complete = future.result()
        with SessionLocal() as db:
            cache.store_literature(db, key, kind, data, complete)
    except Exception:  # noqa: BLE001 - nobody is waiting for this result
        pass


def collect(db: Session, smiles: str, typed_name: str = "", budget: float | None = BUDGET) -> dict:
    """{chemrxiv, journals, patents} for the molecule. Raises chem.ChemError for bad SMILES.
    Sources that take longer than `budget` seconds are left out as pending (None waits for all)."""
    mol = chem.mol_from_smiles(smiles)
    key = Chem.MolToInchiKey(mol)
    row = cache.lookup_name(db, key) if key else None
    found = row is not None and row.found
    cid = row.cid if found else None
    # PubChem's title first (usually the common name), then what the user typed, then the
    # systematic name; the stereo-free record's title and PubChem synonyms only if all of those find nothing.
    names = [n for n in ((row.title if found else ""), typed_name.strip(), (row.iupac if found else "")) if n]
    plain = Chem.MolToSmiles(mol, isomericSmiles=False)
    searches = {
        "chemrxiv": lambda: literature.search(names, more=lambda: [resolver.title_for_skeleton(key), *literature.synonyms(cid)]),
        "journals": lambda: literature_journals.search(cid, names),
        "chembl": lambda: literature_chembl.search(key),
        "openalex": lambda: literature_openalex.search(names),
        "mentions": lambda: literature_mentions.search(key),
        "patents": lambda: literature_patents.search(reactiondb.lookup(smiles, draw=False), cid),
        "surechembl": lambda: literature_surechembl.search(Chem.MolToSmiles(mol), plain, names),
    }
    out = {kind: cache.cached_literature(db, key, kind) for kind in searches}
    # The searches call different services, so run them side by side; the session stays on this thread.
    futures = {kind: _submit(key, kind, searches[kind]) for kind, hit in out.items() if hit is None}
    wait(futures.values(), timeout=budget)
    for kind, future in futures.items():
        if future.done():
            data, complete = future.result()
            out[kind] = cache.store_literature(db, key, kind, data, complete)
        else:
            # Still searching: answer without it, and keep the result for the page's next request.
            future.add_done_callback(partial(_store_later, key, kind))
            out[kind] = {"available": True, "items": [], "pending": True, "total": 0, "query": names[0] if names else ""}
    ord_found = ord_papers.search(key)
    if ord_found["installed"]:  # a server without the index just leaves the source out
        out["ord"] = ord_found
    search_names = names + [n for n in (out["mentions"].get("query"),) if n]
    return {
        "chemrxiv": out["chemrxiv"],
        "journals": merge_journals({k: out[k] for k in JOURNAL_SOURCES if k in out}, search_names),
        "patents": merge_patents(out["patents"], out["surechembl"], search_names),
    }
