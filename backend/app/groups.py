"""Functional group detection by SMARTS. Order matters only for display."""

from __future__ import annotations

from rdkit import Chem

GROUPS: list[tuple[str, str, str]] = [
    # (name, SMARTS, colour)
    ("Carboxylic acid", "[CX3](=O)[OX2H1]", "#dc2626"),
    ("Ester", "[CX3](=O)[OX2][#6]", "#ea580c"),
    ("Amide", "[CX3](=O)[NX3]", "#d97706"),
    ("Acyl halide", "[CX3](=O)[F,Cl,Br,I]", "#b91c1c"),
    ("Anhydride", "[CX3](=O)[OX2][CX3](=O)", "#c2410c"),
    ("Aldehyde", "[CX3H1](=O)[#6,#1]", "#e11d48"),
    ("Ketone", "[#6][CX3](=O)[#6]", "#db2777"),
    ("Nitrile", "[CX2]#[NX1]", "#7c3aed"),
    ("Nitro", "[NX3+](=O)[O-]", "#6d28d9"),
    ("Sulfonic acid", "[SX4](=O)(=O)[OX2H1]", "#ca8a04"),
    ("Sulfone", "[#6][SX4](=O)(=O)[#6]", "#a16207"),
    ("Sulfoxide", "[#6][SX3](=O)[#6]", "#854d0e"),
    ("Thiol", "[SX2H1]", "#eab308"),
    ("Thioether", "[#6][SX2][#6]", "#facc15"),
    ("Phenol", "c[OX2H1]", "#0891b2"),
    ("Alcohol", "[CX4][OX2H1]", "#0284c7"),
    ("Ether", "[#6][OX2;!$(O-C=O)][#6]", "#0ea5e9"),
    ("Amine", "[NX3;H2,H1,H0;!$(NC=O);!$(N-[a]);!$(N=*);!$(N#*)][#6]", "#2563eb"),
    ("Aniline N", "[NX3;!$(NC=O)]c", "#1d4ed8"),
    ("Imine", "[CX3]=[NX2]", "#4f46e5"),
    ("Alkyl halide", "[CX4][F,Cl,Br,I]", "#16a34a"),
    ("Aryl halide", "c[F,Cl,Br,I]", "#15803d"),
    ("Alkene", "[CX3]=[CX3]", "#059669"),
    ("Alkyne", "[CX2]#[CX2]", "#047857"),
    ("Aromatic ring", "a1aaaaa1", "#64748b"),
]

_COMPILED = [(name, Chem.MolFromSmarts(sma), colour) for name, sma, colour in GROUPS]


def find_groups(mol: Chem.Mol) -> list[dict]:
    """[{name, colour, atoms: [[i,j,..], ...]}] for every group present."""
    out = []
    for name, patt, colour in _COMPILED:
        matches = mol.GetSubstructMatches(patt, uniquify=True)
        if not matches:
            continue
        if name == "Aromatic ring":  # one entry per ring, drop duplicate orderings
            seen: set[frozenset[int]] = set()
            uniq = []
            for m in matches:
                fs = frozenset(m)
                if fs not in seen:
                    seen.add(fs)
                    uniq.append(sorted(m))
            matches = uniq
        out.append({"name": name, "colour": colour, "atoms": [list(m) for m in matches]})
    return out
