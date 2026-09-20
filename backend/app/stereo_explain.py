"""Explain an R/S or E/Z assignment: CIP priorities of the substituents and
the rule applied, plus a depiction with the priorities drawn on."""

from __future__ import annotations

from rdkit import Chem
from rdkit.Chem import rdCIPLabeler, rdDepictor
from rdkit.Chem.Draw import rdMolDraw2D

from .chem import ChemError


def _describe(atom: Chem.Atom, exclude: int) -> str:
    """'O (H)' style: the atom and what it carries, for the priority table."""
    nbrs = sorted(
        (n.GetSymbol() for n in atom.GetNeighbors() if n.GetIdx() != exclude),
        key=lambda s: (-Chem.GetPeriodicTable().GetAtomicNumber(s), s),
    )
    hs = ["H"] * atom.GetTotalNumHs()
    inner = ",".join(nbrs + hs)
    return f"{atom.GetSymbol()} ({inner})" if inner else atom.GetSymbol()


def _ranked(mol: Chem.Mol, centre: int, exclude: int | None = None) -> list[Chem.Atom]:
    """Neighbours of `centre` ordered by CIP priority (highest first)."""
    a = mol.GetAtomWithIdx(centre)
    nbrs = [n for n in a.GetNeighbors() if n.GetIdx() != exclude]
    return sorted(nbrs, key=lambda n: -int(n.GetProp("_CIPRank")))


def _prepare(smiles: str) -> Chem.Mol:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ChemError("Invalid SMILES.")
    Chem.AssignStereochemistry(mol, cleanIt=True, force=True, flagPossibleStereoCenters=True)
    rdCIPLabeler.AssignCIPLabels(mol)
    return mol


def _draw(mol: Chem.Mol, notes: dict[int, str], highlight: list[int], colour=(0.15, 0.39, 0.92, 0.35)) -> str:
    m = Chem.Mol(mol)
    rdDepictor.Compute2DCoords(m)
    Chem.WedgeMolBonds(m, m.GetConformer())
    for idx, note in notes.items():
        m.GetAtomWithIdx(idx).SetProp("atomNote", note)
    drawer = rdMolDraw2D.MolDraw2DSVG(480, 360)
    opts = drawer.drawOptions()
    opts.addStereoAnnotation = True
    opts.clearBackground = False
    opts.bondLineWidth = 2
    opts.annotationFontScale = 0.9
    drawer.DrawMolecule(m, highlightAtoms=highlight, highlightAtomColors={i: colour for i in highlight})
    drawer.FinishDrawing()
    return drawer.GetDrawingText()


def explain_centre(smiles: str, idx: int) -> dict:
    mol = _prepare(smiles)
    if idx < 0 or idx >= mol.GetNumAtoms():
        raise ChemError("No such atom.")
    atom = mol.GetAtomWithIdx(idx)
    label = atom.GetPropsAsDict().get("_CIPCode", "")
    if not label:
        raise ChemError("That atom is not a labelled stereocentre.")
    ranked = _ranked(mol, idx)
    rows = [
        {"priority": i + 1, "atom_idx": n.GetIdx(), "symbol": n.GetSymbol(), "group": _describe(n, idx)}
        for i, n in enumerate(ranked)
    ]
    has_h = atom.GetTotalNumHs() > 0
    if has_h:
        rows.append({"priority": len(rows) + 1, "atom_idx": None, "symbol": "H", "group": "H (implicit)"})
    lowest = rows[-1]
    direction = "clockwise" if label.upper() == "R" else "anticlockwise"
    steps = [
        "Rank the four substituents by CIP priority: higher atomic number first; on a tie, "
        "compare the atoms attached to each substituent (duplicated for double bonds).",
        f"Lowest priority is {lowest['group']}; view the centre with it pointing away from you.",
        f"Trace 1 to 2 to 3: the path runs {direction}, so the centre is {label.upper()}.",
    ]
    if label.islower():
        steps.append("Lowercase r/s: pseudo-asymmetric centre, two substituents differ only by their own configuration.")
    notes = {r["atom_idx"]: str(r["priority"]) for r in rows if r["atom_idx"] is not None}
    return {
        "kind": "centre",
        "atom_idx": idx,
        "label": label,
        "priorities": rows,
        "has_h": has_h,
        "steps": steps,
        "svg": _draw(mol, notes, [idx]),
    }


def explain_double_bond(smiles: str, bond_idx: int) -> dict:
    mol = _prepare(smiles)
    if bond_idx < 0 or bond_idx >= mol.GetNumBonds():
        raise ChemError("No such bond.")
    bond = mol.GetBondWithIdx(bond_idx)
    label = bond.GetPropsAsDict().get("_CIPCode", "")
    if not label:
        raise ChemError("That bond is not a labelled stereogenic double bond.")
    a, b = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
    ends = []
    notes: dict[int, str] = {}
    for end, other in ((a, b), (b, a)):
        ranked = _ranked(mol, end, exclude=other)
        rows = [
            {"priority": i + 1, "atom_idx": n.GetIdx(), "symbol": n.GetSymbol(), "group": _describe(n, end)}
            for i, n in enumerate(ranked)
        ]
        if mol.GetAtomWithIdx(end).GetTotalNumHs() > 0:
            rows.append({"priority": len(rows) + 1, "atom_idx": None, "symbol": "H", "group": "H (implicit)"})
        ends.append({"atom_idx": end, "substituents": rows})
        for r in rows:
            if r["atom_idx"] is not None:
                notes[r["atom_idx"]] = f"{r['priority']}{'a' if end == a else 'b'}"
    side = "the same side" if label.upper() == "Z" else "opposite sides"
    steps = [
        "On each end of the double bond, rank the two substituents by CIP priority (1 = higher).",
        f"The two priority-1 groups (1a and 1b) lie on {side} of the double bond, so it is {label.upper()}"
        + (" (zusammen, together)." if label.upper() == "Z" else " (entgegen, opposite)."),
    ]
    return {
        "kind": "bond",
        "bond_idx": bond_idx,
        "atoms": [a, b],
        "label": label,
        "ends": ends,
        "steps": steps,
        "svg": _draw(mol, notes, [a, b], colour=(0.02, 0.47, 0.34, 0.35)),
    }
