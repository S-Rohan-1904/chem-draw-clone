"""Recorded reactions for a molecule, from the prebuilt reaction index.

reactions.db is built offline by scripts/build_reactions.py from Daniel
Lowe's text-mined US patent reactions (1976-Sep 2016, CC0), the Chemical
Reaction Database (CC BY 4.0) and Rhea enzyme reactions (CC BY 4.0). For
each molecule it holds up to five reaction types in each direction, "uses"
(the molecule is a reactant) and "makes" (it is the product), ranked by how
many distinct reactions show that type, each with one real example. Enzyme
reactions are ranked in a group of their own. Indexes built before the extra
sources (no source column) still work.

The lookup is by InChIKey; when a molecule with stereocentres has no entry
for its exact stereoisomer, other stereoisomers of the same skeleton (first
InChIKey block, same protonation) are used and the result says so.
"""

from __future__ import annotations

import os
import re
import sqlite3
from functools import lru_cache
from pathlib import Path

from rdkit import Chem

from . import reaction
from .chem import mol_from_smiles

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "reactions.db"
# Largest molecule the index covers, in heavy atoms (scripts/build_reactions.py MAX_PRODUCT_ATOMS).
MAX_ATOMS = 60
SOURCES = {
    "uspto": {
        "name": "Chemical reactions from US patents (1976 to Sep 2016)",
        "author": "Daniel Lowe",
        "url": "https://doi.org/10.6084/m9.figshare.5104873",
        "licence": "CC0",
    },
    "crd": {
        "name": "Chemical Reaction Database",
        "author": "Rik van der Lingen",
        "url": "https://doi.org/10.5281/zenodo.18109268",
        "licence": "CC BY 4.0",
    },
    "rhea": {
        "name": "Rhea, the reaction knowledgebase",
        "author": "SIB Swiss Institute of Bioinformatics",
        "url": "https://www.rhea-db.org",
        "licence": "CC BY 4.0",
    },
}


def db_path() -> Path:
    return Path(os.environ.get("CHEM_REACTIONS_DB", str(DEFAULT_PATH)))


@lru_cache(maxsize=1)
def _connect(path: str) -> sqlite3.Connection | None:
    if not Path(path).exists():
        return None
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def available() -> bool:
    return _connect(str(db_path())) is not None


@lru_cache(maxsize=4)
def _schema(path: str) -> tuple[bool, list[str]]:
    """(has source columns, sources in the index)."""
    con = _connect(path)
    cols = {r["name"] for r in con.execute("PRAGMA table_info(rxn)")}
    if "source" not in cols:
        return False, ["uspto"]
    row = con.execute("SELECT value FROM meta WHERE key = 'sources'").fetchone()
    return True, (row["value"].split(",") if row else ["uspto"])


def patent_url(patent: str) -> str:
    """Google Patents page. Lowe's numbers look like US03930836, US09450188B2 or USRE038551E1."""
    m = re.fullmatch(r"US(RE|HH|H)?0*(\d+)([A-Z]\d?)?", patent.strip().upper())
    number = f"US{m.group(1) or ''}{m.group(2)}{m.group(3) or ''}" if m else patent.strip()
    return f"https://patents.google.com/patent/{number}/en"


def reference(source: str, ref: str, extra: str = "") -> dict:
    """How the card cites an example: a label, a link, and for enzymes the EC numbers."""
    ref = (ref or "").strip()
    if source == "rhea":
        rid = ref.removeprefix("RHEA:")
        ec = [e for e in (extra or "").split() if e]
        return {"ref": ref, "ref_label": f"Rhea {rid}", "ref_url": f"https://www.rhea-db.org/rhea/{rid}", "ec": ec}
    if source == "crd":
        return {"ref": ref, "ref_label": f"CRD reaction {ref}", "ref_url": SOURCES["crd"]["url"], "ec": []}
    return {"ref": ref, "ref_label": ref, "ref_url": patent_url(ref) if ref else "", "ec": []}


def _highlight(query_smiles: str, centre: str, mol: Chem.Mol) -> list[int]:
    """Map the stored reacting atoms (positions in the stored SMILES) onto the user's molecule."""
    if not centre:
        return []
    stored = Chem.MolFromSmiles(query_smiles)
    if stored is None:
        return []
    match = mol.GetSubstructMatch(stored, useChirality=False)
    if not match:
        return []
    out = []
    for p in centre.split(","):
        i = int(p)
        if 0 <= i < len(match):
            out.append(match[i])
    return sorted(set(out))


