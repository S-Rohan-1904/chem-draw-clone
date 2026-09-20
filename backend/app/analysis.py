"""Structure and bonding analysis for the Bonding card: oxidation states,
bond polarity and dipole, VSEPR shapes, ring aromaticity, degrees of
unsaturation, chirality class (chiral / achiral / meso) and hydrogen
bonding with a solubility estimate.

Atom indices refer to the canonical SMILES of the molecule, as everywhere
else in the app.
"""

from __future__ import annotations

import math

import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem, Crippen, Descriptors, Lipinski, rdDepictor, rdMolDescriptors, rdMolTransforms
from rdkit.Chem.Draw import rdMolDraw2D

from .chem import ChemError, mol_from_smiles

# Pauling electronegativities.
EN = {
    "H": 2.20, "Li": 0.98, "Be": 1.57, "B": 2.04, "C": 2.55, "N": 3.04, "O": 3.44, "F": 3.98,
    "Na": 0.93, "Mg": 1.31, "Al": 1.61, "Si": 1.90, "P": 2.19, "S": 2.58, "Cl": 3.16,
    "K": 0.82, "Ca": 1.00, "Zn": 1.65, "Ga": 1.81, "Ge": 2.01, "As": 2.18, "Se": 2.55, "Br": 2.96,
    "Sn": 1.96, "Sb": 2.05, "Te": 2.10, "I": 2.66, "Fe": 1.83, "Cu": 1.90, "Ag": 1.93, "Hg": 2.00,
}

_HALOGENS = {"F", "Cl", "Br", "I"}


def _kekule(mol: Chem.Mol) -> Chem.Mol:
    k = Chem.Mol(mol)
    Chem.Kekulize(k, clearAromaticFlags=True)
    return k


def _draw(mol: Chem.Mol, *, notes: dict[int, str] | None = None, atom_colours: dict[int, tuple] | None = None,
          bond_colours: dict[int, tuple] | None = None, width: int = 480, height: int = 360) -> str:
    m = Chem.Mol(mol)
    rdDepictor.Compute2DCoords(m)
    Chem.WedgeMolBonds(m, m.GetConformer())
    for idx, text in (notes or {}).items():
        m.GetAtomWithIdx(idx).SetProp("atomNote", text)
    d = rdMolDraw2D.MolDraw2DSVG(width, height)
    opts = d.drawOptions()
    opts.clearBackground = False
    opts.bondLineWidth = 2
    opts.annotationFontScale = 0.65
    d.DrawMolecule(
        m,
        highlightAtoms=sorted(atom_colours or {}),
        highlightBonds=sorted(bond_colours or {}),
        highlightAtomColors=atom_colours or {},
        highlightBondColors=bond_colours or {},
    )
    d.FinishDrawing()
    return d.GetDrawingText()


def _rgba(hex_colour: str, alpha: float = 0.4) -> tuple:
    return tuple(int(hex_colour.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)) + (alpha,)


# --- oxidation states ------------------------------------------------------

def oxidation_states(mol: Chem.Mol) -> list[dict]:
    """Oxidation number of every heavy atom: each bond's electrons go to the
    more electronegative partner; bonds between like atoms are split."""
    k = _kekule(mol)
    out = []
    for a in k.GetAtoms():
        sym = a.GetSymbol()
        en = EN.get(sym, 2.0)
        ox = a.GetFormalCharge()
        parts = []
        for b in a.GetBonds():
            nb = b.GetOtherAtom(a)
            en_nb = EN.get(nb.GetSymbol(), 2.0)
            order = int(b.GetBondTypeAsDouble())
            if en_nb > en:
                ox += order
                parts.append(f"+{order} ({nb.GetSymbol()} more electronegative)")
            elif en_nb < en:
                ox -= order
                parts.append(f"-{order} ({nb.GetSymbol()} less electronegative)")
        hs = a.GetTotalNumHs()
        if hs:
            if EN["H"] < en:
                ox -= hs
                parts.append(f"-{hs} (H)")
            elif EN["H"] > en:
                ox += hs
                parts.append(f"+{hs} (H)")
        if a.GetFormalCharge():
            parts.append(f"{a.GetFormalCharge():+d} (formal charge)")
        out.append({"idx": a.GetIdx(), "symbol": sym, "oxidation_state": ox, "formal_charge": a.GetFormalCharge(), "terms": parts})
    return out


