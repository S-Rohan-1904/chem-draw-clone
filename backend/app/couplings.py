"""1H-1H coupling constants and multiplet patterns.

Every hydrogen pair is classified by the path between them: geminal (same
carbon), vicinal across a single, double or aromatic bond, or meta across an
aromatic ring. Vicinal J across a freely rotating single bond is the usual
7 Hz average; in rings and across double bonds it comes from the Karplus
relation applied to the conformer's dihedral. Values are textbook typical,
good to about 1 Hz.
"""

from __future__ import annotations

import math
from collections import defaultdict

from rdkit import Chem
from rdkit.Chem import rdMolTransforms

# Partners with |J| below this are not resolved as splitting.
MIN_J = 0.8
_LETTERS = {1: "d", 2: "t", 3: "q", 4: "quint", 5: "sext", 6: "sept"}


def _karplus(phi_deg: float) -> float:
    """3J(H-C-C-H) from the H-C-C-H dihedral (Karplus, 1959 form)."""
    phi = math.radians(phi_deg)
    return 7.0 - math.cos(phi) + 5.0 * math.cos(2 * phi)


def _vinyl(phi_deg: float) -> float:
    """3J across C=C: about 10.5 Hz cis (0 deg), 16 Hz trans (180 deg)."""
    return 13.25 - 2.75 * math.cos(math.radians(phi_deg))


def _is_carbonyl(a: Chem.Atom) -> bool:
    return a.GetAtomicNum() == 6 and any(
        b.GetBondType() == Chem.BondType.DOUBLE and b.GetOtherAtom(a).GetAtomicNum() == 8 for b in a.GetBonds()
    )


def _rotatable(bond: Chem.Bond) -> bool:
    """Acyclic single bond: the dihedral averages out, so use the mean J."""
    return not bond.IsInRing() and bond.GetBondType() == Chem.BondType.SINGLE


def _pair_j(mh: Chem.Mol, conf, h1: Chem.Atom, h2: Chem.Atom) -> float | None:
    """|J| in Hz for two hydrogens, or None when they do not couple usefully."""
    p1, p2 = h1.GetNeighbors()[0], h2.GetNeighbors()[0]
    if p1.GetAtomicNum() != 6 or p2.GetAtomicNum() != 6:
        return None  # O-H / N-H protons exchange; no resolved coupling
    if p1.GetIdx() == p2.GetIdx():
        # Geminal: only observable when the two hydrogens are inequivalent.
        if p1.GetHybridization() == Chem.HybridizationType.SP2:
            return 1.5
        return 12.5
    bond = mh.GetBondBetweenAtoms(p1.GetIdx(), p2.GetIdx())
    if bond is not None:
        if bond.GetIsAromatic():
            return 8.0
        if _is_carbonyl(p1) or _is_carbonyl(p2):
            return 2.5  # aldehyde H to alpha H
        phi = None
        if conf is not None:
            phi = rdMolTransforms.GetDihedralDeg(conf, h1.GetIdx(), p1.GetIdx(), p2.GetIdx(), h2.GetIdx())
        if bond.GetBondType() == Chem.BondType.DOUBLE:
            return _vinyl(phi) if phi is not None else 13.0
        if _rotatable(bond) or phi is None:
            return 7.0
        return _karplus(phi)
    # Meta across an aromatic ring: two aromatic bonds apart in the same ring.
    if p1.GetIsAromatic() and p2.GetIsAromatic():
        for mid in p1.GetNeighbors():
            if mid.GetIsAromatic() and mh.GetBondBetweenAtoms(mid.GetIdx(), p2.GetIdx()) is not None:
                ring_info = mh.GetRingInfo()
                if any(p1.GetIdx() in r and p2.GetIdx() in r and mid.GetIdx() in r for r in ring_info.AtomRings()):
                    return 2.0
    return None


def couplings(mh: Chem.Mol, ranks: list[int], conf, h_idx: int) -> list[dict]:
    """Coupling partners of hydrogen ``h_idx``, grouped by equivalence class:
    [{J, n, atoms (heavy parents of the partners), kind}] sorted by J."""
    h = mh.GetAtomWithIdx(h_idx)
    own = ranks[h_idx]
    by_class: dict[int, list[tuple[float, int]]] = defaultdict(list)
    for other in mh.GetAtoms():
        if other.GetAtomicNum() != 1 or other.GetIdx() == h_idx or ranks[other.GetIdx()] == own:
            continue
        j = _pair_j(mh, conf, h, other)
        if j is not None and abs(j) >= MIN_J:
            by_class[ranks[other.GetIdx()]].append((abs(j), other.GetNeighbors()[0].GetIdx()))
    out = []
    for vals in by_class.values():
        # Topologically equivalent partners can still differ in J (axial vs
        # equatorial, cis vs trans on a =CH2): split the class where J jumps.
        vals.sort()
        groups: list[list[tuple[float, int]]] = [[vals[0]]]
        for v in vals[1:]:
            if v[0] - groups[-1][-1][0] > 3.0:
                groups.append([v])
            else:
                groups[-1].append(v)
        for g in groups:
            js = [j for j, _ in g]
            out.append({
                "J": round(sum(js) / len(js), 1),
                "n": len(g),
                "atoms": sorted({p for _, p in g}),
            })
    out.sort(key=lambda c: -c["J"])
    return out


