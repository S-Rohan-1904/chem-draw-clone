"""Resonance forms drawn on a shared 2D layout so the moving electrons are easy to see."""

from __future__ import annotations

from rdkit import Chem
from rdkit.Chem import rdDepictor
from rdkit.Chem.Draw import rdMolDraw2D

from .chem import ChemError

MAX_FORMS = 8


def resonance_forms(smiles: str) -> list[Chem.Mol]:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ChemError("Invalid SMILES.")
    flags = Chem.KEKULE_ALL | Chem.ALLOW_CHARGE_SEPARATION | Chem.ALLOW_INCOMPLETE_OCTETS
    supplier = Chem.ResonanceMolSupplier(mol, flags, 64)
    seen: set[tuple] = set()
    forms: list[Chem.Mol] = []
    for r in supplier:
        if r is None:
            continue
        # KEKULE_ALL already hands back explicit single/double bonds; drop the
        # aromatic flags so drawing shows this particular Kekule form.
        for b in r.GetBonds():
            b.SetIsAromatic(False)
        for a in r.GetAtoms():
            a.SetIsAromatic(False)
        # Same atom order everywhere: distinguish forms by bond orders and charges by index.
        key = (
            tuple(b.GetBondTypeAsDouble() for b in r.GetBonds()),
            tuple(a.GetFormalCharge() for a in r.GetAtoms()),
        )
        if key in seen:
            continue
        seen.add(key)
        forms.append(r)
        if len(forms) >= MAX_FORMS:
            break
    return forms


def resonance_svgs(smiles: str, width: int = 300, height: int = 220) -> list[dict]:
    forms = resonance_forms(smiles)
    if len(forms) < 2:
        return []
    layout = Chem.Mol(forms[0])
    rdDepictor.Compute2DCoords(layout)
    conf = layout.GetConformer()
    out = []
    for f in forms:
        m = Chem.Mol(f)
        m.RemoveAllConformers()
        m.AddConformer(Chem.Conformer(conf), assignId=True)
        drawer = rdMolDraw2D.MolDraw2DSVG(width, height)
        opts = drawer.drawOptions()
        opts.clearBackground = False
        opts.bondLineWidth = 2
        opts.prepareMolsBeforeDrawing = False
        mc = rdMolDraw2D.PrepareMolForDrawing(m, kekulize=False, addChiralHs=False)
        drawer.DrawMolecule(mc)
        drawer.FinishDrawing()
        out.append({"svg": drawer.GetDrawingText(), "smiles": Chem.MolToSmiles(f, kekuleSmiles=True)})
    return out