def _item(row: sqlite3.Row, query_smiles: str, mol: Chem.Mol, draw: bool = True) -> dict:
    reactants, agents, products = row["smiles"].split(">")
    mols = [[Chem.MolFromSmiles(s) for s in side.split(".") if s] for side in (reactants, agents, products)] if draw else []
    svg = ""
    if draw and all(m is not None for side in mols for m in side):
        try:
            svg = reaction.draw_reaction(*mols)
        except Exception:  # noqa: BLE001 - a drawing failure should not hide the entry
            svg = ""
    return {
        "label": row["label"].replace("–", "-"),  # en dash in bond labels (C–N) shown as a hyphen
        "count": row["count"],
        "smiles": row["smiles"],
        "reactants": [s for s in reactants.split(".") if s],
        "agents": [s for s in agents.split(".") if s],
        "products": [s for s in products.split(".") if s],
        "source": row["source"],
        **reference(row["source"], row["ref"], row["extra"]),
        "year": row["year"] or None,
        "yield": row["yield"],
        "svg": svg,
        "atoms": _highlight(query_smiles, row["centre"] or "", mol),
    }


_QUERY = """
    SELECT m.smiles AS query_smiles, t.label, t.count, t.centre, r.smiles, r.source, r.ref, r.year, r.yield, r.extra
    FROM mol m JOIN top t ON t.mol_id = m.id JOIN rxn r ON r.id = t.rxn_id
    WHERE m.{column} = ? AND substr(m.inchikey, 27, 1) = ? AND t.direction = ? AND t.grp = ?
    ORDER BY t.count DESC, t.rank
"""
# Indexes built from USPTO alone: no source columns, no groups.
_QUERY_V1 = """
    SELECT m.smiles AS query_smiles, t.label, t.count, t.centre, r.smiles, 'uspto' AS source, r.patent AS ref,
           r.year, r.yield, '' AS extra
    FROM mol m JOIN top t ON t.mol_id = m.id JOIN rxn r ON r.id = t.rxn_id
    WHERE m.{column} = ? AND substr(m.inchikey, 27, 1) = ? AND t.direction = ? AND ? = 'chem'
    ORDER BY t.count DESC, t.rank
"""
GROUPS = {"chem": ("uses", "makes"), "enzyme": ("enzyme_uses", "enzyme_makes")}


def lookup(smiles: str, limit: int = 5, draw: bool = True) -> dict:
    mol = mol_from_smiles(smiles)
    path = str(db_path())
    con = _connect(path)
    empty = {"uses": [], "makes": [], "enzyme_uses": [], "enzyme_makes": [], "stereo_ignored": False}
    if con is None:
        return {"available": False, **empty, "sources": [SOURCES["uspto"]]}
    has_source, used = _schema(path)
    sources = [SOURCES[k] for k in used if k in SOURCES]
    query = _QUERY if has_source else _QUERY_V1
    key = Chem.MolToInchiKey(mol)
    if not key:
        return {"available": True, **empty, "sources": sources}

    def fetch(column: str, value: str, direction: str, group: str) -> list[dict]:
        # The last InChIKey letter is the protonation state: pyridine and pyridinium share a skeleton.
        rows = con.execute(query.format(column=column), (value, key[-1], direction, group)).fetchall()
        items: list[dict] = []
        seen: set[str] = set()
        # Several stereoisomers can share a skeleton: merge by label, keep the most common example.
        for row in rows:
            if row["label"] in seen:
                continue
            seen.add(row["label"])
            items.append(_item(row, row["query_smiles"], mol, draw))
            if len(items) == limit:
                break
        return items

    result: dict[str, list[dict]] = {}
    stereo_ignored = False
    for group, fields in GROUPS.items():
        for direction, field in zip(("uses", "makes"), fields):
            items = fetch("inchikey", key, direction, group)
            if not items and key[15:25] != "UHFFFAOYSA":
                # No record for this exact stereoisomer: fall back to any stereoisomer of the same skeleton.
                items = fetch("skeleton", key[:14], direction, group)
                stereo_ignored = stereo_ignored or bool(items)
            result[field] = items
    return {"available": True, **result, "stereo_ignored": stereo_ignored, "sources": sources,
            "heavy_atoms": mol.GetNumHeavyAtoms(), "max_atoms": MAX_ATOMS}
