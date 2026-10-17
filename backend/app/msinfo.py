"""Soft-ionisation ions, the nitrogen rule, degrees of unsaturation and formulas that fit an exact mass.

Electron-impact spectra (the fragmentation tree) show M+. and its fragments;
electrospray (ESI), the usual LC-MS source, shows the intact molecule with a
proton, sodium or potassium attached, or a proton removed. The m/z values use
monoisotopic masses and subtract or add the electron. Which ions are likely
follows the groups present: a basic nitrogen takes a proton, an acid loses one,
and oxygen-rich neutral molecules mostly show sodium adducts.

High-resolution MS gives m/z to a few ppm, which narrows the molecular formula:
formulas_for() lists every CHNOS formula (with the molecule's other elements at
their own counts) within a tolerance, filtered by the nitrogen rule and a whole,
non-negative number of rings plus double bonds.
"""

from __future__ import annotations

from rdkit import Chem
from rdkit.Chem import Descriptors

ELECTRON = 0.000548580
PROTON = 1.007276467
MONO = {"C": 12.0, "H": 1.00782503, "N": 14.00307401, "O": 15.99491462, "S": 31.97207117, "F": 18.99840316,
        "Cl": 34.96885268, "Br": 78.9183371, "I": 126.904473, "P": 30.97376199, "Si": 27.97692653, "B": 11.0093054}
VALENCE = {"H": 1, "F": 1, "Cl": 1, "Br": 1, "I": 1, "N": 3, "P": 3, "B": 3, "C": 4, "Si": 4, "O": 2, "S": 2}

_BASIC = Chem.MolFromSmarts("[NX3;H2,H1,H0;!$(NC=[O,S,N]);!$(N-a);!$(N-[SX4]);!$(N#*);!$([N]=*)]")
_PYRIDINE = Chem.MolFromSmarts("[nX2]")
_ACID = Chem.MolFromSmarts("[$([CX3](=O)[OX2H1]),$([SX4](=O)(=O)[OX2H1]),$(c[OX2H1]),$([PX4](=O)[OX2H1])]")


def _ion(label: str, mz: float, likely: bool, why: str) -> dict:
    return {"label": label, "mz": round(mz, 4), "likely": likely, "why": why}


def esi_ions(mol: Chem.Mol) -> list[dict]:
    """The usual ESI ions with exact m/z, the likely ones marked."""
    mass = Descriptors.ExactMolWt(mol)
    charge = Chem.GetFormalCharge(mol)
    if charge:
        # Already an ion: it is seen as it is (RDKit's mass counts the atoms only).
        mz = (mass - charge * ELECTRON) / abs(charge)
        sign = "+" if charge > 0 else "-"
        label = f"[M]{abs(charge) if abs(charge) > 1 else ''}{sign}"
        return [_ion(label, mz, True, "the molecule already carries a charge")]
    basic = mol.HasSubstructMatch(_BASIC) or mol.HasSubstructMatch(_PYRIDINE)
    acid = mol.HasSubstructMatch(_ACID)
    oxygen = sum(a.GetAtomicNum() == 8 for a in mol.GetAtoms())
    nitrogen = sum(a.GetAtomicNum() == 7 for a in mol.GetAtoms())
    polar = basic or acid or oxygen or nitrogen  # a molecule with nothing to protonate or bind barely ionises in ESI
    return [
        _ion("[M+H]+", mass + PROTON, basic or (polar and not acid and oxygen < 2),
             "a basic nitrogen takes a proton" if basic else "protonated molecule"),
        _ion("[M+Na]+", mass + 22.98976928 - ELECTRON, oxygen >= 2 and not basic, "oxygen atoms hold a sodium ion"),
        _ion("[M+K]+", mass + 38.96370649 - ELECTRON, False, "potassium adduct, usually weaker than sodium"),
        _ion("[M+NH4]+", mass + 4 * MONO["H"] + MONO["N"] - ELECTRON, False, "ammonium adduct, with ammonium salts in the eluent"),
        _ion("[2M+H]+", 2 * mass + PROTON, False, "proton-bound dimer at high concentration"),
        _ion("[M-H]-", mass - PROTON, acid, "an acidic O-H loses its proton" if acid else "deprotonated molecule"),
        _ion("[M+Cl]-", mass + MONO["Cl"] + ELECTRON, False, "chloride adduct, with chlorinated solvents"),
        _ion("[M+HCOO]-", mass + MONO["H"] + MONO["C"] + 2 * MONO["O"] + ELECTRON, False, "formate adduct, with formic acid in the eluent"),
    ]


