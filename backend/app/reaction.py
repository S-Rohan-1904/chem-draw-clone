"""Reaction SMILES (reactants>agents>products) drawn with RDKit, plus a
simple atom balance check."""

from __future__ import annotations

import re
from collections import Counter

from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors, rdDepictor, rdMolDescriptors
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


_H = 190
_GAP = 28
_ARROW = 130


# Colours for atom-map numbers, cycled: the same map number gets the same
# colour on both sides of the arrow.
_MAP_COLOURS = [
    (0.86, 0.15, 0.15), (0.15, 0.39, 0.92), (0.02, 0.59, 0.41), (0.85, 0.47, 0.02), (0.49, 0.23, 0.93),
    (0.86, 0.15, 0.47), (0.03, 0.57, 0.70), (0.63, 0.32, 0.18), (0.29, 0.33, 0.39), (0.55, 0.65, 0.05),
]


def _mol_svg(mol: Chem.Mol, width: int, height: int) -> str:
    """Inner SVG (no header) of one molecule drawn into width x height.
    Mapped atoms are highlighted by map number and drawn without the :n label."""
    m = Chem.Mol(mol)
    rdDepictor.Compute2DCoords(m)
    colours = {}
    for a in m.GetAtoms():
        n = a.GetAtomMapNum()
        if n:
            colours[a.GetIdx()] = _MAP_COLOURS[(n - 1) % len(_MAP_COLOURS)] + (0.45,)
            a.SetAtomMapNum(0)
            a.SetProp("atomNote", str(n))
    drawer = rdMolDraw2D.MolDraw2DSVG(width, height)
    opts = drawer.drawOptions()
    opts.clearBackground = False
    opts.bondLineWidth = 2
    opts.fixedBondLength = 28
    opts.annotationFontScale = 0.6
    if colours:
        drawer.DrawMolecule(m, highlightAtoms=list(colours), highlightAtomColors=colours, highlightBonds=[])
    else:
        drawer.DrawMolecule(m)
    drawer.FinishDrawing()
    text = drawer.GetDrawingText()
    body = text.split("<!-- END OF HEADER -->", 1)[1]
    return body.rsplit("</svg>", 1)[0]


def _width(mol: Chem.Mol) -> int:
    return max(100, min(300, 40 + 30 * mol.GetNumHeavyAtoms()))


def _agent_label(mol: Chem.Mol) -> str:
    """H+, Cl-, or the molecular formula for anything bigger."""
    sup = str.maketrans("+-0123456789", "\u207a\u207b\u2070\u00b9\u00b2\u00b3\u2074\u2075\u2076\u2077\u2078\u2079")
    if mol.GetNumHeavyAtoms() == 1:
        a = mol.GetAtomWithIdx(0)
        q = a.GetFormalCharge()
        charge = "" if q == 0 else (("" if abs(q) == 1 else str(abs(q))) + ("+" if q > 0 else "-"))
        hs = a.GetTotalNumHs()
        return a.GetSymbol() + ("" if hs == 0 else "H" + ("" if hs == 1 else str(hs))).translate(str.maketrans("0123456789", "\u2080\u2081\u2082\u2083\u2084\u2085\u2086\u2087\u2088\u2089")) + charge.translate(sup)
    formula = rdMolDescriptors.CalcMolFormula(mol)
    return re.sub(r"(\d+)(?![+-])", lambda m: m.group(1).translate(str.maketrans("0123456789", "\u2080\u2081\u2082\u2083\u2084\u2085\u2086\u2087\u2088\u2089")), formula).translate(sup)


def draw_reaction(reactants: list[Chem.Mol], agents: list[Chem.Mol], products: list[Chem.Mol]) -> str:
    """Reactants + ... -> products as one SVG. RDKit's DrawReaction shrinks
    agents to nothing (and emits NaN paths for single-atom agents), so each
    molecule is drawn on its own and agents go as labels above the arrow."""
    parts: list[str] = []
    x = 10

    def side(mols: list[Chem.Mol]) -> None:
        nonlocal x
        for i, m in enumerate(mols):
            if i:
                parts.append(f"<text x='{x + _GAP / 2:.1f}' y='{_H / 2 + 8:.1f}' text-anchor='middle' font-size='26' fill='#374151'>+</text>")
                x += _GAP
            w = _width(m)
            parts.append(f"<g transform='translate({x},0)'>{_mol_svg(m, w, _H)}</g>")
            x += w

    side(reactants)
    x += _GAP // 2
    y = _H / 2
    parts.append(
        f"<path d='M {x + 10},{y} L {x + _ARROW - 10},{y}' stroke='#111827' stroke-width='2' fill='none'/>"
        f"<path d='M {x + _ARROW - 20},{y - 6} L {x + _ARROW - 10},{y} L {x + _ARROW - 20},{y + 6}' stroke='#111827' stroke-width='2' fill='none'/>"
    )
    if agents:
        labels = [_agent_label(m) for m in agents]
        lines = [", ".join(labels)] if len(labels) <= 2 else labels[:4]
        for j, line in enumerate(lines):
            ty = y - 14 - 18 * (len(lines) - 1 - j)
            parts.append(f"<text x='{x + _ARROW / 2:.1f}' y='{ty:.1f}' text-anchor='middle' font-size='15' font-family='sans-serif' fill='#374151'>{line}</text>")
    x += _ARROW + _GAP // 2
    side(products)
    x += 10
    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {x} {_H}' width='{x}px' height='{_H}px'>"
        + "".join(parts)
        + "</svg>"
    )


def _component(m: Chem.Mol) -> dict:
    plain = Chem.Mol(m)
    for a in plain.GetAtoms():
        a.SetAtomMapNum(0)  # map numbers are for the drawing, not the SMILES shown or opened
    return {"smiles": Chem.MolToSmiles(plain), "formula": rdMolDescriptors.CalcMolFormula(m), "mw": round(Descriptors.MolWt(m), 2)}


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
    svg = draw_reaction(reactants, agents, products)
    left, right = _counts(reactants), _counts(products)
    diff = {el: right.get(el, 0) - left.get(el, 0) for el in set(left) | set(right) if right.get(el, 0) != left.get(el, 0)}
    return {
        "svg": svg,
        "reactants": [_component(m) for m in reactants],
        "agents": [_component(m) for m in agents],
        "products": [_component(m) for m in products],
        "balanced": not diff,
        "imbalance": diff,
        "mapped": any(a.GetAtomMapNum() for m in reactants for a in m.GetAtoms()),
    }
