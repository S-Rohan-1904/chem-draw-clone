"""Check a typed name or drawn molfile against a target structure."""

from __future__ import annotations

from dataclasses import dataclass

from rdkit import Chem
from rdkit.Chem import rdMolDescriptors

from . import chem


@dataclass
class Verdict:
    correct: bool
    verdict: str  # exact | stereo | wrong | unparsed
    message: str
    your_formula: str | None = None


def grade(answer: str, target_inchikey: str, target_formula: str | None = None) -> Verdict:
    try:
        resolved = chem.resolve_full(answer)
        mol = chem.mol_from_smiles(resolved.smiles)
    except chem.ChemError as e:
        what = "structure" if chem._is_molfile(answer) else "name"
        return Verdict(False, "unparsed", f"That is not a readable {what}: {str(e).split('.')[0]}.")
    key = Chem.MolToInchiKey(mol)
    formula = rdMolDescriptors.CalcMolFormula(mol)
    if key == target_inchikey:
        return Verdict(True, "exact", "Correct.", formula)
    if key.split("-")[0] == target_inchikey.split("-")[0]:
        msg = "Right skeleton, wrong or missing stereochemistry."
        if resolved.warnings:
            msg += " " + resolved.warnings[0]
        return Verdict(False, "stereo", msg, formula)
    hint = "Same formula, different connectivity." if target_formula and formula == target_formula else f"Your name gives {formula}."
    return Verdict(False, "wrong", f"Not this molecule. {hint}", formula)
