"""Journal articles ChEMBL links to a molecule's exact structure.

ChEMBL curators extract every compound from medicinal chemistry papers (J. Med.
Chem., Bioorg. Med. Chem. Lett., Eur. J. Med. Chem. and others), so these are
articles that report making or testing the molecule. The molecule is found by
InChIKey (through UniChem, much faster than ChEMBL's own structure filter), its
compound records give the documents, and the documents give
title, journal, year, DOI and PubMed id. Citation counts and open-access copies
come from Europe PMC for the articles with a PubMed id. Data CC BY-SA 4.0.
Never raises.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import httpx

from .literature import MAILTO, _timeout, enabled
from .literature_journals import _by_pmid, _request, _spread
from .literature_mentions import UNICHEM

CHEMBL = "https://www.ebi.ac.uk/chembl/api/data"
VERSION = 2
BATCH = 50  # document ids per request
MAX_DOCS = 300


def _chembl_id(client: httpx.Client, key: str) -> str | None:
    """ChEMBL's id for the InChIKey, "" when ChEMBL has none, None when both lookups failed.
    UniChem answers in about a second; ChEMBL's own structure filter takes several."""
    r = _request(client, "POST", UNICHEM, json={"type": "inchikey", "compound": key})
    if r.status_code == 404:
        return ""
    if r.status_code == 200:
        compounds = r.json().get("compounds") or [{}]
        ids = [s["compoundId"] for s in compounds[0].get("sources", []) if s.get("shortName") == "chembl" and s.get("compoundId")]
        return ids[0] if ids else ""
    r = _request(client, "GET", f"{CHEMBL}/molecule.json",
                 params={"molecule_structures__standard_inchi_key": key, "only": "molecule_chembl_id"})
    if r.status_code != 200:
        return None
    mols = r.json().get("molecules", [])
    return mols[0]["molecule_chembl_id"] if mols else ""


def _documents(client: httpx.Client, key: str) -> tuple[str, list[dict]] | None:
    """(ChEMBL id, publication records) for the InChIKey, or None when ChEMBL failed."""
    chembl_id = _chembl_id(client, key)
    if chembl_id is None:
        return None
    if not chembl_id:
        return "", []
    r = _request(client, "GET", f"{CHEMBL}/compound_record.json",
                 params={"molecule_chembl_id": chembl_id, "only": "document_chembl_id", "limit": "1000"})
    if r.status_code != 200:
        return None
    ids = sorted({c["document_chembl_id"] for c in r.json().get("compound_records", []) if c.get("document_chembl_id")},
                 key=lambda d: int(d.removeprefix("CHEMBL")) if d.removeprefix("CHEMBL").isdigit() else 0)

    def page(chunk: list[str]) -> list[dict] | None:
        r = _request(client, "GET", f"{CHEMBL}/document.json",
                     params={"document_chembl_id__in": ",".join(chunk), "limit": str(BATCH),
                             "only": "document_chembl_id,title,journal,year,doi,pubmed_id,doc_type,authors"})
        return r.json().get("documents", []) if r.status_code == 200 else None

    # Newer document ids first: a popular drug has hundreds of papers, and the newest matter most.
    ids = ids[::-1][:MAX_DOCS]
    with ThreadPoolExecutor(4) as pool:
        pages = list(pool.map(page, [ids[i:i + BATCH] for i in range(0, len(ids), BATCH)]))
    if any(p is None for p in pages):
        return None
    return chembl_id, [d for p in pages for d in p if d.get("doc_type") == "PUBLICATION" and d.get("title")]


def _from_chembl(d: dict) -> dict | None:
    doi = (d.get("doi") or "").lower()
    pmid = str(d.get("pubmed_id") or "")
    url = f"https://doi.org/{doi}" if doi else (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "")
    if not url:
        return None
    authors = [a.strip() for a in (d.get("authors") or "").split(",") if a.strip()]
    return {
        "title": d["title"].strip().removesuffix("."), "authors": ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else ""),
        "journal": d.get("journal") or "", "year": d.get("year"), "date": "", "doi": doi, "pmid": pmid, "url": url,
        "cited_by": 0, "type": "article", "oa_url": "",
    }


def search(key: str) -> tuple[dict, bool]:
    """(payload, complete) for an InChIKey; incomplete means a service failed and the result should not be cached."""
    base = {"available": True, "items": [], "total": 0, "chembl_id": "", "_v": VERSION}
    if not enabled():
        return {**base, "available": False, "reason": "Literature lookup is turned off on this server."}, False
    if not key:
        return base, True
    try:
        # ChEMBL's API is slow (a popular drug's compound records take over 10 s); the card does not wait for
        # it (literature_card.BUDGET), so give it time to finish and be cached.
        with httpx.Client(timeout=max(_timeout() * 5, 45.0), follow_redirects=True,
                          headers={"User-Agent": f"Chem Illustrator (mailto:{MAILTO})"}) as client:
            found = _documents(client, key)
            if found is None:
                return {**base, "available": False, "reason": "ChEMBL is not reachable right now."}, False
            chembl_id, docs = found
            pmids = [int(d["pubmed_id"]) for d in docs if d.get("pubmed_id")]
            detailed = _by_pmid(client, _spread(pmids)) if pmids else []
    except (httpx.HTTPError, ValueError):
        return {**base, "available": False, "reason": "ChEMBL is not reachable right now."}, False
    by_pmid = {it["pmid"]: it for it in detailed or []}
    items = []
    for d in docs:
        it = by_pmid.get(str(d.get("pubmed_id") or "")) or _from_chembl(d)
        if it:
            items.append(it)
    # Europe PMC failing only loses citation counts: keep ChEMBL's own details, but look again next time.
    return {**base, "items": items, "total": len(docs), "chembl_id": chembl_id}, detailed is not None
