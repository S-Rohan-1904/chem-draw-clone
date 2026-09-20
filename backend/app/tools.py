"""Small ChemDraw-style utilities: elemental analysis, biopolymer sequences,
a conformer ensemble with MMFF energies, and substructure / similarity
search over a list of SMILES.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from rdkit import Chem, DataStructs
from rdkit.Chem import AllChem, Descriptors, rdMolAlign, rdMolDescriptors
from rdkit.Chem import rdFingerprintGenerator

from .chem import MAX_HEAVY_ATOMS, ChemError, mol_from_smiles

# --- elemental analysis ------------------------------------------------------


def elemental(smiles: str) -> dict:
    """Mass percentage of each element, Hill order (C, H, then alphabetical)."""
    mol = Chem.AddHs(mol_from_smiles(smiles))
    pt = Chem.GetPeriodicTable()
    counts: Counter[str] = Counter(a.GetSymbol() for a in mol.GetAtoms())
    total = sum(pt.GetAtomicWeight(sym) * n for sym, n in counts.items())

    def order(sym: str) -> tuple[int, str]:
        return (0, "") if sym == "C" else (1, "") if sym == "H" else (2, sym)

    rows = []
    for sym in sorted(counts, key=order):
        n = counts[sym]
        mass = pt.GetAtomicWeight(sym) * n
        rows.append({
            "symbol": sym,
            "count": n,
            "atomic_weight": round(pt.GetAtomicWeight(sym), 4),
            "mass": round(mass, 3),
            "percent": round(100 * mass / total, 2),
        })
    return {
        "formula": rdMolDescriptors.CalcMolFormula(mol),
        "mw": round(total, 3),
        "exact_mass": round(Descriptors.ExactMolWt(mol), 4),
        "elements": rows,
    }


# --- sequences ---------------------------------------------------------------

MAX_RESIDUES = 60

# RDKit flavours: 0 L-peptide, 1 D-peptide, 2..5 RNA, 6..9 DNA (caps vary).
_FLAVOUR = {"peptide": 0, "d-peptide": 1, "rna": 2, "dna": 6}
_ALPHABET = {
    "peptide": "ACDEFGHIKLMNPQRSTVWY",
    "d-peptide": "ACDEFGHIKLMNPQRSTVWY",
    "rna": "ACGU",
    "dna": "ACGT",
}
_THREE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H",
    "ILE": "I", "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
    "TYR": "Y", "VAL": "V",
}


def _one_letter(kind: str, text: str) -> str:
    """Accept one-letter runs, three-letter codes (Ala-Gly-Ser, ALA GLY), spaces and dashes."""
    text = text.strip()
    if kind.endswith("peptide") and re.fullmatch(r"(?:[A-Za-z]{3}[\s\-]*)+", text) and len(re.sub(r"[\s\-]", "", text)) % 3 == 0:
        codes = re.findall(r"[A-Za-z]{3}", text)
        if all(c.upper() in _THREE for c in codes):
            return "".join(_THREE[c.upper()] for c in codes)
    return re.sub(r"[\s\-]", "", text).upper()


def from_sequence(kind: str, sequence: str) -> dict:
    if kind == "helm":
        mol = Chem.MolFromHELM(sequence.strip())
        if mol is None:
            raise ChemError("Could not read that HELM string. Example: PEPTIDE1{A.G.S}$$$$")
        seq = sequence.strip()
    else:
        if kind not in _FLAVOUR:
            raise ChemError("Unknown sequence type.")
        seq = _one_letter(kind, sequence)
        if not seq:
            raise ChemError("Sequence is empty.")
        bad = sorted({c for c in seq if c not in _ALPHABET[kind]})
        if bad:
            raise ChemError(f"Not a {kind.upper() if kind != 'peptide' else 'standard amino acid'} code: {', '.join(bad)}.")
        if len(seq) > MAX_RESIDUES:
            raise ChemError(f"Sequences are limited to {MAX_RESIDUES} residues.")
        mol = Chem.MolFromSequence(seq, flavor=_FLAVOUR[kind])
        if mol is None:
            raise ChemError("Could not build that sequence.")
    if mol.GetNumHeavyAtoms() > MAX_HEAVY_ATOMS:
        raise ChemError(
            f"That sequence has {mol.GetNumHeavyAtoms()} heavy atoms; the viewer handles up to {MAX_HEAVY_ATOMS} "
            f"(about {MAX_HEAVY_ATOMS // 8} amino acids or {MAX_HEAVY_ATOMS // 21} nucleotides)."
        )
    smiles = Chem.MolToSmiles(mol, isomericSmiles=True)
    return {
        "kind": kind,
        "sequence": seq,
        "residues": len(seq) if kind != "helm" else None,
        "smiles": smiles,
        "formula": rdMolDescriptors.CalcMolFormula(mol),
        "mw": round(Descriptors.MolWt(mol), 2),
        "heavy_atoms": mol.GetNumHeavyAtoms(),
    }


# --- conformer ensemble ------------------------------------------------------

MAX_CONF_HEAVY = 40


def conformers(smiles: str, n: int = 8) -> dict:
    """Embed up to ``n`` distinct conformers, minimise each with MMFF94 and
    report energies relative to the lowest, plus heavy-atom RMSD to it."""
    mol = mol_from_smiles(smiles)
    if mol.GetNumHeavyAtoms() > MAX_CONF_HEAVY:
        raise ChemError(f"Conformer search is limited to {MAX_CONF_HEAVY} heavy atoms.")
    mh = Chem.AddHs(mol)
    ps = AllChem.ETKDGv3()
    ps.randomSeed = 7
    ps.pruneRmsThresh = 0.3
    ps.enforceChirality = True
    ps.numThreads = 1
    cids = list(AllChem.EmbedMultipleConfs(mh, numConfs=max(2 * n, 8), params=ps))
    if not cids:
        raise ChemError("Could not embed any conformer.")
    props = AllChem.MMFFGetMoleculeProperties(mh)
    field = "MMFF94" if props is not None else "UFF"
    energies: list[tuple[float, int]] = []
    for cid in cids:
        if props is not None:
            ff = AllChem.MMFFGetMoleculeForceField(mh, props, confId=cid)
        else:
            ff = AllChem.UFFGetMoleculeForceField(mh, confId=cid)
        ff.Minimize(maxIts=500)
        energies.append((ff.CalcEnergy(), cid))
    energies.sort()
    # Minimisation can collapse different starts onto one minimum; keep unique ones.
    heavy = Chem.RemoveHs(mh)
    kept: list[tuple[float, int]] = []
    for e, cid in energies:
        if any(abs(e - e2) < 0.05 and rdMolAlign.GetBestRMS(heavy, heavy, cid2, cid) < 0.3 for e2, cid2 in kept):
            continue
        kept.append((e, cid))
        if len(kept) >= n:
            break
    e0, cid0 = kept[0]
    rows = []
    for i, (e, cid) in enumerate(kept):
        rms = 0.0
        if i:
            rms = rdMolAlign.GetBestRMS(heavy, heavy, cid0, cid)
            rdMolAlign.AlignMol(mh, mh, prbCid=cid, refCid=cid0)  # same frame as the lowest one for the viewer
        rows.append({
            "id": i,
            "energy": round(e, 2),
            "relative": round(e - e0, 2),
            "rmsd": round(rms, 2),
            "molblock": Chem.MolToMolBlock(mh, confId=cid),
        })
    # Boltzmann weights at 298 K, kcal/mol.
    kt = 0.593
    weights = [math.exp(-r["relative"] / kt) for r in rows]
    z = sum(weights)
    for r, w in zip(rows, weights):
        r["population"] = round(100 * w / z, 1)
    return {
        "force_field": field,
        "embedded": len(cids),
        "conformers": rows,
        "note": f"{len(cids)} starting geometries (ETKDG), each minimised with {field}; duplicates merged. Energies are gas-phase and relative to the lowest conformer; populations assume a Boltzmann distribution at 298 K.",
    }


def minimise(molblock: str) -> dict:
    """Energy of the given 3D geometry before and after MMFF minimisation."""
    mol = Chem.MolFromMolBlock(molblock, removeHs=False)
    if mol is None or mol.GetNumConformers() == 0:
        raise ChemError("No 3D geometry available.")
    props = AllChem.MMFFGetMoleculeProperties(mol)
    if props is None:
        ff = AllChem.UFFGetMoleculeForceField(mol)
        field = "UFF"
    else:
        ff = AllChem.MMFFGetMoleculeForceField(mol, props)
        field = "MMFF94"
    before = ff.CalcEnergy()
    converged = ff.Minimize(maxIts=2000) == 0
    after = ff.CalcEnergy()
    return {
        "force_field": field,
        "before": round(before, 2),
        "after": round(after, 2),
        "converged": converged,
        "molblock": Chem.MolToMolBlock(mol),
    }


# --- search ------------------------------------------------------------------

_morgan = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)


def search(query: str, items: list[tuple[int, str]], mode: str = "auto", limit: int = 50) -> dict:
    """Substructure (SMARTS or SMILES) or Tanimoto similarity over (id, smiles).

    mode 'auto': substructure when the query parses as SMARTS/SMILES and any
    item contains it, otherwise similarity. Returns rows sorted best first.
    """
    q = query.strip()
    if not q:
        raise ChemError("Empty query.")
    patt = Chem.MolFromSmarts(q)
    qmol = Chem.MolFromSmiles(q)
    if patt is None and qmol is None:
        raise ChemError("Query is not a valid SMILES or SMARTS.")
    if mode not in ("auto", "substructure", "similarity"):
        raise ChemError("Unknown search mode.")

    mols = [(i, Chem.MolFromSmiles(s)) for i, s in items]
    mols = [(i, m) for i, m in mols if m is not None]

    sub_hits: list[dict] = []
    if patt is not None and mode != "similarity":
        for i, m in mols:
            match = m.GetSubstructMatch(patt)
            if match:
                sub_hits.append({"id": i, "score": 1.0, "atoms": list(match)})
    if mode == "substructure" or (mode == "auto" and sub_hits):
        return {"mode": "substructure", "hits": sub_hits[:limit]}

    if qmol is None:
        raise ChemError("Similarity search needs a SMILES query.")
    qfp = _morgan.GetFingerprint(qmol)
    sims = []
    for i, m in mols:
        s = DataStructs.TanimotoSimilarity(qfp, _morgan.GetFingerprint(m))
        sims.append({"id": i, "score": round(s, 3), "atoms": []})
    sims.sort(key=lambda r: -r["score"])
    return {"mode": "similarity", "hits": [r for r in sims if r["score"] > 0][:limit]}
