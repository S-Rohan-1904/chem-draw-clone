"""Patents of every year and country that contain a molecule, from SureChEMBL.

SureChEMBL (EMBL-EBI) text-mines and image-mines chemical structures from the
full text of patents worldwide and keeps them up to date, so it covers what the
reaction index cannot: patents after 2016 and outside the US. The molecule is
looked up by SMILES; its documents come oldest first, so the newest two pages are
ranked here (titles naming the compound first, then titles about making it,
then the main patent offices, then the highest numbers, usually the newest), and
the dates and assignees of the ones shown are read with one content search. Never raises.
"""

from __future__ import annotations

import re

import httpx

from .literature import MAILTO, _timeout, enabled, names_it

SURECHEMBL = "https://www.surechembl.org/api"
VERSION = 2
PAGE = 100  # documents per page; the newest two pages are ranked
KEEP = 15
OFFICES = {"US": 3, "EP": 3, "WO": 3, "GB": 1, "JP": 1, "CN": 1, "KR": 1, "DE": 1}
_MAKING = re.compile(r"\b(prepar\w*|synthe\w*|process(es)? for|method(s)? (of|for) (producing|making|manufactur\w*)|manufactur\w*|production of)\b", re.I)


def doc_url(doc_id: str) -> str:
    """Google Patents page for a SureChEMBL id such as US-9450188-B2 or WO-2015123456-A1."""
    return f"https://patents.google.com/patent/{doc_id.replace('-', '')}/en"


def _rank(doc: dict, names: list[str]) -> tuple:
    country = doc["number"].split("-")[0]
    return (names_it(doc["title"], names), doc["making"], OFFICES.get(country, 0), doc["number"])


def _post(client: httpx.Client, path: str, **params) -> dict | None:
    r = client.post(f"{SURECHEMBL}{path}", params=params)
    if r.status_code != 200:
        return None
    body = r.json()
    return body.get("data") if body.get("status") == "OK" else None


def _chemical_id(client: httpx.Client, smiles: str) -> str | None:
    """SureChEMBL's id for the structure, "" when it has none, None when the service failed."""
    data = _post(client, "/chemical/smiles/", smiles=smiles)
    if data is None:
        return None
    hit = next(iter(data.values()), None) if isinstance(data, dict) else None
    return str((hit or {}).get("chemical_id") or "")


def search(smiles: str, plain_smiles: str = "", names: list[str] | None = None) -> tuple[dict, bool]:
    """(payload, complete). `plain_smiles` (without stereo) is tried when the exact structure is not known,
    since many patents draw the compound without stereo. Titles naming one of `names` rank first."""
    base = {"available": True, "items": [], "total": 0, "chemical_id": "", "_v": VERSION}
    if not enabled():
        return {**base, "available": False, "reason": "Literature lookup is turned off on this server."}, False
    down = {**base, "available": False, "reason": "SureChEMBL is not reachable right now."}
    try:
        with httpx.Client(timeout=_timeout() * 3, follow_redirects=True, headers={"User-Agent": f"Chem Illustrator (mailto:{MAILTO})"}) as client:
            chem_id = _chemical_id(client, smiles)
            if chem_id == "" and plain_smiles and plain_smiles != smiles:
                chem_id = _chemical_id(client, plain_smiles)
            if chem_id is None:
                return down, False
            if not chem_id:
                return base, True
            data = _post(client, "/search/documents_for_structures", chemicalIds=chem_id, page=1, itemsPerPage=PAGE)
            if data is None:
                return down, False
            results = data.get("results") or {}
            found = list(results.get("documents", []))
            # Documents come in the order SureChEMBL indexed them, oldest first; the reaction index already
            # has the old US ones, so rank the newest two pages instead.
            last = -(-(results.get("total_hits") or 0) // PAGE)
            if last > 1:
                newest = [_post(client, "/search/documents_for_structures", chemicalIds=chem_id, page=p, itemsPerPage=PAGE)
                          for p in sorted({max(last - 1, 2), last})]
                if any(n is None for n in newest):
                    return down, False
                found = [d for n in newest for d in (n.get("results") or {}).get("documents", [])]
            docs = []
            for d in found:
                titles = ((d.get("metadata") or {}).get("titles") or [])
                english = next((t["titles"][0] for t in titles if t.get("lang") == "en" and t.get("titles")), "")
                if d.get("docId") and all(x["number"] != d["docId"] for x in docs):  # pages can shift while SureChEMBL indexes
                    docs.append({"number": d["docId"], "title": english, "url": doc_url(d["docId"]), "date": "", "year": None,
                                 "assignee": "", "making": bool(_MAKING.search(english)), "source": "SureChEMBL"})
            docs.sort(key=lambda d: _rank(d, names or []), reverse=True)
            docs = docs[:KEEP]
            if docs:
                query = "pn:(" + " OR ".join(f'"{d["number"]}"' for d in docs) + ")"
                found = _post(client, "/search/content", query=query, page=1, itemsPerPage=len(docs))
                for hit in ((found or {}).get("results") or {}).get("documents", []):
                    pd = ((hit.get("metadata") or {}).get("pd") or "")
                    for d in docs:
                        if d["number"] == hit.get("docId") and re.fullmatch(r"\d{8}", pd):
                            d["date"], d["year"] = f"{pd[:4]}-{pd[4:6]}-{pd[6:]}", int(pd[:4])
                            d["assignee"] = (hit.get("pa") or "").title() if hit.get("pa") not in (None, "null") else ""
    except (httpx.HTTPError, ValueError):
        return down, False
    return {**base, "items": docs, "total": results.get("total_hits") or len(docs), "chemical_id": chem_id}, True
