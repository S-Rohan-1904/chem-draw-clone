"""Journal articles about a molecule, linked by structure rather than by name.

PubChem links each compound to PubMed articles (MeSH indexing and depositor
links for that exact structure). Their metadata (title, journal, year,
citations) comes from OpenAlex in batches of 100 PubMed ids. Popular
compounds have tens of thousands of links, so a spread of at most 300 is
looked up: the newest half and an even sample of the rest. Articles are
ranked by citations, with a boost for recent ones and for titles that name
the molecule. When PubChem has no links, OpenAlex is searched for articles
whose title names the molecule. Never raises.
"""

from __future__ import annotations

import math
import os
from datetime import date

import httpx

from .literature import MAILTO, _authors, _bare_doi, _squash, _timeout, enabled, search_name

PUBCHEM_PMIDS = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{}/xrefs/PubMedID/JSON"
OPENALEX = "https://api.openalex.org/works"
LOOKUP = 300  # PubMed ids looked up per molecule
BATCH = 100  # OpenAlex allows 100 values in one OR filter
KEEP = 20
VERSION = 1
SELECT = "id,doi,title,publication_year,publication_date,cited_by_count,type,authorships,primary_location,ids,is_retracted"


def _spread(pmids: list[int]) -> list[int]:
    ids = sorted(set(pmids))
    if len(ids) <= LOOKUP:
        return ids
    newest = ids[-LOOKUP // 2:]
    rest = ids[: -LOOKUP // 2]
    step = len(rest) / (LOOKUP - len(newest))
    return [rest[int(i * step)] for i in range(LOOKUP - len(newest))] + newest


def _params(extra: dict) -> dict:
    params = {"select": SELECT, "mailto": MAILTO, **extra}
    key = os.environ.get("OPENALEX_API_KEY")
    if key:
        params["api_key"] = key
    return params


def _item(w: dict) -> dict | None:
    if not w.get("title") or w.get("is_retracted"):
        return None
    doi = _bare_doi(w.get("doi"))
    pmid = ((w.get("ids") or {}).get("pmid") or "").rsplit("/", 1)[-1]
    source = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
    url = f"https://doi.org/{doi}" if doi else (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "")
    if not url:
        return None
    return {
        "title": w["title"],
        "authors": _authors([(a.get("author") or {}).get("display_name", "") for a in w.get("authorships") or []]),
        "journal": source,
        "year": w.get("publication_year"),
        "date": w.get("publication_date") or "",
        "doi": doi,
        "pmid": pmid,
        "url": url,
        "cited_by": w.get("cited_by_count") or 0,
        "type": w.get("type") or "",
    }


def _score(item: dict, names: list[str]) -> float:
    s = math.log1p(item["cited_by"])
    age = date.today().year - (item["year"] or 1900)
    s += 2 if age <= 5 else 1 if age <= 10 else 0
    title = _squash(item["title"])
    if any(n and n in title for n in names):
        s += 6  # the article is about this molecule, not one of many it mentions
    if item["type"] == "review":
        s += 1
    return s


def _by_pmid(client: httpx.Client, pmids: list[int]) -> list[dict] | None:
    out = []
    for i in range(0, len(pmids), BATCH):
        chunk = pmids[i:i + BATCH]
        r = client.get(OPENALEX, params=_params({"filter": "ids.pmid:" + "|".join(map(str, chunk)), "per_page": str(BATCH)}))
        if r.status_code != 200:
            return None
        out += [it for it in (_item(w) for w in r.json().get("results", [])) if it]
    return out


def _by_title(client: httpx.Client, name: str) -> list[dict] | None:
    term = name.replace(",", " ")
    r = client.get(OPENALEX, params=_params({
        "filter": f"title.search:{term},type:article|review",
        "sort": "cited_by_count:desc",
        "per_page": "50",
    }))
    if r.status_code != 200:
        return None
    wanted = _squash(name)
    # OpenAlex stems words ("butanol" finds "butanal"); keep titles that name the molecule exactly.
    return [it for it in (_item(w) for w in r.json().get("results", [])) if it and wanted in _squash(it["title"])]


def search(cid: int | None, names: list[str]) -> tuple[dict, bool]:
    """(payload, complete); incomplete means a service failed and the result should not be cached."""
    base = {"available": True, "items": [], "total": 0, "match": "", "query": "", "_v": VERSION}
    if not enabled():
        return {**base, "available": False, "reason": "Literature lookup is turned off on this server."}, False
    names = [search_name(n) for n in names if n]
    squashed = [_squash(n) for n in names]
    try:
        with httpx.Client(timeout=_timeout(), follow_redirects=True, headers={"User-Agent": f"Chem Illustrator (mailto:{MAILTO})"}) as client:
            pmids: list[int] = []
            if cid:
                r = client.get(PUBCHEM_PMIDS.format(cid))
                if r.status_code == 200:
                    info = r.json().get("InformationList", {}).get("Information", [{}])[0]
                    pmids = [int(p) for p in info.get("PubMedID", [])]
                elif r.status_code != 404:
                    return {**base, "available": False, "reason": "PubChem is not reachable right now."}, False
            if pmids:
                items = _by_pmid(client, _spread(pmids))
                match = "pubchem"
            elif names:
                items = _by_title(client, names[0])
                match = "title"
            else:
                return {**base, "available": False, "reason": "There is no PubChem entry or name to search journals with."}, True
    except (httpx.HTTPError, ValueError):
        items = None
    if items is None:
        return {**base, "available": False, "reason": "The journal search is not reachable right now."}, False
    items.sort(key=lambda it: -_score(it, squashed))
    return {**base, "items": items[:KEEP], "total": len(pmids) if pmids else len(items), "match": match,
            "query": names[0] if names else ""}, True
