"""Conformational energies with MMFF94: a torsion scan around a chosen bond
and the energy difference between the two chairs of a six-membered ring."""

from __future__ import annotations

import math

import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem, rdMolTransforms

from .chem import ChemError
from .projections import _mol3d
from .sugars import group_label as _label

MAX_HEAVY = 40


def _ref_atoms(mol: Chem.Mol, front: int, back: int) -> tuple[int, int]:
    """Same reference substituents as the Newman projection: the first
    neighbour of each end that is not the other end."""
    a = next((n.GetIdx() for n in mol.GetAtomWithIdx(front).GetNeighbors() if n.GetIdx() != back), None)
    d = next((n.GetIdx() for n in mol.GetAtomWithIdx(back).GetNeighbors() if n.GetIdx() != front), None)
    if a is None or d is None:
        raise ChemError("Both ends of the bond need another neighbour.")
    return a, d


def _energy(mol: Chem.Mol, props, conf_id: int = -1) -> float:
    ff = AllChem.MMFFGetMoleculeForceField(mol, props, confId=conf_id)
    return float(ff.CalcEnergy())


def torsion_scan(molblock: str, front: int, back: int, step: int = 10) -> dict:
    mol = _mol3d(molblock)
    if mol.GetNumHeavyAtoms() > MAX_HEAVY:
        raise ChemError(f"Torsion scans are limited to {MAX_HEAVY} heavy atoms.")
    n = mol.GetNumAtoms()
    if not (0 <= front < n and 0 <= back < n) or mol.GetBondBetweenAtoms(front, back) is None:
        raise ChemError("Pick two bonded atoms.")
    if mol.GetBondBetweenAtoms(front, back).IsInRing():
        raise ChemError("Ring bonds cannot be scanned.")
    props = AllChem.MMFFGetMoleculeProperties(mol)
    if props is None:
        raise ChemError("MMFF94 has no parameters for this molecule.")
    a, d = _ref_atoms(mol, front, back)
    conf = mol.GetConformer()
    start = rdMolTransforms.GetDihedralDeg(conf, a, front, back, d) % 360
    work = Chem.Mol(mol)
    wconf = work.GetConformer()
    points = []
    for k in range(0, 360, step):
        angle = float(k)
        rdMolTransforms.SetDihedralDeg(wconf, a, front, back, d, angle)
        ff = AllChem.MMFFGetMoleculeForceField(work, props)
        ff.MMFFAddTorsionConstraint(a, front, back, d, False, angle - 0.5, angle + 0.5, 2000.0)
        ff.Minimize(maxIts=400)
        e = _energy(work, props)
        points.append({"angle": k, "energy": e})
    emin = min(p["energy"] for p in points)
    for p in points:
        p["energy"] = round(p["energy"] - emin, 2)
    emax = max(p["energy"] for p in points)
    # Name the stationary points relative to the reference substituents.
    minima = [p for i, p in enumerate(points) if p["energy"] <= points[i - 1]["energy"] and p["energy"] <= points[(i + 1) % len(points)]["energy"]]
    maxima = [p for i, p in enumerate(points) if p["energy"] >= points[i - 1]["energy"] and p["energy"] >= points[(i + 1) % len(points)]["energy"]]
    return {
        "atoms": [a, front, back, d],
        "labels": [_label(mol.GetAtomWithIdx(a), front), _label(mol.GetAtomWithIdx(d), back)],
        "start_dihedral": round(start, 1),
        "step": step,
        "points": points,
        "barrier": round(emax, 2),
        "minima": [p["angle"] for p in minima],
        "maxima": [p["angle"] for p in maxima],
        "unit": "kcal/mol",
        "note": "MMFF94 energies, each point relaxed with the dihedral held fixed. Barriers are approximate; the shape of the curve is what to look at.",
    }


# --- chair flip -------------------------------------------------------------

def _ring_order(mol: Chem.Mol, ring: list[int]) -> list[int]:
    ordered = [ring[0]]
    ring_set = set(ring)
    while len(ordered) < len(ring):
        cur = mol.GetAtomWithIdx(ordered[-1])
        nxt = next(n.GetIdx() for n in cur.GetNeighbors() if n.GetIdx() in ring_set and n.GetIdx() not in ordered)
        ordered.append(nxt)
    return ordered


def _is_chair(conf, ordered: list[int]) -> bool:
    tors = [rdMolTransforms.GetDihedralDeg(conf, ordered[i], ordered[(i + 1) % 6], ordered[(i + 2) % 6], ordered[(i + 3) % 6]) for i in range(6)]
    if any(abs(t) < 35 or abs(t) > 80 for t in tors):
        return False
    return all((tors[i] > 0) != (tors[(i + 1) % 6] > 0) for i in range(6))


def _axial_set(mol: Chem.Mol, conf, ordered: list[int]) -> frozenset[int]:
    pos = np.array(conf.GetPositions())
    centre = pos[ordered].mean(axis=0)
    _, _, vt = np.linalg.svd(pos[ordered] - centre)
    normal = vt[2]
    axial = set()
    ring_set = set(ordered)
    for idx in ordered:
        for nb in mol.GetAtomWithIdx(idx).GetNeighbors():
            if nb.GetIdx() in ring_set or nb.GetAtomicNum() == 1:
                continue
            d = pos[nb.GetIdx()] - pos[idx]
            d /= np.linalg.norm(d)
            if abs(float(np.dot(d, normal))) > 0.7:
                axial.add(nb.GetIdx())
    return frozenset(axial)


