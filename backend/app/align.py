"""Overlay two molecules on their maximum common substructure and report RMSD."""

from __future__ import annotations

from rdkit import Chem
from rdkit.Chem import rdFMCS, rdMolAlign

from .chem import ChemError


def align(molblock_a: str, molblock_b: str) -> dict:
    ma = Chem.MolFromMolBlock(molblock_a, removeHs=False)
    mb = Chem.MolFromMolBlock(molblock_b, removeHs=False)
    if ma is None or mb is None:
        raise ChemError("Could not read the 3D models.")
    ha, hb = Chem.RemoveHs(ma), Chem.RemoveHs(mb)
    mcs = rdFMCS.FindMCS([ha, hb], timeout=5, ringMatchesRingOnly=True, completeRingsOnly=False, matchValences=False)
    if mcs.numAtoms < 3:
        raise ChemError("The molecules share fewer than three atoms; nothing to overlay.")
    patt = Chem.MolFromSmarts(mcs.smartsString)
    ia, ib = ha.GetSubstructMatch(patt), hb.GetSubstructMatch(patt)
    # Heavy-atom indices are the first atoms of the H-added mol blocks, so the
    # map carries over to the models with hydrogens.
    rms = rdMolAlign.AlignMol(mb, ma, atomMap=list(zip(ib, ia)))
    identical = Chem.MolToSmiles(ha, isomericSmiles=False) == Chem.MolToSmiles(hb, isomericSmiles=False)
    return {
        "rmsd": round(float(rms), 3),
        "common_atoms": mcs.numAtoms,
        "common_bonds": mcs.numBonds,
        "heavy_a": ha.GetNumAtoms(),
        "heavy_b": hb.GetNumAtoms(),
        "identical_connectivity": identical,
        "molblock_a": molblock_a,
        "molblock_b": Chem.MolToMolBlock(mb),
        "mcs_smarts": mcs.smartsString,
        "atoms_a": list(ia),
        "atoms_b": list(ib),
    }
