"""Isotope labelling: swap atoms (or hydrogens on an atom) for a heavier
isotope and report the exact mass shift."""

from __future__ import annotations

from rdkit import Chem
from rdkit.Chem import Descriptors, rdDepictor, rdMolDescriptors
from rdkit.Chem.Draw import rdMolDraw2D

from .chem import ChemError, mol_from_smiles

# isotope code -> (element, mass number, display)
ISOTOPES = {
    "2H": ("H", 2, "D"),
    "3H": ("H", 3, "T"),
    "13C": ("C", 13, "13C"),
    "14C": ("C", 14, "14C"),
    "15N": ("N", 15, "15N"),
    "17O": ("O", 17, "17O"),
    "18O": ("O", 18, "18O"),
    "34S": ("S", 34, "34S"),
    "37Cl": ("Cl", 37, "37Cl"),
    "81Br": ("Br", 81, "81Br"),
}


def options_for(mol: Chem.Mol) -> list[dict]:
    """Which labels each heavy atom can take: its own heavy isotopes, plus D/T for its hydrogens."""
    out = []
    for a in mol.GetAtoms():
        codes = [code for code, (el, _, _) in ISOTOPES.items() if el == a.GetSymbol()]
        hs = a.GetTotalNumHs()
        if hs:
            codes = ["2H", "3H"] + codes
        if codes:
            out.append({"atom_idx": a.GetIdx(), "symbol": a.GetSymbol(), "hs": hs, "codes": codes})
    return out


def apply_labels(smiles: str, labels: list[dict]) -> dict:
    mol = mol_from_smiles(smiles)
    base_mass = Descriptors.ExactMolWt(mol)
    rw = Chem.RWMol(mol)
    applied = []
    for lab in labels:
        idx = int(lab.get("atom_idx", -1))
        code = str(lab.get("isotope", ""))
        count = max(1, int(lab.get("count", 1)))
        if not (0 <= idx < mol.GetNumAtoms()):
            raise ChemError("No such atom.")
        if code not in ISOTOPES:
            raise ChemError(f"Unknown isotope {code}.")
        el, mass, display = ISOTOPES[code]
        atom = rw.GetAtomWithIdx(idx)
        if el == "H":
            hs = atom.GetTotalNumHs()
            if hs < 1:
                raise ChemError(f"{atom.GetSymbol()}{idx + 1} has no hydrogens to replace.")
            count = min(count, hs)
            atom.SetNumExplicitHs(hs - count)
            atom.SetNoImplicit(True)
            for _ in range(count):
                h = Chem.Atom(1)
                h.SetIsotope(mass)
                new = rw.AddAtom(h)
                rw.AddBond(idx, new, Chem.BondType.SINGLE)
            applied.append({"atom_idx": idx, "isotope": code, "count": count, "text": f"{count} x {display} on {atom.GetSymbol()}{idx + 1}"})
        else:
            if atom.GetSymbol() != el:
                raise ChemError(f"{code} cannot label a {atom.GetSymbol()} atom.")
            atom.SetIsotope(mass)
            applied.append({"atom_idx": idx, "isotope": code, "count": 1, "text": f"{display} at {atom.GetSymbol()}{idx + 1}"})
    m = rw.GetMol()
    try:
        Chem.SanitizeMol(m)
    except Exception as e:  # noqa: BLE001
        raise ChemError(f"Could not apply the labels: {e}")
    labelled_mass = Descriptors.ExactMolWt(m)
    shift = labelled_mass - base_mass
    heavy = Chem.RemoveHs(m)  # keeps isotopic H
    return {
        "smiles": Chem.MolToSmiles(heavy, isomericSmiles=True),
        "formula": rdMolDescriptors.CalcMolFormula(heavy, separateIsotopes=True).replace("[2H]", "D").replace("[3H]", "T"),
        "exact_mass": round(labelled_mass, 5),
        "base_mass": round(base_mass, 5),
        "shift": round(shift, 5),
        "nominal_shift": int(round(shift)),
        "svg": _svg(heavy),
        "applied": applied,
    }


def _svg(mol: Chem.Mol, width: int = 480, height: int = 300) -> str:
    m = Chem.Mol(mol)
    rdDepictor.Compute2DCoords(m)
    Chem.WedgeMolBonds(m, m.GetConformer())
    d = rdMolDraw2D.MolDraw2DSVG(width, height)
    opts = d.drawOptions()
    opts.clearBackground = False
    opts.bondLineWidth = 2
    opts.atomLabelDeuteriumTritium = True
    opts.isotopeLabels = True
    d.DrawMolecule(m)
    d.FinishDrawing()
    return d.GetDrawingText()
