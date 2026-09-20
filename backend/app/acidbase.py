"""Rule-based acid/base sites with textbook pKa values, the ionisation state
at a chosen pH, and the isoelectric point.

These are typical values for the group in water, not predictions for the
specific molecule. Substituent effects beyond the listed patterns are not
modelled, so the numbers are good to about one pKa unit.
"""

from __future__ import annotations

import math

from rdkit import Chem
from rdkit.Chem import rdDepictor
from rdkit.Chem.Draw import rdMolDraw2D

from .chem import ChemError, mol_from_smiles

# (name, SMARTS, index of the site atom in the match, pKa, kind)
# Specific patterns come first; an atom is claimed by the first rule that matches it.
RULES: list[tuple[str, str, int, float, str]] = [
    ("Sulfonic acid", "[SX4](=O)(=O)[OX2H1]", 3, -2.0, "acid"),
    ("Trifluoroacetic acid", "FC(F)(F)[CX3](=O)[OX2H1]", 6, 0.5, "acid"),
    ("Alpha-amino acid, carboxyl", "[NX3;H2,H1;!$(NC=O)][CX4][CX3](=O)[OX2H1]", 4, 2.3, "acid"),
    ("Alpha-amino acid, amino", "[NX3;H2,H1;!$(NC=O)][CX4][CX3](=O)[OX2H1,OX1-]", 0, 9.7, "base"),
    ("Alpha-chloro carboxylic acid", "Cl[CX4][CX3](=O)[OX2H1]", 4, 2.9, "acid"),
    ("Benzoic acid", "c[CX3](=O)[OX2H1]", 3, 4.2, "acid"),
    ("Acrylic acid (conjugated)", "[CX3]=[CX3][CX3](=O)[OX2H1]", 4, 4.3, "acid"),
    ("Carboxylic acid", "[CX3](=O)[OX2H1]", 2, 4.8, "acid"),
    ("Tetrazole", "[nH]1nnnc1", 0, 4.9, "acid"),
    ("Nitrophenol", "[OX2H1]c1ccc([N+](=O)[O-])cc1", 0, 7.2, "acid"),
    ("Nitrophenol", "[OX2H1]c1c([N+](=O)[O-])cccc1", 0, 7.2, "acid"),
    ("Phenol", "c[OX2H1]", 1, 10.0, "acid"),
    ("Thiophenol", "c[SX2H1]", 1, 6.6, "acid"),
    ("Thiol", "[CX4][SX2H1]", 1, 10.5, "acid"),
    ("Imide N-H", "[CX3](=O)[NX3H1][CX3](=O)", 2, 8.3, "acid"),
    ("Sulfonamide N-H", "[SX4](=O)(=O)[NX3H2]", 3, 10.1, "acid"),
    ("1,3-Diketone C-H", "[#6][CX3](=O)[CH2][CX3](=O)[#6]", 3, 9.0, "acid"),
    ("Beta-keto ester C-H", "[#6][CX3](=O)[CH2][CX3](=O)[OX2][#6]", 3, 11.0, "acid"),
    ("Alcohol", "[CX4][OX2H1]", 1, 16.0, "acid"),
    ("Terminal alkyne C-H", "[CX2H1]#[CX2]", 0, 25.0, "acid"),
    ("Guanidine", "[NX3]C(=[NX2])[NX3]", 2, 13.6, "base"),
    ("Amidine", "[CX3](=[NX2;!$(N-C=O)])[NX3;!$(NC=O)]", 1, 12.4, "base"),
    ("Imidazole", "[nX2]1c[nH]cc1", 0, 7.0, "base"),
    ("Imidazole", "[nX2]1cc[nH]c1", 0, 7.0, "base"),
    ("Pyridine", "[nX2;r6;!$(n-*)]", 0, 5.2, "base"),
    ("Azole N", "[nX2;r5]", 0, 2.5, "base"),
    ("Aniline", "[NX3;H2,H1,H0;!$(NC=O);!$(N-[SX4]);!$(N=*)]c", 0, 4.6, "base"),
    ("Primary amine", "[NX3H2;!$(NC=O);!$(N-[a]);!$(N-[SX4]);!$(NN);!$(NO)][CX4]", 0, 10.6, "base"),
    ("Secondary amine", "[NX3H1;!$(NC=O);!$(N-[a]);!$(N-[SX4]);!$(NN);!$(NO)]([CX4])[CX4]", 0, 11.0, "base"),
    ("Tertiary amine", "[NX3H0;!$(NC=O);!$(N-[a]);!$(N-[SX4]);!$(NN);!$(NO)]([CX4])([CX4])[CX4]", 0, 9.8, "base"),
]

_COMPILED = [(name, Chem.MolFromSmarts(sma), pos, pka, kind) for name, sma, pos, pka, kind in RULES]
for _r in _COMPILED:
    assert _r[1] is not None, _r[0]

WATER_RANGE = (0.0, 14.0)


