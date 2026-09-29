"""Recorded reactions for a molecule, from the prebuilt reaction index.

reactions.db is built offline by scripts/build_reactions.py from Daniel
Lowe's text-mined US patent reactions (1976-Sep 2016, CC0), the Chemical
Reaction Database (CC BY 4.0), Rhea enzyme reactions (CC BY 4.0) and the
equations written in Wikipedia compound articles (CC BY-SA 4.0). For
each molecule it holds up to five reaction types in each direction, "uses"
(the molecule is a reactant) and "makes" (it is the product), ranked by how
many distinct reactions show that type, each with one real example. Enzyme
reactions and Wikipedia's textbook equations are ranked in groups of their own. Indexes built before the extra
sources (no source column) still work.

The lookup is by structure without stereochemistry (first InChIKey block, same
protonation): every stereoisomer's reactions are pooled, the exact stereoisomer's
example is preferred, and each item says when its example is another
stereoisomer's. Records rarely hold the stereoisomer a student draws, and the
reaction types are the same.
"""

from __future__ import annotations

import os
import re
import sqlite3
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

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
    "wiki": {
        "name": "Equations in chemical compound articles",
        "author": "Wikipedia contributors",
        "url": "https://en.wikipedia.org/wiki/Wikipedia:Copyrights",
        "licence": "CC BY-SA 4.0",
    },
    "hsdb": {
        "name": "Hazardous Substances Data Bank, Methods of Manufacturing",
        "author": "U.S. National Library of Medicine, via PubChem",
        "url": "https://pubchem.ncbi.nlm.nih.gov/source/11933",
        "licence": "U.S. government work",
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
    detail = (extra or "").rpartition("|")[0] if "|" in (extra or "") else (extra or "")
    if source == "wiki":
        title = ref.partition("#")[0]
        url = f"https://en.wikipedia.org/w/index.php?title={quote(title.replace(' ', '_'))}"
        if detail.strip().isdigit():
            url += f"&oldid={detail.strip()}"
        return {"ref": title, "ref_label": f"Wikipedia: {title}", "ref_url": url, "ec": []}
    if source == "hsdb":
        cid = ref.partition("#")[0]
        cited = detail.split(";")[0].strip()
        label = f"PubChem CID {cid}" + (f", citing {cited[:80]}" if cited else "")
        return {"ref": cid, "ref_label": label, "ec": [],
                "ref_url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}#section=Methods-of-Manufacturing"}
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
    SELECT m.inchikey, m.smiles AS query_smiles, t.label, t.count, t.rank, t.centre, r.smiles, r.source, r.ref, r.year,
           r.yield, r.extra
    FROM mol m JOIN top t ON t.mol_id = m.id JOIN rxn r ON r.id = t.rxn_id
    WHERE m.{column} = ? AND substr(m.inchikey, 27, 1) = ? AND t.direction = ? AND t.grp = ?
    ORDER BY t.count DESC, t.rank
"""
# Indexes built from USPTO alone: no source columns, no groups.
_QUERY_V1 = """
    SELECT m.inchikey, m.smiles AS query_smiles, t.label, t.count, t.rank, t.centre, r.smiles, 'uspto' AS source,
           r.patent AS ref, r.year, r.yield, '' AS extra
    FROM mol m JOIN top t ON t.mol_id = m.id JOIN rxn r ON r.id = t.rxn_id
    WHERE m.{column} = ? AND substr(m.inchikey, 27, 1) = ? AND t.direction = ? AND ? = 'chem'
    ORDER BY t.count DESC, t.rank
"""
GROUPS = {"chem": ("uses", "makes"), "enzyme": ("enzyme_uses", "enzyme_makes"),
          "textbook": ("textbook_uses", "textbook_makes")}


def lookup(smiles: str, limit: int = 5, draw: bool = True) -> dict:
    mol = mol_from_smiles(smiles)
    path = str(db_path())
    con = _connect(path)
    empty = {field: [] for fields in GROUPS.values() for field in fields} | {"stereo_ignored": False}
    if con is None:
        return {"available": False, **empty, "sources": [SOURCES["uspto"]]}
    has_source, used = _schema(path)
    sources = [SOURCES[k] for k in used if k in SOURCES]
    query = _QUERY if has_source else _QUERY_V1
    key = Chem.MolToInchiKey(mol)
    if not key:
        return {"available": True, **empty, "sources": sources}

    def fetch(direction: str, group: str) -> list[dict]:
        # Every stereoisomer of the structure, and the one without stereochemistry, is looked up:
        # records rarely hold the exact stereoisomer asked for, and the chemistry is the same.
        # The last InChIKey letter is the protonation state: pyridine and pyridinium share a skeleton.
        rows = con.execute(query.format(column="skeleton"), (key[:14], key[-1], direction, group)).fetchall()
        # Merge the stereoisomers by reaction type: counts add up, and the example is the exact
        # stereoisomer's when it has one, else the most common one's.
        merged: dict[str, dict] = {}
        for row in rows:
            m = merged.setdefault(row["label"], {"count": 0, "rank": row["rank"], "row": row})
            m["count"] += row["count"]
            if m["row"]["inchikey"] != key and row["inchikey"] == key:
                m["row"], m["rank"] = row, row["rank"]
        order = sorted(merged.values(), key=lambda m: (-m["count"], m["row"]["inchikey"] != key, m["rank"]))
        items = []
        for m in order[:limit]:
            item = _item(m["row"], m["row"]["query_smiles"], mol, draw)
            item["count"] = m["count"]
            item["other_stereo"] = m["row"]["inchikey"] != key
            items.append(item)
        return items

    result: dict[str, list[dict]] = {}
    for group, fields in GROUPS.items():
        for direction, field in zip(("uses", "makes"), fields):
            result[field] = fetch(direction, group)
    stereo_ignored = any(x["other_stereo"] for items in result.values() for x in items)
    return {"available": True, **result, "stereo_ignored": stereo_ignored, "sources": sources,
            "heavy_atoms": mol.GetNumHeavyAtoms(), "max_atoms": MAX_ATOMS}
