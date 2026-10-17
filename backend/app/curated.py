"""Hand-reviewed textbook routes (app/data/curated_reactions.tsv).

Most teaching molecules still missing a "Made by" route are stereo-defined textbook
examples (meso-2,3-dibromobutane, cis-1,2-dimethylcyclohexane) that no patent, database
or Wikipedia sentence records. Candidate routes are drafted into a review sheet and only
rows a reviewer marked right are copied into the curated file (scripts/curated_reactions.py
accept), so nothing predicted or unreviewed reaches the card.

Two kinds of row:
- route: a reaction SMILES (reactants>agents>products) that makes product_smiles, with its
  stereochemistry, and a textbook-level reference. scripts/map_reactions.py maps these and
  scripts/build_reactions.py indexes them as their own "curated" group, which the lookup
  puts ahead of the other textbook routes.
- no_preparation: a molecule with no real preparation (3-methylhexane, spiro[4.5]decane).
  The note is shown on the card instead of "no recorded reactions"; it is read from this
  file at run time, so it needs no index rebuild.
"""

from __future__ import annotations

import csv
import os
from functools import lru_cache
from pathlib import Path

from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")

DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "curated_reactions.tsv"
FIELDS = ["id", "kind", "name", "product_smiles", "reaction_smiles", "reference", "note", "reviewed_by", "reviewed_on"]
KINDS = ("route", "no_preparation")
# Text shown on the site: colons and hyphens are fine, semicolons and long dashes are not.
BANNED = (";", "–", "—")


def path() -> Path:
    return Path(os.environ.get("CHEM_CURATED_REACTIONS", str(DEFAULT_PATH)))


def read(file: Path) -> list[dict]:
    if not file.exists():
        return []
    with open(file, encoding="utf-8", newline="") as f:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f, delimiter="\t")]


def write(file: Path, rows: list[dict]) -> None:
    with open(file, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in FIELDS})


def _key(smiles: str) -> str:
    mol = Chem.MolFromSmiles(smiles) if smiles else None
    return (Chem.MolToInchiKey(mol) or "") if mol is not None else ""


def _elements(smiles: str) -> set[str]:
    out: set[str] = set()
    for s in smiles.split("."):
        m = Chem.MolFromSmiles(s) if s else None
        if m is not None:
            out.update(a.GetSymbol() for a in m.GetAtoms())
    return out


def problems(row: dict) -> list[str]:
    """What is wrong with a curated row (an empty list when it can go in)."""
    out = []
    kind = row.get("kind", "")
    if kind not in KINDS:
        return [f"kind must be one of {', '.join(KINDS)}, not {kind!r}"]
    for field in ("id", "name", "product_smiles", "reviewed_by"):
        if not row.get(field):
            out.append(f"{field} is empty")
    for field in ("name", "reference", "note"):
        if any(b in row.get(field, "") for b in BANNED):
            out.append(f"{field} has a semicolon or a long dash")
        if "|" in row.get(field, ""):
            out.append(f"{field} has a | (the index uses it as a separator)")
    target = _key(row.get("product_smiles", ""))
    if row.get("product_smiles") and not target:
        out.append("product_smiles does not parse")
    rxn = row.get("reaction_smiles", "")
    if kind == "no_preparation":
        if rxn:
            out.append("a no_preparation row has no reaction")
        if not row.get("note"):
            out.append("a no_preparation row needs the note the card shows")
        return out
    if not row.get("reference"):
        out.append("reference is empty")
    parts = rxn.split(">")
    if len(parts) != 3 or not parts[0] or not parts[2]:
        return out + ["reaction_smiles must be reactants>agents>products"]
    for side in parts:
        for s in side.split("."):
            if s and Chem.MolFromSmiles(s) is None:
                out.append(f"{s} does not parse")
    if out:
        return out
    # The product must be the molecule itself, stereochemistry included.
    if target not in {_key(s) for s in parts[2].split(".")}:
        out.append("product_smiles (with its stereochemistry) is not among the products")
    # Every element of the product comes from a reactant or a reagent (H2O2 in a hydroboration).
    missing = _elements(row["product_smiles"]) - _elements(parts[0]) - _elements(parts[1]) - {"H"}
    if missing:
        out.append(f"nothing on the left supplies {', '.join(sorted(missing))} for the product")
    return out


@lru_cache(maxsize=4)
def _notes(file: str, mtime: float) -> tuple[dict[str, str], dict[str, str]]:
    exact: dict[str, str] = {}
    skeleton: dict[str, str] = {}
    for row in read(Path(file)):
        if row.get("kind") != "no_preparation" or problems(row):
            continue
        key = _key(row["product_smiles"])
        exact.setdefault(key, row["note"])
        skeleton.setdefault(key[:14] + key[-1], row["note"])
    return exact, skeleton


def no_preparation(inchikey: str) -> str:
    """The reviewed "no common preparation" note for a molecule: its own stereoisomer's,
    else that of another stereoisomer of the structure, else ""."""
    file = path()
    if not inchikey or not file.exists():
        return ""
    exact, skeleton = _notes(str(file), file.stat().st_mtime)
    return exact.get(inchikey) or skeleton.get(inchikey[:14] + inchikey[-1], "")
