"""Constitutional isomer enumeration for small formulas.

Scope: up to 8 heavy atoms, elements C, N, O, F, Cl, Br, I, at most two
heteroatoms, and a degree of unsaturation of 0 or 1 (one double bond or
one ring). Each constitutional isomer also reports its stereoisomers.
This covers the formulas used in introductory courses (C4H10, C5H12,
C4H10O, C3H8O, C4H8, C4H9Cl, C3H9N, C4H8O ...).
"""

from __future__ import annotations

import re
from functools import lru_cache
from itertools import combinations

from rdkit import Chem
from rdkit.Chem import rdDepictor
from rdkit.Chem.Draw import rdMolDraw2D

from .chem import ChemError

MAX_HEAVY = 8
_HALOGENS = {"F", "Cl", "Br", "I"}
_MAX_DEGREE = {"C": 4, "N": 3, "O": 2, "F": 1, "Cl": 1, "Br": 1, "I": 1}


def parse_formula(text: str) -> dict[str, int]:
    text = text.strip().replace(" ", "")
    if not re.fullmatch(r"(?:[A-Z][a-z]?\d*)+", text):
        raise ChemError("Formula must look like C4H10O.")
    counts: dict[str, int] = {}
    for el, n in re.findall(r"([A-Z][a-z]?)(\d*)", text):
        counts[el] = counts.get(el, 0) + (int(n) if n else 1)
    for el in counts:
        if el not in _MAX_DEGREE and el != "H":
            raise ChemError(f"Element {el} is not supported (C, H, N, O and halogens only).")
    return counts


def unsaturation(counts: dict[str, int]) -> float:
    c = counts.get("C", 0)
    h = counts.get("H", 0)
    n = counts.get("N", 0)
    x = sum(counts.get(el, 0) for el in _HALOGENS)
    return (2 * c + 2 + n - h - x) / 2


@lru_cache(maxsize=None)
def carbon_trees(n: int) -> tuple[str, ...]:
    """Canonical SMILES of all acyclic saturated carbon skeletons with n atoms."""
    if n == 1:
        return ("C",)
    out: set[str] = set()
    for smi in carbon_trees(n - 1):
        mol = Chem.MolFromSmiles(smi)
        for atom in mol.GetAtoms():
            if atom.GetDegree() >= 4:
                continue
            rw = Chem.RWMol(mol)
            new = rw.AddAtom(Chem.Atom(6))
            rw.AddBond(atom.GetIdx(), new, Chem.BondType.SINGLE)
            out.add(Chem.MolToSmiles(rw.GetMol()))
    return tuple(sorted(out))


def _substitute(smiles: str, elements: list[str]) -> set[str]:
    """Replace `len(elements)` skeleton atoms by the given heteroatoms in every valid way."""
    mol = Chem.MolFromSmiles(smiles)
    n = mol.GetNumAtoms()
    out: set[str] = set()
    k = len(elements)
    if k == 0:
        return {Chem.MolToSmiles(mol)}
    for positions in combinations(range(n), k):
        # assign elements to positions in every distinct order
        for order in set(_permutations(elements)):
            rw = Chem.RWMol(mol)
            ok = True
            for pos, el in zip(positions, order):
                a = rw.GetAtomWithIdx(pos)
                if a.GetDegree() > _MAX_DEGREE[el]:
                    ok = False
                    break
                a.SetAtomicNum(Chem.GetPeriodicTable().GetAtomicNumber(el))
            if not ok:
                continue
            m = rw.GetMol()
            try:
                Chem.SanitizeMol(m)
            except Exception:  # noqa: BLE001
                continue
            if _has_bad_bond(m):
                continue
            out.add(Chem.MolToSmiles(m))
    return out


def _permutations(items: list[str]) -> list[tuple[str, ...]]:
    from itertools import permutations

    return list(permutations(items))


def _has_bad_bond(m: Chem.Mol) -> bool:
    """Skip peroxides, hydrazines and halogen-heteroatom bonds: not what a course wants."""
    for b in m.GetBonds():
        a, c = b.GetBeginAtom().GetSymbol(), b.GetEndAtom().GetSymbol()
        if a != "C" and c != "C":
            return True
    return False


def _add_ring_bond(smiles: str) -> set[str]:
    """Close one ring by bonding two non-adjacent atoms (tree + one edge = one ring)."""
    mol = Chem.MolFromSmiles(smiles)
    n = mol.GetNumAtoms()
    out: set[str] = set()
    for i in range(n):
        for j in range(i + 1, n):
            if mol.GetBondBetweenAtoms(i, j) is not None:
                continue
            ai, aj = mol.GetAtomWithIdx(i), mol.GetAtomWithIdx(j)
            if ai.GetDegree() >= _MAX_DEGREE[ai.GetSymbol()] or aj.GetDegree() >= _MAX_DEGREE[aj.GetSymbol()]:
                continue
            # ring size >= 3: i and j must not share a neighbour... they may (gives a 3-ring), just not be bonded
            rw = Chem.RWMol(mol)
            rw.AddBond(i, j, Chem.BondType.SINGLE)
            m = rw.GetMol()
            try:
                Chem.SanitizeMol(m)
            except Exception:  # noqa: BLE001
                continue
            if _has_bad_bond(m):
                continue
            out.add(Chem.MolToSmiles(m))
    return out


