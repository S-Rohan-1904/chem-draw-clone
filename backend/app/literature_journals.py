"""Journal articles about a molecule, linked by structure rather than by name.

PubChem links each compound to PubMed articles (MeSH indexing and depositor
links for that exact structure). Their metadata (title, journal, year,
citations) comes from Europe PMC in batches of 100 PubMed ids; Europe PMC has
no daily quota, unlike OpenAlex, whose budget the ChemRxiv search spends.
The batches are fetched at once. Popular compounds have tens of thousands of links, so a spread of at most 300
is looked up: the newest half and an even sample of the rest. Articles are
ranked by citations, with a boost for recent ones and for titles that name
the molecule. When PubChem has no links, Europe PMC is searched for articles
whose title names the molecule. Busy services are retried briefly. Never raises.
"""

from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import httpx

from .literature import MAILTO, _authors, _squash, _timeout, enabled, search_name

PUBCHEM_PMIDS = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{}/xrefs/PubMedID/JSON"
EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/searchPOST"
LOOKUP = 300  # PubMed ids looked up per molecule
BATCH = 100
KEEP = 20
VERSION = 2
RETRIES = 2  # extra tries when a service says it is busy (429 or 5xx)


def _spread(pmids: list[int]) -> list[int]:
    ids = sorted(set(pmids))
    if len(ids) <= LOOKUP:
        return ids
    newest = ids[-LOOKUP // 2:]
    rest = ids[: -LOOKUP // 2]
    step = len(rest) / (LOOKUP - len(newest))
    return [rest[int(i * step)] for i in range(LOOKUP - len(newest))] + newest


def _request(client: httpx.Client, method: str, url: str, **kwargs) -> httpx.Response:
    """The response, retried after a short wait while the service is busy."""
    for attempt in range(RETRIES + 1):
        r = client.request(method, url, **kwargs)
        if (r.status_code != 429 and r.status_code < 500) or attempt == RETRIES:
            return r
        try:
            wait = min(float(r.headers.get("Retry-After", "")), 5.0)
        except ValueError:
            wait = 1.0 + attempt
        time.sleep(wait)
    return r


def _item(w: dict) -> dict | None:
    types = [t.strip() for t in (w.get("pubType") or "").split(";")]
    if not w.get("title") or "retracted publication" in types or "retraction of publication" in types:
        return None
    doi = (w.get("doi") or "").lower()
    pmid = w.get("pmid") or ""
    url = f"https://doi.org/{doi}" if doi else (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "")
    if not url:
        return None
    year = w.get("pubYear")
    return {
        "title": w["title"].strip().removesuffix("."),
        "authors": _authors([a.strip().removesuffix(".") for a in (w.get("authorString") or "").split(",")]),
        "journal": w.get("journalTitle") or "",
        "year": int(year) if year and year.isdigit() else None,
        "date": w.get("firstPublicationDate") or "",
        "doi": doi,
        "pmid": pmid,
        "url": url,
        "cited_by": w.get("citedByCount") or 0,
        "type": "review" if "review" in types else "article",
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


def _europepmc(client: httpx.Client, query: str, size: int, sort: str = "") -> list[dict] | None:
    data = {"query": query, "format": "json", "resultType": "lite", "pageSize": str(size)}
    if sort:
        data["sort"] = sort
    r = _request(client, "POST", EUROPEPMC, data=data)
    if r.status_code != 200:
        return None
    return [it for it in (_item(w) for w in r.json().get("resultList", {}).get("result", [])) if it]


def _by_pmid(client: httpx.Client, pmids: list[int]) -> list[dict] | None:
    queries = ["SRC:MED AND (" + " OR ".join(f"EXT_ID:{p}" for p in pmids[i:i + BATCH]) + ")" for i in range(0, len(pmids), BATCH)]
    with ThreadPoolExecutor(len(queries) or 1) as pool:
        batches = list(pool.map(lambda q: _europepmc(client, q, BATCH), queries))
    if any(b is None for b in batches):
        return None
    return [it for b in batches for it in b]


def _by_title(client: httpx.Client, name: str) -> list[dict] | None:
    term = name.replace('"', " ")
    found = _europepmc(client, f'TITLE:"{term}" AND SRC:MED', 50, sort="CITED desc")
    if found is None:
        return None
    wanted = _squash(name)
    # Title search matches words in any form ("butanol" can find "butanal"); keep titles that name the molecule exactly.
    return [it for it in found if wanted in _squash(it["title"])]


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
                r = _request(client, "GET", PUBCHEM_PMIDS.format(cid))
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
