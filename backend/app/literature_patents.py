"""Patents that show the chemistry of a molecule.

The patents come from the reaction index: the US patents whose examples make
or use the molecule (the examples on the Reactions card). Titles, dates and
assignees are read from PubChem's patent records. PubChem links far more
patents to most compounds (often tens of thousands, in no useful order), so
those are left to a link to the compound's PubChem page. Never raises.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

import httpx

from .literature import MAILTO, _timeout, enabled
from .reactiondb import patent_url

PUBCHEM_PATENT = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/patent/{}/JSON"
VERSION = 1


def pubchem_ids(number: str) -> list[str]:
    """PubChem ids to try for one of Lowe's patent numbers: US03930836 -> US-3930836-A,
    US09450188B2 -> US-9450188-B2, USRE038551E1 -> US-RE38551-E1 then US-RE38551-E."""
    m = re.fullmatch(r"US(RE|HH|H)?0*(\d+)([A-Z]\d?)?", number.strip().upper())
    if not m:
        return []
    body = f"{m.group(1) or ''}{m.group(2)}"
    kind = m.group(3) or "A"
    ids = [f"US-{body}-{kind}"]
    if len(kind) == 2:
        ids.append(f"US-{body}-{kind[0]}")
    return ids


def _strings(section: dict) -> list[str]:
    out = []
    for info in section.get("Information", []):
        v = info.get("Value", {})
        out += [s.get("String", "") for s in v.get("StringWithMarkup", [])]
        out += v.get("DateISO8601", [])
    return [s for s in out if s]


def _record(client: httpx.Client, number: str) -> dict | None:
    """Title, date and assignee from PubChem, or None when PubChem has no record."""
    for pid in pubchem_ids(number):
        r = client.get(PUBCHEM_PATENT.format(pid))
        if r.status_code == 404:
            continue
        r.raise_for_status()
        rec = r.json().get("Record", {})
        fields: dict[str, list[str]] = {}

        def walk(sections: list[dict]) -> None:
            for s in sections:
                fields.setdefault(s.get("TOCHeading", ""), _strings(s))
                walk(s.get("Section", []))

        walk(rec.get("Section", []))
        date = (fields.get("Publication Date") or fields.get("Grant Date") or [""])[0].replace("/", "-")
        return {"title": rec.get("RecordTitle", ""), "date": date, "assignee": ", ".join(fields.get("Assignee", [])[:2])}
    return None


def search(reactions: dict, cid: int | None) -> tuple[dict, bool]:
    """(payload, complete). `reactions` is reactiondb.lookup() for the molecule."""
    base = {"available": True, "items": [], "cid": cid, "_v": VERSION,
            "pubchem_url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}#section=Patents" if cid else ""}
    by_number: dict[str, dict] = {}
    for direction in ("uses", "makes"):
        for r in reactions.get(direction, []):
            if r.get("source") != "uspto" or not r.get("ref"):
                continue
            entry = by_number.setdefault(r["ref"], {
                "number": r["ref"], "url": patent_url(r["ref"]), "year": r.get("year"), "title": "", "date": "",
                "assignee": "", "reactions": [],
            })
            entry["reactions"].append({"direction": direction, "label": r["label"]})
    items = list(by_number.values())
    if not items or not enabled():
        return {**base, "items": items}, True
    complete = True

    def fill(item: dict) -> None:
        nonlocal complete
        try:
            with httpx.Client(timeout=_timeout(), follow_redirects=True, headers={"User-Agent": f"Chem Forge (mailto:{MAILTO})"}) as client:
                rec = _record(client, item["number"])
        except (httpx.HTTPError, ValueError):
            complete = False  # titles missing: show numbers now, try again next time
            return
        if rec:
            item.update(rec)

    with ThreadPoolExecutor(4) as pool:  # PubChem allows 5 requests a second
        list(pool.map(fill, items))
    items.sort(key=lambda it: -(it["year"] or 0))
    return {**base, "items": items}, complete
