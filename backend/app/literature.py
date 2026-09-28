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
MAX_NAMES = 6  # names tried per molecule
VERSION = 4  # bump when the payload or the search changes; older cache rows are redone
SNIPPET = 220  # characters of abstract shown around the name


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


# The same descriptors written after the name, as catalogues do: "1,2-Dimethylcyclohexane, cis-",
# "Butan-2-ol, (R)-", "Camphor, (+/-)-".
_STEREO_SUFFIX = re.compile(r",\s*(?:\([^()]*\)|cis|trans|rac|rel|meso|[DL]{1,2}|[+-]|\u00b1)-?\s*$", re.I)


def search_name(name: str) -> str:
    """The name to search for: stereo descriptors dropped, since papers rarely use them."""
    name = name.strip().replace('"', "")
    while True:
        stripped = _STEREO_SUFFIX.sub("", _STEREO_PREFIX.sub("", name, count=1)).strip()
        if stripped == name or not stripped:
            return name
        name = stripped


def _term(name: str) -> str:
    """Quote multi-word names so they are searched as a phrase."""
    return f'"{name}"' if any(c in name for c in " -,()[]") else name


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _abstract(inverted: dict | None) -> str:
    """OpenAlex stores abstracts as {word: [positions]}; put the words back in order."""
    if not inverted:
        return ""
    words: dict[int, str] = {}
    for word, positions in inverted.items():
        for p in positions:
            words[p] = word
    return " ".join(words[i] for i in sorted(words))


def snippet(text: str, name: str) -> str:
    """A stretch of the abstract around the first mention of the name, or ''."""
    at = text.lower().find(name.lower()) if name else -1
    if at < 0:
        return ""
    start = max(0, at - SNIPPET // 2)
    end = min(len(text), at + len(name) + SNIPPET // 2)
    if start > 0:
        start = text.find(" ", start) + 1 or start
    if end < len(text):
        cut = text.rfind(" ", at + len(name), end)
        end = cut if cut > 0 else end
    return ("…" if start > 0 else "") + text[start:end].strip() + ("…" if end < len(text) else "")


PUBCHEM_SYNONYMS = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{}/synonyms/JSON"


def synonyms(cid: int | None, limit: int = 3) -> list[str]:
    """PubChem's leading synonyms that read like names papers use (no CAS numbers,
    registry codes or long systematic names). Never raises."""
    if not cid or not enabled():
        return []
    try:
        with httpx.Client(timeout=_timeout(), follow_redirects=True) as client:
            r = client.get(PUBCHEM_SYNONYMS.format(cid))
            if r.status_code != 200:
                return []
            info = r.json().get("InformationList", {}).get("Information", [{}])[0]
    except (httpx.HTTPError, ValueError):
        return []
    out = []
    for syn in info.get("Synonym", [])[:30]:
        if (len(syn) > 40 or re.fullmatch(r"[\d-]+", syn) or re.search(r"\d{2,}-\d{2}-\d", syn)
                or re.fullmatch(r"[A-Z0-9 -]+", syn) or not re.search(r"[a-z]{3}", syn)):
            continue
        out.append(syn)
        if len(out) == limit:
            break
    return out


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


def _openalex(client: httpx.Client, name: str, fulltext: bool = False) -> list[dict] | None:
    if fulltext:
        # Title, abstract and body text; a plain term, since phrase quotes match nothing here.
        params = {"search": name, "filter": f"primary_location.source.id:{CHEMRXIV_SOURCE}"}
    else:
        # Commas separate OpenAlex filters, so they cannot appear inside the term.
        params = {"filter": f"primary_location.source.id:{CHEMRXIV_SOURCE},title_and_abstract.search:{_term(name.replace(',', ' '))}"}
    params.update({"sort": "relevance_score:desc", "per_page": str(LIMIT * 2), "mailto": MAILTO,
                   "select": "doi,title,authorships,publication_date,cited_by_count,abstract_inverted_index"})
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
            "snippet": snippet(_abstract(w.get("abstract_inverted_index")), name),
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
            "snippet": "",
        })
    return items


def _one(client: httpx.Client, name: str) -> tuple[list[dict] | None, str]:
    for label, fn in (("OpenAlex", _openalex), ("Crossref", _crossref)):
        try:
            items = fn(client, name)
        except (httpx.HTTPError, ValueError):
            items = None
        if items is not None:
            return _dedupe(items)[:LIMIT], label
    return None, ""


def search(names: list[str], more=None) -> tuple[dict, bool]:
    """(payload, complete). Tries each name in turn (a molecule's catalogue title
    is not always what papers call it) and stops at the first with results.
    `more()` supplies further names, fetched only if these all come back empty.
    Incomplete means the services failed: do not cache."""
    tried: list[str] = []
    base = {"available": True, "query": "", "items": [], "source": "", "_v": VERSION}
    if not enabled():
        return {**base, "available": False, "reason": "Literature lookup is turned off on this server."}, False
    failed = False
    try:
        with httpx.Client(timeout=_timeout(), follow_redirects=True, headers={"User-Agent": f"Chem Illustrator (mailto:{MAILTO})"}) as client:
            pending = list(names)
            fetched_more = False
            while pending or (more is not None and not fetched_more):
                if not pending:
                    fetched_more = True
                    pending = list(more())
                    continue
                name = search_name(pending.pop(0))
                if not name or name.lower() in (t.lower() for t in tried) or len(tried) >= MAX_NAMES:
                    continue
                tried.append(name)
                items, label = _one(client, name)
                if items is None:
                    failed = True
                    continue
                if items:
                    return {**base, "query": name, "items": items, "source": label}, True
    except Exception:  # noqa: BLE001 - best effort
        failed = True
    if not tried:
        return {**base, "available": False, "reason": "There is no name to search ChemRxiv with, because PubChem has no entry for this structure."}, True
    if failed:
        return {**base, "available": False, "query": tried[0], "reason": "ChemRxiv search is not reachable right now."}, False
    # No title or abstract names the molecule: fall back to preprints that mention it in the text.
    try:
        with httpx.Client(timeout=_timeout(), follow_redirects=True, headers={"User-Agent": f"Chem Illustrator (mailto:{MAILTO})"}) as client:
            items = _openalex(client, tried[0], fulltext=True)
    except (httpx.HTTPError, ValueError):
        items = None
    if items:
        return {**base, "query": tried[0], "items": _dedupe(items)[:LIMIT], "source": "OpenAlex", "match": "fulltext"}, True
    return {**base, "query": " / ".join(tried)}, True