def _stereoisomers(smiles: str) -> list[str]:
    from rdkit.Chem.EnumerateStereoisomers import EnumerateStereoisomers, StereoEnumerationOptions

    mol = Chem.MolFromSmiles(smiles)
    opts = StereoEnumerationOptions(onlyUnassigned=True, unique=True, tryEmbedding=False, maxIsomers=32)
    return sorted({Chem.MolToSmiles(m) for m in EnumerateStereoisomers(mol, options=opts)})


def _add_double_bond(smiles: str) -> set[str]:
    mol = Chem.MolFromSmiles(smiles)
    out: set[str] = set()
    for b in mol.GetBonds():
        a1, a2 = b.GetBeginAtom(), b.GetEndAtom()
        if any(x.GetSymbol() in _HALOGENS for x in (a1, a2)):
            continue
        rw = Chem.RWMol(mol)
        rw.GetBondWithIdx(b.GetIdx()).SetBondType(Chem.BondType.DOUBLE)
        m = rw.GetMol()
        try:
            Chem.SanitizeMol(m)
        except Exception:  # noqa: BLE001
            continue
        # valence check: no atom may exceed its maximum
        if any(a.GetExplicitValence() > _MAX_DEGREE[a.GetSymbol()] for a in m.GetAtoms()):
            continue
        out.add(Chem.MolToSmiles(m))
    return out


def enumerate_isomers(formula: str) -> dict:
    counts = parse_formula(formula)
    c = counts.get("C", 0)
    hetero = [el for el, n in counts.items() if el not in ("C", "H") for _ in range(n)]
    heavy = c + len(hetero)
    if c == 0:
        raise ChemError("Formula needs at least one carbon.")
    if heavy > MAX_HEAVY:
        raise ChemError(f"Up to {MAX_HEAVY} heavy atoms are supported.")
    if len(hetero) > 2:
        raise ChemError("Up to two heteroatoms are supported.")
    dbe = unsaturation(counts)
    if dbe not in (0, 1):
        raise ChemError("Only formulas with zero or one degree of unsaturation are supported (one double bond or one ring at most).")

    skeletons: set[str] = set()
    for tree in carbon_trees(heavy):
        skeletons |= _substitute(tree, hetero)
    if dbe == 1:
        unsaturated: set[str] = set()
        for s in skeletons:
            unsaturated |= _add_double_bond(s)
            unsaturated |= _add_ring_bond(s)
        skeletons = unsaturated

    # Verify formula and dedupe by canonical SMILES (stereo ignored).
    from rdkit.Chem import rdMolDescriptors

    target = _formula_key(counts)
    results = []
    skipped = 0
    for s in sorted(skeletons):
        m = Chem.MolFromSmiles(s)
        if _formula_key(parse_formula(rdMolDescriptors.CalcMolFormula(m))) != target:
            continue
        if any(m.HasSubstructMatch(p) for p in _UNSTABLE):
            skipped += 1
            continue
        results.append(s)
    # acyclic first, then rings; within each, canonical order
    def _nrings(smi: str) -> int:
        m = Chem.MolFromSmiles(smi)
        Chem.FastFindRings(m)
        return m.GetRingInfo().NumRings()

    results.sort(key=lambda s: (_nrings(s), s))
    isomers = []
    stereo_total = 0
    for s in results:
        stereo = _stereoisomers(s)
        stereo_total += len(stereo)
        isomers.append({
            "smiles": s,
            "svg": _svg(s),
            "cyclic": _nrings(s) > 0,
            "stereoisomers": stereo,
            "stereo_count": len(stereo),
        })
    return {
        "formula": formula.strip(),
        "count": len(results),
        "stereo_total": stereo_total,
        "unsaturation": dbe,
        "isomers": isomers,
        "skipped_unstable": skipped,
        "note": ("Constitutional isomers with at most one ring or double bond." if dbe == 1 else "Constitutional isomers.")
        + f" Counting stereoisomers separately gives {stereo_total}."
        + (f" {skipped} enol or gem-diol tautomer{'s' if skipped != 1 else ''} omitted." if skipped else ""),
    }


# Tautomers that courses do not count as separate isomers.
_UNSTABLE = [Chem.MolFromSmarts(p) for p in ("[CX3]=[CX3][OX2H1]", "[CX4]([OX2H1])[OX2H1]", "[CX3]=[CX3][NX3H2]", "[CX3]=[CX3][NX3H1]")]


def _formula_key(counts: dict[str, int]) -> tuple:
    return tuple(sorted(counts.items()))


def _svg(smiles: str, width: int = 220, height: int = 160) -> str:
    m = Chem.MolFromSmiles(smiles)
    rdDepictor.Compute2DCoords(m)
    d = rdMolDraw2D.MolDraw2DSVG(width, height)
    d.drawOptions().clearBackground = False
    d.drawOptions().bondLineWidth = 1.6
    d.DrawMolecule(m)
    d.FinishDrawing()
    return d.GetDrawingText()