def _ox_label(n: int) -> str:
    return "0" if n == 0 else f"{n:+d}"


# --- bond polarity and dipole ----------------------------------------------

def bond_polarity(mol: Chem.Mol) -> list[dict]:
    out = []
    for b in mol.GetBonds():
        a1, a2 = b.GetBeginAtom(), b.GetEndAtom()
        e1, e2 = EN.get(a1.GetSymbol(), 2.0), EN.get(a2.GetSymbol(), 2.0)
        d = abs(e1 - e2)
        cls = "nonpolar" if d < 0.4 else "polar" if d < 1.7 else "ionic"
        neg = a1.GetIdx() if e1 > e2 else a2.GetIdx() if e2 > e1 else None
        out.append({
            "bond_idx": b.GetIdx(),
            "atoms": [a1.GetIdx(), a2.GetIdx()],
            "label": f"{a1.GetSymbol()}{a1.GetIdx() + 1}-{a2.GetSymbol()}{a2.GetIdx() + 1}",
            "delta_en": round(d, 2),
            "class": cls,
            "negative_end": neg,
        })
    return out


def _ch_polarity(mol: Chem.Mol) -> dict | None:
    if not any(a.GetTotalNumHs() for a in mol.GetAtoms() if a.GetSymbol() == "C"):
        return None
    d = round(EN["C"] - EN["H"], 2)
    return {"label": "C-H", "delta_en": d, "class": "nonpolar"}


def dipole(molblock: str) -> dict | None:
    """Dipole from Gasteiger partial charges on the 3D conformer. Rough, but
    the direction and the zero for symmetric molecules are right."""
    mh = Chem.MolFromMolBlock(molblock, removeHs=False)
    if mh is None or mh.GetNumConformers() == 0:
        return None
    try:
        AllChem.ComputeGasteigerCharges(mh)
    except Exception:  # noqa: BLE001
        return None
    pos = mh.GetConformer().GetPositions()
    q = np.array([float(a.GetProp("_GasteigerCharge")) for a in mh.GetAtoms()])
    if not np.all(np.isfinite(q)):
        return None
    centre = pos.mean(axis=0)
    mu = ((pos - centre) * q[:, None]).sum(axis=0)  # e * Angstrom
    debye = float(np.linalg.norm(mu) * 4.80320)
    return {
        "debye": round(debye, 2),
        "vector": [round(float(x), 3) for x in mu],
        "centre": [round(float(x), 3) for x in centre],
        "net_charge": int(round(q.sum())),
    }


# --- VSEPR ----------------------------------------------------------------

_SHAPES = {
    (2, 0): ("linear", 180.0),
    (3, 0): ("trigonal planar", 120.0),
    (3, 1): ("bent", 120.0),
    (4, 0): ("tetrahedral", 109.5),
    (4, 1): ("trigonal pyramidal", 107.0),
    (4, 2): ("bent", 104.5),
    (5, 0): ("trigonal bipyramidal", 120.0),
    (5, 1): ("seesaw", 120.0),
    (5, 2): ("T-shaped", 90.0),
    (5, 3): ("linear", 180.0),
    (6, 0): ("octahedral", 90.0),
    (6, 1): ("square pyramidal", 90.0),
    (6, 2): ("square planar", 90.0),
}
_DOMAINS = {
    Chem.HybridizationType.SP: 2,
    Chem.HybridizationType.SP2: 3,
    Chem.HybridizationType.SP3: 4,
    Chem.HybridizationType.SP3D: 5,
    Chem.HybridizationType.SP3D2: 6,
}


