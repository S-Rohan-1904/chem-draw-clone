"""ChemRxiv preprints that mention a molecule, searched by name.

ChemRxiv's own API sits behind a browser challenge and refuses server
requests, so the search goes through OpenAlex (titles and abstracts,
ranked by relevance, filtered to the ChemRxiv source) and falls back to
Crossref (titles only, filtered to ChemRxiv's DOI prefix 10.26434) when
OpenAlex fails or its free daily budget is spent. Never raises.
"""

from __future__ import annotations

import os
import re

import httpx

OPENALEX = "https://api.openalex.org/works"
CROSSREF = "https://api.crossref.org/works"
CHEMRXIV_SOURCE = "S4393918830"  # OpenAlex source id for ChemRxiv
CHEMRXIV_PREFIX = "10.26434"
MAILTO = "chem-forge@users.noreply.github.com"
LIMIT = 5


def enabled() -> bool:
    return os.environ.get("CHEM_LITERATURE_LOOKUP", "1") not in ("0", "false", "no")


def _timeout() -> float:
    return float(os.environ.get("CHEM_LOOKUP_TIMEOUT", "6"))


def chemrxiv_url(doi: str) -> str:
    """The article page on ChemRxiv (the URL ChemRxiv registers with Crossref)."""
    if doi.lower().startswith(CHEMRXIV_PREFIX + "/"):
        return f"https://chemrxiv.org/doi/full/{doi}"
    return f"https://doi.org/{doi}"


def _bare_doi(doi: str | None) -> str:
    doi = doi or ""
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.lower().startswith(prefix):
            return doi[len(prefix):]
    return doi


def _authors(names: list[str]) -> str:
    names = [n for n in names if n]
    if len(names) > 3:
        return ", ".join(names[:3]) + " et al."
    return ", ".join(names)


# Leading stereo and optical-rotation descriptors: (R)-, (2R,3S)-, (-)-, (+/-)-, (E)-, cis-, D-, L-, rac-.
_STEREO_PREFIX = re.compile(r"^(?:\((?:[0-9]*[RSEZrs](?:,\s*[0-9]*[RSEZrs])*|[+-]|\+/-|\u00b1)\)|cis|trans|rac|meso|[DL])-", re.I)


def search_name(name: str) -> str:
    """The name to search for: stereo prefixes dropped, since papers rarely use them."""
    name = name.strip().replace('"', "")
    while True:
        stripped = _STEREO_PREFIX.sub("", name, count=1)
        if stripped == name or not stripped:
            return name
        name = stripped


def _term(name: str) -> str:
    """Quote multi-word names so they are searched as a phrase."""
    return f'"{name}"' if any(c in name for c in " -,()[]") else name


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _dedupe(items: list[dict]) -> list[dict]:
    """One row per preprint: versions (.v1, .v2) and repeated titles collapse."""
    seen: set[str] = set()
    out = []
    for it in items:
        keys = {re.sub(r"\.v\d+$", "", it["doi"].lower()), it["title"].strip().lower()}
        if keys & seen:
            continue
        seen |= keys
        out.append(it)
    return out


def _openalex(client: httpx.Client, name: str) -> list[dict] | None:
    params = {
        # Commas separate OpenAlex filters, so they cannot appear inside the term.
        "filter": f"primary_location.source.id:{CHEMRXIV_SOURCE},title_and_abstract.search:{_term(name.replace(',', ' '))}",
        "sort": "relevance_score:desc",
        "per_page": str(LIMIT * 2),
        "mailto": MAILTO,
    }
    key = os.environ.get("OPENALEX_API_KEY")
    if key:
        params["api_key"] = key
    r = client.get(OPENALEX, params=params)
    if r.status_code != 200:
        return None
    items = []
    for w in r.json().get("results", []):
        doi = _bare_doi(w.get("doi"))
        if not doi or not w.get("title"):
            continue
        items.append({
            "title": w["title"],
            "authors": _authors([(a.get("author") or {}).get("display_name", "") for a in w.get("authorships") or []]),
            "date": w.get("publication_date") or "",
            "doi": doi,
            "url": chemrxiv_url(doi),
            "cited_by": w.get("cited_by_count"),
        })
    return items


def _crossref(client: httpx.Client, name: str) -> list[dict] | None:
    params = {
        "query.bibliographic": name,
        "filter": f"prefix:{CHEMRXIV_PREFIX}",
        "rows": str(LIMIT * 2),
        "select": "DOI,title,author,posted,created",
        "mailto": MAILTO,
    }
    r = client.get(CROSSREF, params=params)
    if r.status_code != 200:
        return None
    items = []
    wanted = _squash(name)
    for w in r.json().get("message", {}).get("items", []):
        doi = w.get("DOI", "")
        title = (w.get("title") or [""])[0]
        # Crossref ranks loosely ("2-butanol" finds n-butanol papers): keep titles that name the molecule.
        if not doi or not title or wanted not in _squash(title):
            continue
        parts = ((w.get("posted") or w.get("created") or {}).get("date-parts") or [[]])[0]
        date = "-".join(f"{p:02d}" if i else str(p) for i, p in enumerate(parts))
        items.append({
            "title": title,
            "authors": _authors([" ".join(x for x in (a.get("given"), a.get("family")) if x) for a in w.get("author") or []]),
            "date": date,
            "doi": doi,
            "url": chemrxiv_url(doi),
            "cited_by": None,
        })
    return items


def search(name: str) -> tuple[dict, bool]:
    """(payload, complete). Incomplete means both services failed: do not cache."""
    name = search_name(name)
    base = {"available": True, "query": name, "items": [], "source": ""}
    if not enabled():
        return {**base, "available": False, "reason": "Literature lookup is turned off on this server."}, False
    try:
        with httpx.Client(timeout=_timeout(), follow_redirects=True, headers={"User-Agent": f"Chem Forge (mailto:{MAILTO})"}) as client:
            for label, fn in (("OpenAlex", _openalex), ("Crossref", _crossref)):
                try:
                    items = fn(client, name)
                except (httpx.HTTPError, ValueError):
                    items = None
                if items is not None:
                    return {**base, "items": _dedupe(items)[:LIMIT], "source": label}, True
    except Exception:  # noqa: BLE001 - best effort
        pass
    return {**base, "available": False, "reason": "ChemRxiv search is not reachable right now."}, False
