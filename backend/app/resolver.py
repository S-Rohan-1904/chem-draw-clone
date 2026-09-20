"""Name-to-structure lookup for names OPSIN cannot parse.

OPSIN only understands systematic nomenclature. Trivial and trade names
(protoporphyrin IX, hemin, aspirin) are labels, not descriptions, so they are
looked up in PubChem and then NCI CACTUS. Results go into the name cache like
any other name, so the network is hit once per name.
"""

from __future__ import annotations

import os
import re
from urllib.parse import quote

import httpx
from rdkit import Chem

PUBCHEM = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{}/property/IsomericSMILES,ConnectivitySMILES/JSON"
CACTUS = "https://cactus.nci.nih.gov/chemical/structure/{}/smiles"

MAX_NAME_LEN = 200


def enabled() -> bool:
    return os.environ.get("CHEM_NAME_LOOKUP", "1") not in ("0", "false", "no")


def _timeout() -> float:
    return float(os.environ.get("CHEM_LOOKUP_TIMEOUT", "6"))


def _valid(smiles: str) -> bool:
    return bool(smiles) and Chem.MolFromSmiles(smiles) is not None


def _pubchem(client: httpx.Client, name: str) -> tuple[str, str] | None:
    r = client.get(PUBCHEM.format(quote(name, safe="")))
    if r.status_code != 200:
        return None
    props = r.json().get("PropertyTable", {}).get("Properties", [])
    for p in props:
        smiles = p.get("SMILES") or p.get("IsomericSMILES") or p.get("ConnectivitySMILES") or ""
        if _valid(smiles):
            return smiles, f"PubChem CID {p.get('CID')}"
    return None


def _cactus(client: httpx.Client, name: str) -> tuple[str, str] | None:
    r = client.get(CACTUS.format(quote(name, safe="")))
    if r.status_code != 200:
        return None
    smiles = r.text.strip().splitlines()[0].strip() if r.text.strip() else ""
    if _valid(smiles):
        return smiles, "NCI CACTUS"
    return None


_SOURCES = (("pubchem", _pubchem), ("cactus", _cactus))


def lookup(name: str) -> tuple[str, str, str] | None:
    """Return (smiles, source, note) or None. Never raises."""
    name = name.strip()
    if not enabled() or not name or len(name) > MAX_NAME_LEN or "\n" in name:
        return None
    if not re.search(r"[A-Za-z]{3}", name):  # nothing name-like to look up
        return None
    try:
        with httpx.Client(timeout=_timeout(), follow_redirects=True) as client:
            for source, fn in _SOURCES:
                try:
                    hit = fn(client, name)
                except (httpx.HTTPError, ValueError):
                    continue
                if hit:
                    smiles, record = hit
                    note = f"'{name}' is not a systematic IUPAC name; structure taken from {record}."
                    return smiles, source, note
    except Exception:  # noqa: BLE001 - lookup is best effort
        return None
    return None