def _mean_angle(mh: Chem.Mol, idx: int) -> float | None:
    conf = mh.GetConformer()
    nbrs = [n.GetIdx() for n in mh.GetAtomWithIdx(idx).GetNeighbors()]
    if len(nbrs) < 2:
        return None
    angles = []
    for i in range(len(nbrs)):
        for j in range(i + 1, len(nbrs)):
            angles.append(rdMolTransforms.GetAngleDeg(conf, nbrs[i], idx, nbrs[j]))
    # For 5 and 6 domains the mean mixes 90 and 120/180; report the smallest instead.
    return round(min(angles) if len(nbrs) >= 5 else sum(angles) / len(angles), 1)


def vsepr(mol: Chem.Mol, molblock: str | None = None) -> list[dict]:
    mh = Chem.MolFromMolBlock(molblock, removeHs=False) if molblock else None
    out = []
    for a in mol.GetAtoms():
        n = a.GetDegree() + a.GetTotalNumHs()
        if n < 2:
            continue
        hyb = a.GetHybridization()
        domains = _DOMAINS.get(hyb)
        if a.GetIsAromatic():
            domains = 3
        elif a.GetSymbol() in ("O", "S") and n == 2 and hyb == Chem.HybridizationType.SP2:
            domains = 4  # ether-type oxygen: conjugation flattens it a little, but it stays bent near 105
        if domains is None or domains < n:
            domains = n
        lone = domains - n
        shape, ideal = _SHAPES.get((domains, lone), ("", None))
        if not shape:
            continue
        note = ""
        if hyb == Chem.HybridizationType.SP2 and a.GetSymbol() in ("N", "O", "S") and lone == 0 and n == 3:
            note = "lone pair delocalised in a p orbital"
        measured = _mean_angle(mh, a.GetIdx()) if mh is not None else None
        out.append({
            "idx": a.GetIdx(),
            "symbol": a.GetSymbol(),
            "domains": domains,
            "bonded": n,
            "lone_pairs": lone,
            "shape": shape,
            "ideal_angle": ideal,
            "model_angle": measured,
            "note": note,
        })
    return out


# --- aromaticity ----------------------------------------------------------