def _flip_chair(mol: Chem.Mol, conf_id: int, ordered: list[int], props) -> tuple[float, int] | None:
    """Drive the six ring torsions to their negatives (the other chair), then relax freely."""
    src = mol.GetConformer(conf_id)
    tors = [rdMolTransforms.GetDihedralDeg(src, ordered[i], ordered[(i + 1) % 6], ordered[(i + 2) % 6], ordered[(i + 3) % 6]) for i in range(6)]
    new = Chem.Conformer(src)
    new.SetId(mol.GetNumConformers() + 100)
    cid = mol.AddConformer(new, assignId=True)
    ff = AllChem.MMFFGetMoleculeForceField(mol, props, confId=cid)
    for i in range(6):
        target = -tors[i]
        ff.MMFFAddTorsionConstraint(ordered[i], ordered[(i + 1) % 6], ordered[(i + 2) % 6], ordered[(i + 3) % 6], False, target - 5, target + 5, 200.0)
    ff.Minimize(maxIts=2000)
    ff2 = AllChem.MMFFGetMoleculeForceField(mol, props, confId=cid)
    ff2.Minimize(maxIts=2000)
    conf = mol.GetConformer(cid)
    if not _is_chair(conf, ordered):
        return None
    return float(ff2.CalcEnergy()), cid


def chair_energies(molblock: str, ring: list[int], n_conf: int = 30) -> dict:
    mol = _mol3d(molblock)
    if mol.GetNumHeavyAtoms() > MAX_HEAVY:
        raise ChemError(f"Chair energies are limited to {MAX_HEAVY} heavy atoms.")
    if len(ring) != 6 or any(not (0 <= i < mol.GetNumAtoms()) for i in ring):
        raise ChemError("Not a six-membered ring.")
    ordered = _ring_order(mol, ring)
    props = AllChem.MMFFGetMoleculeProperties(mol)
    if props is None:
        raise ChemError("MMFF94 has no parameters for this molecule.")
    ring_set = set(ordered)
    subs = {nb.GetIdx(): _label(nb, idx) for idx in ordered for nb in mol.GetAtomWithIdx(idx).GetNeighbors() if nb.GetIdx() not in ring_set and nb.GetAtomicNum() > 1}
    if not subs:
        raise ChemError("No substituents on this ring, so both chairs are the same.")
    base_conf = mol.GetConformer()
    current = _axial_set(mol, base_conf, ordered) if _is_chair(base_conf, ordered) else None

    work = Chem.Mol(mol)
    work.RemoveAllConformers()
    ps = AllChem.ETKDGv3()
    ps.randomSeed = 7
    ps.pruneRmsThresh = 0.2
    ps.enforceChirality = True
    cids = list(AllChem.EmbedMultipleConfs(work, numConfs=n_conf, params=ps))
    if not cids:
        raise ChemError("Could not generate conformers.")
    res = AllChem.MMFFOptimizeMoleculeConfs(work, maxIters=1000)
    best: dict[frozenset[int], tuple[float, int]] = {}
    for cid, (converged, e) in zip(cids, res):
        conf = work.GetConformer(cid)
        if not _is_chair(conf, ordered):
            continue
        key = _axial_set(work, conf, ordered)
        if key not in best or e < best[key][0]:
            best[key] = (float(e), cid)
    # Make sure both chairs are present: flip the best chair by inverting its ring torsions.
    if best:
        seed_key = min(best, key=lambda k: best[k][0])
        flipped = _flip_chair(work, best[seed_key][1], ordered, props)
        if flipped is not None:
            e, cid = flipped
            key = _axial_set(work, work.GetConformer(cid), ordered)
            if key not in best or e < best[key][0]:
                best[key] = (e, cid)
    if not best:
        raise ChemError("No chair conformers found.")
    # The two chairs are complementary axial sets; pair the current pattern with its complement.
    keys = sorted(best, key=lambda k: best[k][0])
    if current is not None and current in best:
        first = current
    else:
        first = keys[0]
    complement = frozenset(set(subs) - set(first))
    second = complement if complement in best else next((k for k in keys if k != first), None)
    e1 = best[first][0]
    e2 = best[second][0] if second is not None else None
    chairs = []
    for label, key, e in (("current", first, e1), ("flipped", second, e2)):
        if key is None:
            continue
        chairs.append({
            "which": label,
            "energy": round(e - min(e1, e2 if e2 is not None else e1), 2),
            "axial": [{"atom_idx": i, "label": subs[i]} for i in sorted(key)],
            "equatorial": [{"atom_idx": i, "label": subs[i]} for i in sorted(set(subs) - set(key))],
        })
    delta = round(e2 - e1, 2) if e2 is not None else None
    if delta is None:
        summary = "Only one chair was found in the conformer search."
    elif abs(delta) < 0.3:
        summary = "The two chairs are within 0.3 kcal/mol: about a 50:50 mixture at room temperature."
    else:
        k = math.exp(-abs(delta) / (0.001987 * 298.15))
        pct = 100.0 / (1.0 + k)
        favoured = "current" if delta > 0 else "flipped"
        summary = f"The {favoured} chair is lower by {abs(delta):.1f} kcal/mol, so it makes up about {pct:.0f}% of the mixture at 25 °C."
    return {
        "ring": ordered,
        "chairs": chairs,
        "delta": delta,
        "summary": summary,
        "conformers_checked": len(cids),
        "unit": "kcal/mol",
        "note": "Lowest MMFF94 energy found for each chair among the generated conformers. Textbook A values (methyl 1.7, tert-butyl about 5) are free energies; these are force field energies, so expect differences.",
    }
