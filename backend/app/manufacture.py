"""How a molecule is made industrially or in the lab, from PubChem.

PubChem's "Methods of Manufacturing" section comes from the Hazardous
Substances Data Bank (HSDB, U.S. National Library of Medicine), which covers
the simple and industrial chemicals that patents buy rather than make, the
molecules the reaction index is weakest on. Each method is short text with
its literature reference; compounds named in it carry PubChem links, which
the card turns into buttons that open them. When the exact stereoisomer has
no entry, the compound without stereochemistry is tried. Never raises.
"""

from __future__ import annotations

import httpx

from .literature import MAILTO, _timeout, enabled

PUBCHEM_VIEW = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{}/JSON?heading=Methods+of+Manufacturing"
PUBCHEM_CIDS = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/inchikey/{}/cids/JSON"
SECTION_URL = "https://pubchem.ncbi.nlm.nih.gov/compound/{}#section=Methods-of-Manufacturing"
HSDB_URL = "https://pubchem.ncbi.nlm.nih.gov/source/11933"
MAX_METHODS = 6
MAX_CHARS = 420
VERSION = 1


def _clip(text: str) -> tuple[str, int]:
    """Text cut at a word near MAX_CHARS, and how many characters were kept."""
    if len(text) <= MAX_CHARS:
        return text, len(text)
    cut = text.rfind(" ", 0, MAX_CHARS)
    cut = cut if cut > MAX_CHARS // 2 else MAX_CHARS
    return text[:cut].rstrip(" ,.;") + "…", cut


def methods_from_record(record: dict, cid: int | None = None) -> list[dict]:
    """[{text, compounds: [{start, length, name}], reference}] from a PUG View record."""
    out: list[dict] = []
    seen: set[str] = set()

    def walk(sections: list[dict]) -> None:
        for s in sections:
            if s.get("TOCHeading") == "Methods of Manufacturing":
                for info in s.get("Information", []):
                    for part in info.get("Value", {}).get("StringWithMarkup", []):
                        raw = part.get("String", "")  # unchanged: the markup offsets point into it
                        # Pointers to the full HSDB record are not methods.
                        if not raw.strip() or raw.lower().startswith("for more methods of manufacturing"):
                            continue
                        key = raw.lower()[:80]
                        if key in seen:
                            continue
                        seen.add(key)
                        text, kept = _clip(raw)
                        compounds = []
                        for m in part.get("Markup", []):
                            start, length = m.get("Start", -1), m.get("Length", 0)
                            if m.get("Type") != "PubChem Internal Link" or start < 0 or start + length > kept:
                                continue
                            if cid and m.get("Extra") == f"CID-{cid}":
                                continue  # the molecule itself
                            compounds.append({"start": start, "length": length, "name": raw[start:start + length]})
                        out.append({"text": text, "compounds": compounds, "reference": "; ".join(info.get("Reference", []))[:300]})
            walk(s.get("Section", []))

    walk(record.get("Section", []))
    return out[:MAX_METHODS]


def _fetch(client: httpx.Client, cid: int) -> list[dict] | None:
    r = client.get(PUBCHEM_VIEW.format(cid))
    if r.status_code == 404:
        return []
    r.raise_for_status()
    return methods_from_record(r.json().get("Record", {}), cid)


def search(cid: int | None, inchikey: str) -> tuple[dict, bool]:
    """(payload, complete); incomplete means PubChem failed and the result should not be cached."""
    base = {"available": True, "methods": [], "cid": None, "stereo_ignored": False, "url": "", "source_url": HSDB_URL, "_v": VERSION}
    if not enabled():
        return {**base, "available": False}, False
    try:
        with httpx.Client(timeout=_timeout(), follow_redirects=True, headers={"User-Agent": f"Chem Illustrator (mailto:{MAILTO})"}) as client:
            methods = _fetch(client, cid) if cid else []
            used, stereo_ignored = cid, False
            if not methods and inchikey and inchikey[15:25] != "UHFFFAOYSA":
                # A stereoisomer: HSDB describes the compound, usually as the racemate or mixture.
                r = client.get(PUBCHEM_CIDS.format(inchikey[:14]))
                cids = r.json().get("IdentifierList", {}).get("CID", []) if r.status_code == 200 else []
                for other in sorted(c for c in cids if c != cid)[:3]:
                    methods = _fetch(client, other)
                    if methods:
                        used, stereo_ignored = other, True
                        break
    except (httpx.HTTPError, ValueError):
        return {**base, "available": False}, False
    if not methods:
        return base, True
    return {**base, "methods": methods, "cid": used, "stereo_ignored": stereo_ignored, "url": SECTION_URL.format(used)}, True
