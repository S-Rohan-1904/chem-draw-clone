"""UV-Vis absorption maximum estimated with the Woodward-Fieser rules (ethanol).

The chromophore is the longest chain of conjugated, non-aromatic C=C and C=O
bonds. A conjugated diene or polyene starts from 217 nm (acyclic), 214 nm (in
rings but not both double bonds in one ring) or 253 nm (homoannular, both in one
ring); an alpha,beta-unsaturated carbonyl from 215 nm (ketone or six-membered
ring), 202 nm (cyclopentenone), 210 nm (aldehyde) or 195 nm (acid or ester).
Increments are added for each further conjugated double bond, a homoannular
diene component, exocyclic double bonds, and each substituent on the chromophore
by kind and, for carbonyls, by position (alpha, beta, gamma or further). Above
four conjugated double bonds the Fieser-Kuhn rule applies instead. Values are
the textbook ones; the rules are good to about 5 nm for the molecules they were
made for and do not cover aromatic chromophores.
"""

from __future__ import annotations

from rdkit import Chem

ENONE_BASE = {"ketone": 215, "cyclopentenone": 202, "aldehyde": 210, "acid or ester": 195}
# Substituent increments for enones by position: alpha, beta, gamma, delta or further.
ENONE_SUB = {
    "alkyl or ring residue": (10, 12, 18, 18),
    "OH": (35, 30, 30, 50),
    "OR": (35, 30, 17, 31),
    "O-acyl": (6, 6, 6, 6),
    "Cl": (15, 12, 12, 12),
    "Br": (25, 30, 25, 25),
    "NR2": (95, 95, 95, 95),
    "SR": (85, 85, 85, 85),
}
DIENE_SUB = {"alkyl or ring residue": 5, "OH": 6, "OR": 6, "O-acyl": 0, "Cl": 5, "Br": 5, "NR2": 60, "SR": 30}
POSITIONS = ("alpha", "beta", "gamma", "delta or further")


def _double_bonds(mol: Chem.Mol) -> list[Chem.Bond]:
    out = []
    for b in mol.GetBonds():
        if b.GetBondType() != Chem.BondType.DOUBLE or b.GetIsAromatic():
            continue
        z = {b.GetBeginAtom().GetAtomicNum(), b.GetEndAtom().GetAtomicNum()}
        if z == {6} or z == {6, 8}:
            out.append(b)
    return out


def _chains(mol: Chem.Mol, bonds: list[Chem.Bond]) -> list[list[int]]:
    """Every simple path of double bonds joined by single bonds, as atom chains [a0, a1, a2, ...]
    where (a0, a1), (a2, a3), ... are the double bonds."""
    by_atom: dict[int, list[Chem.Bond]] = {}
    for b in bonds:
        for a in (b.GetBeginAtomIdx(), b.GetEndAtomIdx()):
            by_atom.setdefault(a, []).append(b)
    chains = []

    def extend(chain: list[int]):
        chains.append(chain)
        end = mol.GetAtomWithIdx(chain[-1])
        for nb in end.GetNeighbors():
            single = mol.GetBondBetweenAtoms(end.GetIdx(), nb.GetIdx())
            if single.GetBondType() != Chem.BondType.SINGLE or nb.GetIdx() in chain:
                continue
            for b in by_atom.get(nb.GetIdx(), []):
                other = b.GetOtherAtomIdx(nb.GetIdx())
                if other not in chain:
                    extend(chain + [nb.GetIdx(), other])

    for b in bonds:
        for a0, a1 in ((b.GetBeginAtomIdx(), b.GetEndAtomIdx()), (b.GetEndAtomIdx(), b.GetBeginAtomIdx())):
            extend([a0, a1])
    return chains


def _kind(mol: Chem.Mol, atom: Chem.Atom, came_from: int) -> str | None:
    z = atom.GetAtomicNum()
    if z == 6:
        return "alkyl or ring residue"
    if z == 8:
        if atom.GetTotalNumHs() > 0:
            return "OH"
        for nb in atom.GetNeighbors():
            if nb.GetIdx() != came_from and any(b.GetBondType() == Chem.BondType.DOUBLE and b.GetOtherAtom(nb).GetAtomicNum() == 8
                                                for b in nb.GetBonds()):
                return "O-acyl"
        return "OR"
    return {7: "NR2", 16: "SR", 17: "Cl", 35: "Br"}.get(z)