def sites(mol: Chem.Mol) -> list[dict]:
    claimed: set[int] = set()
    out = []
    for name, patt, pos, pka, kind in _COMPILED:
        for match in mol.GetSubstructMatches(patt):
            idx = match[pos]
            if idx in claimed:
                continue
            claimed.add(idx)
            out.append({
                "atom_idx": idx,
                "symbol": mol.GetAtomWithIdx(idx).GetSymbol(),
                "group": name,
                "pka": pka,
                "kind": kind,
                "in_water_range": WATER_RANGE[0] - 1 <= pka <= WATER_RANGE[1] + 1,
                "atoms": list(match),
            })
    out.sort(key=lambda s: s["pka"])
    return out


def fraction_ionised(site: dict, ph: float) -> float:
    """Fraction of the site carrying a charge at this pH (Henderson-Hasselbalch)."""
    if site["kind"] == "acid":
        return 1.0 / (1.0 + 10 ** (site["pka"] - ph))
    return 1.0 / (1.0 + 10 ** (ph - site["pka"]))


def net_charge(site_list: list[dict], ph: float, base_charge: int = 0) -> float:
    total = float(base_charge)
    for s in site_list:
        f = fraction_ionised(s, ph)
        total += -f if s["kind"] == "acid" else f
    return total


def isoelectric_point(site_list: list[dict], base_charge: int = 0) -> float | None:
    acids = [s for s in site_list if s["kind"] == "acid" and s["in_water_range"]]
    bases = [s for s in site_list if s["kind"] == "base" and s["in_water_range"]]
    if not acids or not bases:
        return None
    lo, hi = -2.0, 16.0
    if net_charge(site_list, lo, base_charge) <= 0 or net_charge(site_list, hi, base_charge) >= 0:
        return None
    for _ in range(60):
        mid = (lo + hi) / 2
        if net_charge(site_list, mid, base_charge) > 0:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 2)


def species_at(mol: Chem.Mol, site_list: list[dict], ph: float) -> Chem.Mol:
    """The dominant protonation state: each site is ionised when more than half of it is."""
    rw = Chem.RWMol(mol)
    for s in site_list:
        if fraction_ionised(s, ph) <= 0.5:
            continue
        a = rw.GetAtomWithIdx(s["atom_idx"])
        if s["kind"] == "acid":
            if a.GetTotalNumHs() < 1:
                continue
            a.SetFormalCharge(a.GetFormalCharge() - 1)
            a.SetNumExplicitHs(max(0, a.GetTotalNumHs() - 1))
            a.SetNoImplicit(True)
        else:
            a.SetFormalCharge(a.GetFormalCharge() + 1)
            a.SetNumExplicitHs(a.GetTotalNumHs() + 1)
            a.SetNoImplicit(True)
    m = rw.GetMol()
    try:
        Chem.SanitizeMol(m)
    except Exception as e:  # noqa: BLE001
        raise ChemError(f"Could not build the ionised form: {e}")
    return m


def _svg(mol: Chem.Mol, highlight: dict[int, tuple], width: int = 480, height: int = 300) -> str:
    m = Chem.Mol(mol)
    rdDepictor.Compute2DCoords(m)
    Chem.WedgeMolBonds(m, m.GetConformer())
    d = rdMolDraw2D.MolDraw2DSVG(width, height)
    opts = d.drawOptions()
    opts.clearBackground = False
    opts.bondLineWidth = 2
    opts.addStereoAnnotation = True
    d.DrawMolecule(m, highlightAtoms=sorted(highlight), highlightAtomColors=highlight, highlightBonds=[])
    d.FinishDrawing()
    return d.GetDrawingText()


def analyse(smiles: str, ph: float = 7.4) -> dict:
    mol = mol_from_smiles(smiles)
    base_charge = sum(a.GetFormalCharge() for a in mol.GetAtoms())
    site_list = sites(mol)
    for s in site_list:
        s["fraction_ionised"] = round(fraction_ionised(s, ph), 3)
    species = species_at(mol, site_list, ph)
    colours = {}
    for s in site_list:
        if s["fraction_ionised"] > 0.5:
            colours[s["atom_idx"]] = (0.86, 0.15, 0.15, 0.45) if s["kind"] == "acid" else (0.15, 0.39, 0.92, 0.45)
    charge = net_charge(site_list, ph, base_charge)
    strongest_acid = next((s for s in site_list if s["kind"] == "acid"), None)
    strongest_base = max((s for s in site_list if s["kind"] == "base"), key=lambda s: s["pka"], default=None)
    return {
        "ph": ph,
        "sites": site_list,
        "net_charge": round(charge, 2),
        "species_smiles": Chem.MolToSmiles(species, isomericSmiles=True),
        "species_svg": _svg(species, colours),
        "species_charge": sum(a.GetFormalCharge() for a in species.GetAtoms()),
        "pi": isoelectric_point(site_list, base_charge),
        "strongest_acid": strongest_acid["group"] if strongest_acid else None,
        "strongest_base": strongest_base["group"] if strongest_base else None,
        "note": "Typical pKa values for each group in water; substituent effects beyond the listed patterns are not modelled, so expect about one unit of error.",
    }
