"""Chemistry journal articles that name a molecule, from OpenAlex.

PubMed (the other journal source) indexes mostly biomedical journals, so the
organic, inorganic and materials journals where a reagent or building block is
actually used are rarely there. OpenAlex covers them: this searches titles and
abstracts for the molecule's names, keeps articles whose primary topic is in
Chemistry, Chemical Engineering or Materials Science, and leaves out ChemRxiv
(listed on its own). One query per molecule, all names joined by OR, since every
OpenAlex search costs the same share of the daily budget. Never raises.
"""

from __future__ import annotations

import os

import httpx

from .literature_journals import clean_title
from .literature import CHEMRXIV_SOURCE, MAILTO, OPENALEX, _abstract, _authors, _bare_doi, _term, _timeout, enabled, names_it, search_name, snippet

VERSION = 1
FIELDS = "16|15|25"  # OpenAlex field ids: Chemistry, Chemical Engineering, Materials Science
FETCH = 25


def _item(w: dict, names: list[str]) -> dict | None:
    doi = _bare_doi(w.get("doi")).lower()
    title = (w.get("title") or "").strip()
    if not doi or not title or w.get("is_retracted"):
        return None
    source = ((w.get("primary_location") or {}).get("source") or {})
    oa = w.get("open_access") or {}
    abstract = _abstract(w.get("abstract_inverted_index"))
    return {
        "title": clean_title(title),
        "authors": _authors([(a.get("author") or {}).get("display_name", "") for a in w.get("authorships") or []]),
        "journal": source.get("display_name") or "",
        "year": w.get("publication_year"),
        "date": w.get("publication_date") or "",
        "doi": doi,
        "pmid": "",
        "url": f"https://doi.org/{doi}",
        "cited_by": w.get("cited_by_count") or 0,
        "type": "review" if w.get("type") == "review" else "article",
        "oa_url": (oa.get("oa_url") or "") if oa.get("is_oa") else "",
        "snippet": next((s for s in (snippet(abstract, n) for n in names) if s), ""),
        "match": "title" if names_it(title, names) else "abstract",
    }


def search(names: list[str]) -> tuple[dict, bool]:
    """(payload, complete); incomplete means OpenAlex failed and the result should not be cached."""
    base = {"available": True, "items": [], "total": 0, "query": "", "_v": VERSION}
    if not enabled():
        return {**base, "available": False, "reason": "Literature lookup is turned off on this server."}, False
    names = list(dict.fromkeys(search_name(n) for n in names if n))[:4]
    if not names:
        return base, True
    terms = [_term(n.replace(",", " ")) for n in names]
    term = terms[0] if len(terms) == 1 else "(" + " OR ".join(terms) + ")"
    params = {
        "filter": f"title_and_abstract.search:{term},type:article|review,primary_topic.field.id:{FIELDS},"
                  f"primary_location.source.id:!{CHEMRXIV_SOURCE}",
        "sort": "relevance_score:desc", "per_page": str(FETCH), "mailto": MAILTO,
        "select": "doi,title,authorships,publication_year,publication_date,cited_by_count,type,primary_location,"
                  "open_access,abstract_inverted_index,is_retracted",
    }
    key = os.environ.get("OPENALEX_API_KEY")
    if key:
        params["api_key"] = key
    try:
        with httpx.Client(timeout=_timeout(), follow_redirects=True) as client:
            r = client.get(OPENALEX, params=params)
    except httpx.HTTPError:
        r = None
    if r is None or r.status_code != 200:
        return {**base, "available": False, "query": names[0], "reason": "OpenAlex is not reachable right now."}, False
    data = r.json()
    items = [it for it in (_item(w, names) for w in data.get("results", [])) if it]
    return {**base, "items": items, "total": (data.get("meta") or {}).get("count") or len(items), "query": names[0]}, True