def ring_aromaticity(mol: Chem.Mol) -> list[dict]:
    k = _kekule(mol)
    rings = []
    for ring in mol.GetRingInfo().AtomRings():
        ring_set = set(ring)
        pi = 0
        conjugated = True
        details = []
        for idx in ring:
            a = k.GetAtomWithIdx(idx)
            sym = a.GetSymbol()
            ring_double = any(b.GetBondType() == Chem.BondType.DOUBLE and b.GetOtherAtomIdx(idx) in ring_set for b in a.GetBonds())
            exo_double = any(b.GetBondType() in (Chem.BondType.DOUBLE, Chem.BondType.TRIPLE) and b.GetOtherAtomIdx(idx) not in ring_set for b in a.GetBonds())
            charge = a.GetFormalCharge()
            pt = Chem.GetPeriodicTable()
            valence_e = pt.GetNOuterElecs(a.GetAtomicNum())
            bonding_e = int(round(sum(b.GetBondTypeAsDouble() for b in a.GetBonds()))) + a.GetTotalNumHs()
            lone = max(0, (valence_e - charge - bonding_e) // 2)
            if ring_double:
                pi += 1
                details.append(f"{sym}{idx + 1}: 1 (double bond)")
            elif exo_double:
                details.append(f"{sym}{idx + 1}: 0 (exocyclic double bond)")
            elif charge > 0 and sym == "C":
                details.append(f"{sym}{idx + 1}: 0 (empty p orbital)")
            elif lone > 0:
                pi += 2
                details.append(f"{sym}{idx + 1}: 2 (lone pair)")
            else:
                conjugated = False
                details.append(f"{sym}{idx + 1}: sp3, breaks conjugation")
        aromatic = all(mol.GetBondBetweenAtoms(ring[i], ring[(i + 1) % len(ring)]).GetIsAromatic() for i in range(len(ring)))
        if aromatic:
            n = (pi - 2) // 4
            verdict = f"aromatic: {pi} pi electrons = 4n+2 with n = {n}, planar and fully conjugated"
        elif not conjugated:
            verdict = "not aromatic: an sp3 atom breaks the conjugation"
        elif pi % 4 == 2:
            verdict = f"{pi} pi electrons fit 4n+2 but the ring is not perceived as aromatic (usually not planar)"
        elif pi % 4 == 0:
            verdict = f"{pi} pi electrons = 4n: antiaromatic if planar; larger rings twist out of plane and are simply non-aromatic"
        else:
            verdict = f"{pi} pi electrons: an odd count, not aromatic"
        rings.append({"atoms": list(ring), "size": len(ring), "pi_electrons": pi, "aromatic": aromatic, "conjugated": conjugated, "verdict": verdict, "details": details})
    return rings


# --- degrees of unsaturation ------------------------------------------------

def unsaturation(mol: Chem.Mol) -> dict:
    mh = Chem.AddHs(mol)
    counts: dict[str, int] = {}
    for a in mh.GetAtoms():
        counts[a.GetSymbol()] = counts.get(a.GetSymbol(), 0) + 1
    c = counts.get("C", 0)
    h = counts.get("H", 0)
    n = counts.get("N", 0) + counts.get("P", 0)
    x = sum(counts.get(el, 0) for el in _HALOGENS)
    dbe = (2 * c + 2 + n - h - x) / 2
    k = _kekule(mol)
    rings = mol.GetRingInfo().NumRings()
    doubles = sum(1 for b in k.GetBonds() if b.GetBondType() == Chem.BondType.DOUBLE)
    triples = sum(1 for b in k.GetBonds() if b.GetBondType() == Chem.BondType.TRIPLE)
    parts = []
    if rings:
        parts.append(f"{rings} ring{'s' if rings != 1 else ''}")
    if doubles:
        parts.append(f"{doubles} double bond{'s' if doubles != 1 else ''}")
    if triples:
        parts.append(f"{triples} triple bond{'s' if triples != 1 else ''} (2 each)")
    structural = rings + doubles + 2 * triples
    formula_terms = f"C {c}, H {h}" + (f", N {n}" if n else "") + (f", halogen {x}" if x else "")
    aromatic_rings = rdMolDescriptors.CalcNumAromaticRings(mol)
    note = ""
    if aromatic_rings:
        note = f"Each benzene-type ring counts 4: 1 ring + 3 double bonds."
    other = {el for el in counts if el not in ("C", "H", "N", "O", "P", "S", *_HALOGENS)}
    if other:
        note = (note + " " if note else "") + f"Formula count ignores {', '.join(sorted(other))}."
    return {
        "dbe": dbe,
        "from_formula": f"(2 x {c} + 2 + {n} - {h} - {x}) / 2 = {dbe:g}",
        "formula_terms": formula_terms,
        "rings": rings,
        "double_bonds": doubles,
        "triple_bonds": triples,
        "structural": structural,
        "breakdown": " + ".join(parts) if parts else "no rings or multiple bonds",
        "consistent": abs(structural - dbe) < 1e-6,
        "note": note,
    }


# --- chirality class -------------------------------------------------------

_INVERT = {
    Chem.ChiralType.CHI_TETRAHEDRAL_CW: Chem.ChiralType.CHI_TETRAHEDRAL_CCW,
    Chem.ChiralType.CHI_TETRAHEDRAL_CCW: Chem.ChiralType.CHI_TETRAHEDRAL_CW,
}


def chirality_class(mol: Chem.Mol) -> dict:
    from .chem import _cip_labels, _unspecified_centres

    centres = [a.GetIdx() for a in mol.GetAtoms() if a.GetChiralTag() in _INVERT]
    unspecified = _unspecified_centres(mol)
    labels = _cip_labels(mol)
    if unspecified:
        return {
            "kind": "unknown",
            "title": "Cannot decide yet",
            "reason": f"{len(unspecified)} stereocentre{'s are' if len(unspecified) != 1 else ' is'} unspecified. Give every centre a descriptor in the name and the app will classify the molecule.",
            "centres": centres,
            "unspecified": unspecified,
            "pairs": [],
        }
    if not centres:
        # Axial or planar chirality (allenes, atropisomers) is not handled here.
        return {
            "kind": "achiral",
            "title": "Achiral",
            "reason": "No stereocentres, so the molecule and its mirror image are the same compound.",
            "centres": [],
            "unspecified": [],
            "pairs": [],
        }
    mirror = Chem.Mol(mol)
    for idx in centres:
        a = mirror.GetAtomWithIdx(idx)
        a.SetChiralTag(_INVERT[a.GetChiralTag()])
    Chem.AssignStereochemistry(mirror, cleanIt=True, force=True)
    same = Chem.MolToSmiles(mirror, isomericSmiles=True) == Chem.MolToSmiles(mol, isomericSmiles=True)
    label_text = ", ".join(f"{mol.GetAtomWithIdx(i).GetSymbol()}{i + 1} {labels.get(f'a{i}', '?')}" for i in centres)
    if not same:
        return {
            "kind": "chiral",
            "title": "Chiral",
            "reason": f"Inverting every centre ({label_text}) gives a different molecule, the enantiomer. The mirror image cannot be superimposed on the original.",
            "centres": centres,
            "unspecified": [],
            "pairs": [],
        }
    # Meso: stereocentres present, yet mirror image identical. Find the equivalent centre pairs.
    plain = Chem.Mol(mol)
    Chem.RemoveStereochemistry(plain)
    ranks = list(Chem.CanonicalRankAtoms(plain, breakTies=False))
    pairs = []
    seen: set[int] = set()
    for i in centres:
        for j in centres:
            if j <= i or i in seen or j in seen:
                continue
            if ranks[i] == ranks[j] and labels.get(f"a{i}") and labels.get(f"a{i}") != labels.get(f"a{j}"):
                pairs.append([i, j])
                seen.update((i, j))
    pair_text = "; ".join(f"{mol.GetAtomWithIdx(i).GetSymbol()}{i + 1} ({labels.get(f'a{i}')}) and {mol.GetAtomWithIdx(j).GetSymbol()}{j + 1} ({labels.get(f'a{j}')})" for i, j in pairs)
    reason = "Stereocentres are present, but the mirror image is the same molecule."
    if pairs:
        reason += f" The equivalent centres {pair_text} carry opposite descriptors, so one half of the molecule mirrors the other: an internal mirror plane or inversion centre makes it superimposable on its mirror image."
    else:
        reason += " A symmetry element relates the centres to each other."
    return {
        "kind": "meso",
        "title": "Meso (achiral)",
        "reason": reason,
        "centres": centres,
        "unspecified": [],
        "pairs": pairs,
    }


# --- hydrogen bonding and solubility --------------------------------------

_DONOR = Lipinski.HDonorSmarts
_ACCEPTOR = Lipinski.HAcceptorSmarts


def hbond_sites(mol: Chem.Mol) -> dict:
    donors = sorted({m[0] for m in mol.GetSubstructMatches(_DONOR)})
    acceptors = sorted({m[0] for m in mol.GetSubstructMatches(_ACCEPTOR)})
    both = sorted(set(donors) & set(acceptors))
    colours: dict[int, tuple] = {}
    for i in donors:
        colours[i] = _rgba("#2563eb", 0.45)
    for i in acceptors:
        colours[i] = _rgba("#dc2626", 0.45)
    for i in both:
        colours[i] = _rgba("#7c3aed", 0.45)
    return {
        "donors": donors,
        "acceptors": acceptors,
        "both": both,
        "svg": _draw(mol, atom_colours=colours),
    }


def solubility(mol: Chem.Mol) -> dict:
    """ESOL (Delaney 2004) estimate of aqueous solubility."""
    logp = Crippen.MolLogP(mol)
    mw = Descriptors.MolWt(mol)
    rb = rdMolDescriptors.CalcNumRotatableBonds(mol)
    heavy = mol.GetNumHeavyAtoms()
    arom = sum(1 for a in mol.GetAtoms() if a.GetIsAromatic()) / heavy if heavy else 0.0
    logs = 0.16 - 0.63 * logp - 0.0062 * mw + 0.066 * rb - 0.74 * arom
    mol_per_l = 10 ** logs
    g_per_l = mol_per_l * mw
    if logs > 0:
        cls, text = "very soluble", "mixes with water in any proportion in practice"
    elif logs > -2:
        cls, text = "soluble", "dissolves well in water"
    elif logs > -4:
        cls, text = "moderately soluble", "dissolves to some extent; heating or a co-solvent helps"
    else:
        cls, text = "poorly soluble", "mostly insoluble in water"
    reasons = []
    hbd = rdMolDescriptors.CalcNumHBD(mol)
    hba = rdMolDescriptors.CalcNumHBA(mol)
    c = sum(1 for a in mol.GetAtoms() if a.GetSymbol() == "C")
    if hbd + hba == 0:
        reasons.append("no hydrogen bond donors or acceptors, so water has nothing to bind to")
    elif c and c / max(1, hbd + hba) > 5:
        reasons.append(f"{c} carbons per {hbd + hba} polar group{'s' if hbd + hba != 1 else ''}: the hydrocarbon part dominates")
    else:
        reasons.append(f"{hbd} donor{'s' if hbd != 1 else ''} and {hba} acceptor{'s' if hba != 1 else ''} for {c} carbon{'s' if c != 1 else ''}: enough polar groups to hydrogen bond with water")
    if logp > 3:
        reasons.append(f"logP {logp:.1f} is high: prefers oil over water")
    elif logp < 0:
        reasons.append(f"logP {logp:.1f} is negative: prefers water over oil")
    if any(a.GetFormalCharge() for a in mol.GetAtoms()):
        reasons.append("a charged group pulls the molecule into water")
    return {
        "logs": round(logs, 2),
        "mol_per_l": mol_per_l,
        "g_per_l": round(g_per_l, 4),
        "class": cls,
        "text": text,
        "reasons": reasons,
        "logp": round(logp, 2),
        "method": "ESOL: logS = 0.16 - 0.63 logP - 0.0062 MW + 0.066 rotatable bonds - 0.74 aromatic proportion",
    }


# --- everything for the Bonding card ----------------------------------------

def bonding(smiles: str, molblock: str | None = None) -> dict:
    mol = mol_from_smiles(smiles)
    ox = oxidation_states(mol)
    polarity = bond_polarity(mol)
    polar_colours = {}
    for p in polarity:
        if p["class"] == "polar":
            polar_colours[p["bond_idx"]] = _rgba("#f59e0b", 0.6)
        elif p["class"] == "ionic":
            polar_colours[p["bond_idx"]] = _rgba("#dc2626", 0.6)
    ox_notes = {o["idx"]: _ox_label(o["oxidation_state"]) for o in ox}
    return {
        "oxidation": {"atoms": ox, "svg": _draw(mol, notes=ox_notes)},
        "polarity": {
            "bonds": polarity,
            "ch": _ch_polarity(mol),
            "svg": _draw(mol, bond_colours=polar_colours),
            "dipole": dipole(molblock) if molblock else None,
        },
        "vsepr": vsepr(mol, molblock),
        "rings": ring_aromaticity(mol),
        "unsaturation": unsaturation(mol),
        "chirality": chirality_class(mol),
        "hbond": hbond_sites(mol),
        "solubility": solubility(mol),
    }
