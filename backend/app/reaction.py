"""Reaction SMILES (reactants>agents>products) drawn with RDKit, plus a
simple atom balance check."""

from __future__ import annotations

from collections import Counter

from rdkit import Chem
from rdkit.Chem import AllChem, rdMolDescriptors
from rdkit.Chem.Draw import rdMolDraw2D

from .chem import ChemError


def is_reaction(text: str) -> bool:
    return ">" in text and " " not in text.strip()


def _counts(mols) -> Counter:
    total: Counter = Counter()
    for m in mols:
        mh = Chem.AddHs(m)
        for a in mh.GetAtoms():
            total[a.GetSymbol()] += 1
    return total


def parse_reaction(text: str) -> dict:
    try:
        rxn = AllChem.ReactionFromSmarts(text.strip(), useSmiles=True)
    except Exception as e:  # noqa: BLE001
        raise ChemError(f"Could not read the reaction: {e}")
    if rxn is None or rxn.GetNumReactantTemplates() == 0 or rxn.GetNumProductTemplates() == 0:
        raise ChemError("A reaction needs at least one reactant and one product: reactants>>products.")
    reactants = [Chem.Mol(m) for m in rxn.GetReactants()]
    products = [Chem.Mol(m) for m in rxn.GetProducts()]
    agents = [Chem.Mol(m) for m in rxn.GetAgents()]
    for m in reactants + products + agents:
        try:
            m.UpdatePropertyCache(strict=False)
            Chem.SanitizeMol(m)
        except Exception as e:  # noqa: BLE001
            raise ChemError(f"A component of the reaction is not a valid molecule: {e}")
    rxn.Initialize()
    drawer = rdMolDraw2D.MolDraw2DSVG(900, 300)
    opts = drawer.drawOptions()
    opts.clearBackground = False
    opts.bondLineWidth = 2
    drawer.DrawReaction(rxn, highlightByReactant=True)
    drawer.FinishDrawing()
    left, right = _counts(reactants), _counts(products)
    diff = {el: right.get(el, 0) - left.get(el, 0) for el in set(left) | set(right) if right.get(el, 0) != left.get(el, 0)}
    return {
        "svg": drawer.GetDrawingText(),
        "reactants": [{"smiles": Chem.MolToSmiles(m), "formula": rdMolDescriptors.CalcMolFormula(m)} for m in reactants],
        "agents": [{"smiles": Chem.MolToSmiles(m), "formula": rdMolDescriptors.CalcMolFormula(m)} for m in agents],
        "products": [{"smiles": Chem.MolToSmiles(m), "formula": rdMolDescriptors.CalcMolFormula(m)} for m in products],
        "balanced": not diff,
        "imbalance": diff,
        "mapped": any(a.GetAtomMapNum() for m in reactants for a in m.GetAtoms()),
    }