def _counts(mol: Chem.Mol) -> dict[str, int]:
    counts: dict[str, int] = {}
    for a in Chem.AddHs(mol).GetAtoms():
        counts[a.GetSymbol()] = counts.get(a.GetSymbol(), 0) + 1
    return counts


def dbe(counts: dict[str, int]) -> float:
    """Rings plus double bonds: 1 + sum over atoms of (valence - 2) / 2."""
    return 1 + sum(n * (VALENCE.get(el, 4) - 2) for el, n in counts.items()) / 2


def rules(mol: Chem.Mol) -> dict | None:
    """Rings plus double bonds and the nitrogen rule, for neutral molecules (None for ions)."""
    if Chem.GetFormalCharge(mol):
        return None
    counts = _counts(mol)
    table = Chem.GetPeriodicTable()
    nominal = sum(table.GetMostCommonIsotope(el) * n for el, n in counts.items())
    n_count = counts.get("N", 0)
    return {
        "dbe": dbe(counts),
        "nitrogen": n_count,
        "nominal": nominal,
        "nitrogen_rule": (nominal % 2 == 1) == (n_count % 2 == 1),
    }


def _formula(counts: dict[str, int]) -> str:
    order = ["C", "H"] + sorted(k for k in counts if k not in ("C", "H"))
    return "".join(f"{el}{counts[el] if counts[el] > 1 else ''}" for el in order if counts.get(el))


def formulas_for(mol: Chem.Mol, ppm: float = 5.0, limit: int = 8) -> dict:
    """Formulas whose neutral monoisotopic mass is within `ppm` of the molecule's: C, H, N, O, S free, the
    molecule's other elements fixed at their counts. Sorted by error; the true one is marked."""
    counts = _counts(mol)
    if Chem.GetFormalCharge(mol) or any(el not in MONO for el in counts):
        return {"ppm": ppm, "candidates": [], "total": 0}
    target = sum(MONO[el] * n for el, n in counts.items())
    fixed = {el: n for el, n in counts.items() if el not in ("C", "H", "N", "O", "S")}
    fixed_mass = sum(MONO[el] * n for el, n in fixed.items())
    tol = target * ppm * 1e-6
    out = []
    for c in range(0, 81):
        for n in range(0, 9):
            for o in range(0, 13):
                for s in range(0, 4):
                    rest = target - fixed_mass - c * MONO["C"] - n * MONO["N"] - o * MONO["O"] - s * MONO["S"]
                    h = round(rest / MONO["H"])
                    if h < 0:
                        continue
                    err = rest - h * MONO["H"]
                    if abs(err) > tol:
                        continue
                    cand = {**fixed, "C": c, "H": h, "N": n, "O": o, "S": s}
                    cand = {k: v for k, v in cand.items() if v}
                    d = dbe(cand)
                    halogens = sum(cand.get(x, 0) for x in ("F", "Cl", "Br", "I"))
                    if d < 0 or d != int(d) or h > 2 * c + n + 2 - halogens + 2 * cand.get("Si", 0):
                        continue
                    out.append({"formula": _formula(cand), "ppm": round(err / target * 1e6, 2), "dbe": int(d)})
    true = _formula(counts)
    out.sort(key=lambda f: (abs(f["ppm"]), f["formula"]))
    shown = out[:limit]
    if true not in {f["formula"] for f in shown}:
        shown += [f for f in out if f["formula"] == true]
    for f in shown:
        f["actual"] = f["formula"] == true
    return {"ppm": ppm, "candidates": shown, "total": len(out)}