def _exocyclic(mol: Chem.Mol, a: int, b: int) -> int:
    """Rings the double bond a=b is exocyclic to: rings that contain exactly one of its atoms."""
    return sum((a in ring) != (b in ring) for ring in mol.GetRingInfo().AtomRings())


def _homoannular(mol: Chem.Mol, pairs: list[tuple[int, int]]) -> bool:
    for ring in mol.GetRingInfo().AtomRings():
        inside = [p for p in pairs if p[0] in ring and p[1] in ring]
        if len(inside) >= 2:
            return True
    return False


def estimate(mol: Chem.Mol) -> dict:
    """{rule, lambda_max, parts: [{label, nm, atoms}], chromophore, note}; rule None when no rule applies."""
    bonds = _double_bonds(mol)
    chains = [c for c in _chains(mol, bonds) if len(c) >= 4]
    carbonyl = lambda i: mol.GetAtomWithIdx(i).GetAtomicNum() == 8  # noqa: E731
    enones = [c for c in chains if carbonyl(c[0]) and not any(carbonyl(i) for i in c[1:])]
    polyenes = [c for c in chains if not any(carbonyl(i) for i in c)]
    aromatic = any(a.GetIsAromatic() for a in mol.GetAtoms())
    if not enones and not polyenes:
        notes = []
        if aromatic:
            notes.append("an aromatic ring absorbs near 255 nm (weak) and 200 nm (strong)")
        if any(carbonyl(b.GetBeginAtomIdx()) or carbonyl(b.GetEndAtomIdx()) for b in bonds):
            notes.append("an isolated C=O absorbs very weakly near 280 nm (n to pi*)")
        if any(not (carbonyl(b.GetBeginAtomIdx()) or carbonyl(b.GetEndAtomIdx())) for b in bonds):
            notes.append("an isolated C=C absorbs below 200 nm")
        return {"rule": None, "lambda_max": None, "parts": [], "chromophore": [],
                "note": "No conjugated diene or enone, so the Woodward-Fieser rules do not apply."
                        + (" Here " + ", and ".join(notes) + "." if notes else "")}
    if enones:
        chain = max(enones, key=len)
        return _enone(mol, chain, aromatic)
    chain = max(polyenes, key=len)
    return _polyene(mol, chain, aromatic)


def _substituents(mol: Chem.Mol, chain: list[int], skip: set[int]) -> list[tuple[int, int, str]]:
    """(chain atom, substituent atom, kind) for every heavy atom on the chromophore that is not part of it."""
    out = []
    for i in chain:
        if i in skip:
            continue
        for nb in mol.GetAtomWithIdx(i).GetNeighbors():
            if nb.GetIdx() in chain:
                continue
            kind = _kind(mol, nb, i)
            if kind:
                out.append((i, nb.GetIdx(), kind))
    return out


def _common(mol: Chem.Mol, chain: list[int], cc: list[tuple[int, int]], parts: list[dict], covered: int, homo: int) -> None:
    """Increments shared by both rules: C=C beyond those the base value covers, a homoannular diene
    component (enones only; for dienes it is in the base) and exocyclic C=C."""
    extra = len(cc) - covered
    if extra > 0:
        parts.append({"label": f"{extra} more conjugated C=C", "nm": 30 * extra, "atoms": chain})
    if homo and _homoannular(mol, cc):
        parts.append({"label": "homoannular diene component", "nm": homo, "atoms": chain})
    exo = sum(_exocyclic(mol, a, b) for a, b in cc)
    if exo:
        parts.append({"label": f"{exo} exocyclic C=C", "nm": 5 * exo, "atoms": chain})