def pattern(cs: list[dict]) -> tuple[str, list[dict]]:
    """Multiplet symbol (s, d, dd, td, m, ...) plus the merged coupling list.
    Partners whose J differ by under 0.7 Hz are treated as one splitting."""
    if not cs:
        return "s", []
    merged: list[dict] = []
    for c in cs:
        if merged and abs(merged[-1]["J"] - c["J"]) < 0.7:
            m = merged[-1]
            tot = m["n"] + c["n"]
            m["J"] = round((m["J"] * m["n"] + c["J"] * c["n"]) / tot, 1)
            m["n"] = tot
            m["atoms"] = sorted(set(m["atoms"]) | set(c["atoms"]))
        else:
            merged.append(dict(c))
    if len(merged) > 3 or any(m["n"] > 6 for m in merged) or sum(m["n"] for m in merged) > 8:
        return "m", merged
    return "".join(_LETTERS[m["n"]] for m in merged), merged


def _a_value(sub: Chem.Atom, ring_atom: int) -> float:
    """Conformational free energy (kcal/mol) an axial substituent costs on a
    cyclohexane, by substituent type (Eliel's A values, rounded)."""
    z = sub.GetAtomicNum()
    heavy = [n for n in sub.GetNeighbors() if n.GetAtomicNum() > 1 and n.GetIdx() != ring_atom]
    if z == 6:
        if sub.GetIsAromatic():
            return 2.8
        if any(b.GetBondType() == Chem.BondType.TRIPLE for b in sub.GetBonds()):
            return 0.2  # C#N
        if any(b.GetBondType() == Chem.BondType.DOUBLE and b.GetOtherAtom(sub).GetAtomicNum() == 8 for b in sub.GetBonds()):
            return 1.3  # COOH / COOR / COR
        if any(b.GetBondType() == Chem.BondType.DOUBLE for b in sub.GetBonds()):
            return 1.5  # vinyl
        return {0: 1.7, 1: 1.75, 2: 2.2}.get(len(heavy), 4.9)
    if z == 8:
        return 0.9 if not heavy else 0.6
    if z == 7:
        return 1.4
    if z == 16:
        return 1.0
    return {9: 0.25, 17: 0.5, 35: 0.5, 53: 0.5}.get(z, 1.0)


def _axial_penalty(mol: Chem.Mol, conf) -> float:
    """Sum of A values for axial substituents on chair cyclohexanes. MMFF
    misranks some (it puts chlorocyclohexane's Cl axial), so this decides
    between conformers before the force-field energy does."""
    from .conformers import _axial_set, _is_chair, _ring_order

    total = 0.0
    for ring in mol.GetRingInfo().AtomRings():
        if len(ring) != 6 or any(mol.GetAtomWithIdx(i).GetAtomicNum() != 6 or mol.GetAtomWithIdx(i).GetHybridization() != Chem.HybridizationType.SP3 for i in ring):
            continue
        ordered = _ring_order(mol, list(ring))
        if not _is_chair(conf, ordered):
            total += 3.0  # twist-boat: worse than any single axial group
            continue
        for sub_idx in _axial_set(mol, conf, ordered):
            sub = mol.GetAtomWithIdx(sub_idx)
            ring_atom = next(n.GetIdx() for n in sub.GetNeighbors() if n.GetIdx() in ring)
            total += _a_value(sub, ring_atom)
    return total


def conformer(mol: Chem.Mol):
    """The preferred one of a few embedded conformers: fewest axial A values
    on chair rings first, then the lowest MMFF energy. None if embedding fails."""
    from rdkit.Chem import AllChem

    try:
        ps = AllChem.ETKDGv3()
        ps.randomSeed = 11
        cids = list(AllChem.EmbedMultipleConfs(mol, numConfs=8, params=ps))
        if not cids:
            return None
        if not AllChem.MMFFHasAllMoleculeParams(mol):
            return mol.GetConformer(cids[0])
        res = AllChem.MMFFOptimizeMoleculeConfs(mol, maxIters=300)
        ranked = sorted(zip(cids, res), key=lambda t: (round(_axial_penalty(mol, mol.GetConformer(t[0])), 1), t[1][1]))
        return mol.GetConformer(ranked[0][0])
    except Exception:  # noqa: BLE001 - fall back to averaged J values
        return None
