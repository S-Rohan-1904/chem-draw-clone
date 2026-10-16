"""Articles that mention a molecule anywhere in the text, from Europe PMC's chemical tagging.

Europe PMC text-mines abstracts and open-access full texts and tags every
chemical it recognises with its ChEBI entry, so this finds papers that use a
compound in passing (a reagent, a solvent, a ligand) without naming it in the
title. The structure is matched exactly: InChIKey to ChEBI id through UniChem,
then the ChEBI name, which Europe PMC indexes the tags under. Only molecules
in ChEBI (about 200,000, the common ones) can be found this way. Never raises.
"""

from __future__ import annotations

import httpx

from .literature import MAILTO, _timeout, enabled
from .literature_journals import _europepmc, _request

UNICHEM = "https://www.ebi.ac.uk/unichem/api/v1/compounds"
OLS = "https://www.ebi.ac.uk/ols4/api/ontologies/chebi/terms"
VERSION = 1
FETCH = 25


def chebi(client: httpx.Client, key: str) -> tuple[str, str] | None:
    """(ChEBI id, ChEBI name) for an InChIKey, ("", "") when ChEBI has no entry, None when a service failed."""
    r = _request(client, "POST", UNICHEM, json={"type": "inchikey", "compound": key})
    if r.status_code == 404:
        return "", ""
    if r.status_code != 200:
        return None
    compounds = r.json().get("compounds") or [{}]
    ids = [s["compoundId"] for s in compounds[0].get("sources", []) if s.get("shortName") == "chebi" and s.get("compoundId")]
    if not ids:
        return "", ""
    chebi_id = ids[0] if str(ids[0]).startswith("CHEBI:") else f"CHEBI:{ids[0]}"
    r = _request(client, "GET", OLS, params={"obo_id": chebi_id})
    if r.status_code != 200:
        return None
    terms = (r.json().get("_embedded") or {}).get("terms") or []
    return chebi_id, (terms[0].get("label") or "") if terms else ""


def search(key: str) -> tuple[dict, bool]:
    """(payload, complete) for an InChIKey; incomplete means a service failed and the result should not be cached."""
    base = {"available": True, "items": [], "total": 0, "chebi": "", "query": "", "_v": VERSION}
    if not enabled():
        return {**base, "available": False, "reason": "Literature lookup is turned off on this server."}, False
    if not key:
        return base, True
    try:
        with httpx.Client(timeout=_timeout() * 2, follow_redirects=True, headers={"User-Agent": f"Chem Illustrator (mailto:{MAILTO})"}) as client:
            found = chebi(client, key)
            if found is None:
                return {**base, "available": False, "reason": "ChEBI is not reachable right now."}, False
            chebi_id, name = found
            if not name:
                return base, True
            items = _europepmc(client, f'CHEBITERM:"{name}"', FETCH)
    except (httpx.HTTPError, ValueError):
        items = None
    if items is None:
        return {**base, "available": False, "reason": "Europe PMC is not reachable right now."}, False
    for it in items:
        it["match"] = "text"
    return {**base, "items": items, "chebi": chebi_id, "query": name}, True