def _enone(mol: Chem.Mol, chain: list[int], aromatic: bool) -> dict:
    o, c1, alpha, beta = chain[0], chain[1], chain[2], chain[3]
    carbonyl_c = mol.GetAtomWithIdx(c1)
    others = [nb for nb in carbonyl_c.GetNeighbors() if nb.GetIdx() not in (o, alpha)]
    if carbonyl_c.GetTotalNumHs() > 0:
        kind = "aldehyde"
    elif any(nb.GetAtomicNum() == 8 for nb in others):
        kind = "acid or ester"
    elif any(len(r) == 5 and c1 in r and alpha in r and beta in r for r in mol.GetRingInfo().AtomRings()):
        kind = "cyclopentenone"
    else:
        kind = "ketone"
    parts = [{"label": f"base value, {kind}", "nm": ENONE_BASE[kind], "atoms": [o, c1, alpha, beta]}]
    pairs = [(chain[k], chain[k + 1]) for k in range(0, len(chain), 2)]
    _common(mol, chain, pairs[1:], parts, covered=1, homo=39)
    position = {atom: min(k - 2, 3) for k, atom in enumerate(chain) if k >= 2}
    for atom, sub, kind_ in _substituents(mol, chain, {o, c1}):
        pos = position[atom]
        parts.append({"label": f"{kind_} at {POSITIONS[pos]}", "nm": ENONE_SUB[kind_][pos], "atoms": [atom, sub]})
    return _result("enone", parts, chain, aromatic)


def _polyene(mol: Chem.Mol, chain: list[int], aromatic: bool) -> dict:
    pairs = [(chain[k], chain[k + 1]) for k in range(0, len(chain), 2)]
    subs = _substituents(mol, chain, set())
    if len(pairs) > 4:
        # Fieser-Kuhn: 114 + 5M + n(48.0 - 1.7n) - 16.5 R_endo - 10 R_exo
        n = len(pairs)
        m = sum(1 for *_, k in subs if k == "alkyl or ring residue")
        rings = mol.GetRingInfo().AtomRings()
        endo = sum(1 for r in rings if any(a in r and b in r for a, b in pairs))
        exo = sum(1 for r in rings if any((a in r) != (b in r) for a, b in pairs))
        parts = [{"label": "Fieser-Kuhn base", "nm": 114, "atoms": chain},
                 {"label": f"{n} conjugated C=C, n(48.0 - 1.7n)", "nm": round(n * (48.0 - 1.7 * n), 1), "atoms": chain},
                 {"label": f"{m} alkyl groups, 5 nm each", "nm": 5 * m, "atoms": sorted({s for _, s, _ in subs})}]
        if endo:
            parts.append({"label": f"{endo} rings with a C=C inside, -16.5 nm each", "nm": -16.5 * endo, "atoms": chain})
        if exo:
            parts.append({"label": f"{exo} rings with an exocyclic C=C, -10 nm each", "nm": -10 * exo, "atoms": chain})
        return _result("polyene", parts, chain, aromatic)
    in_ring = any(any(i in r for r in mol.GetRingInfo().AtomRings()) for i in chain)
    homo = _homoannular(mol, pairs)
    base, label = (253, "homoannular diene") if homo else (214, "heteroannular diene") if in_ring else (217, "acyclic diene")
    parts = [{"label": f"base value, {label}", "nm": base, "atoms": chain[:4]}]
    _common(mol, chain, pairs, parts, covered=2, homo=0)
    for atom, sub, kind in _substituents(mol, chain, set()):
        if DIENE_SUB[kind]:
            parts.append({"label": kind, "nm": DIENE_SUB[kind], "atoms": [atom, sub]})
    return _result("diene", parts, chain, aromatic)


def _result(rule: str, parts: list[dict], chain: list[int], aromatic: bool) -> dict:
    total = round(sum(p["nm"] for p in parts))
    note = "Woodward-Fieser estimate for ethanol solution, usually within about 5 nm for dienes and enones."
    if rule == "polyene":
        note = "Fieser-Kuhn estimate for long polyenes (hexane), usually within about 10 nm."
    if aromatic:
        note += " An aromatic ring conjugated with the chromophore shifts it further than the rules allow."
    if total >= 400:
        note += " It absorbs visible light, so the compound is coloured."
    return {"rule": rule, "lambda_max": total, "parts": parts, "chromophore": sorted(set(chain)), "note": note}
