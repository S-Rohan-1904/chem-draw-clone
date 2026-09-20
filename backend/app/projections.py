"""Teaching projections drawn from the 3D conformer: Newman projections
along a chosen bond and chair diagrams for saturated six-membered rings."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from rdkit import Chem

from .chem import ChemError

COLORS = {"C": "#1a1d29", "O": "#dc2626", "N": "#2563eb", "S": "#ca8a04", "Cl": "#16a34a", "Br": "#9a3412", "F": "#16a34a", "I": "#7c3aed", "H": "#6b7280", "P": "#ea580c"}


def _mol3d(molblock: str) -> Chem.Mol:
    mol = Chem.MolFromMolBlock(molblock, removeHs=False)
    if mol is None or mol.GetNumConformers() == 0:
        raise ChemError("No 3D geometry available.")
    return mol


def _label(atom: Chem.Atom, exclude: int) -> str:
    """Short substituent label: H, CH3, OH, NH2, Cl, or the atom symbol."""
    sym = atom.GetSymbol()
    if sym == "H":
        return "H"
    hs = sum(1 for n in atom.GetNeighbors() if n.GetAtomicNum() == 1) + atom.GetNumImplicitHs()
    heavy = [n for n in atom.GetNeighbors() if n.GetAtomicNum() > 1 and n.GetIdx() != exclude]
    if sym == "C":
        if not heavy:
            return "CH3"
        if len(heavy) == 1 and hs == 2:
            return "CH2R"
        return "CR" if hs == 0 else f"CH{hs}R" if hs > 1 else "CHR"
    sub = {1: "", 2: "2", 3: "3"}
    return f"{sym}{'H' + sub[hs] if hs else ''}" if hs else (sym if not heavy else f"{sym}R")


def newman_bonds(molblock: str) -> list[dict]:
    """Candidate bonds for a Newman projection: single, acyclic, both ends heavy with 2+ neighbours."""
    mol = _mol3d(molblock)
    out = []
    for b in mol.GetBonds():
        a1, a2 = b.GetBeginAtom(), b.GetEndAtom()
        if b.GetBondType() != Chem.BondType.SINGLE or b.IsInRing():
            continue
        if a1.GetAtomicNum() == 1 or a2.GetAtomicNum() == 1:
            continue
        heavy1 = sum(1 for n in a1.GetNeighbors() if n.GetAtomicNum() > 1)
        heavy2 = sum(1 for n in a2.GetNeighbors() if n.GetAtomicNum() > 1)
        if heavy1 < 2 or heavy2 < 2:
            continue
        out.append({"atoms": [a1.GetIdx(), a2.GetIdx()], "label": f"{a1.GetSymbol()}{a1.GetIdx() + 1}–{a2.GetSymbol()}{a2.GetIdx() + 1}"})
    return out


def newman_svg(molblock: str, front: int, back: int, rotate_deg: float = 0.0, size: int = 360) -> dict:
    mol = _mol3d(molblock)
    n = mol.GetNumAtoms()
    if not (0 <= front < n and 0 <= back < n) or mol.GetBondBetweenAtoms(front, back) is None:
        raise ChemError("Pick two bonded atoms.")
    pos = mol.GetConformer().GetPositions()
    axis = pos[back] - pos[front]
    axis /= np.linalg.norm(axis)
    # Orthonormal basis of the plane perpendicular to the bond.
    ref = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(axis, ref)
    u /= np.linalg.norm(u)
    v = np.cross(axis, u)

    def project(idx: int, centre: int, extra_rot: float) -> tuple[float, float]:
        d = pos[idx] - pos[centre]
        x, y = float(np.dot(d, u)), float(np.dot(d, v))
        ang = math.atan2(y, x) + math.radians(extra_rot)
        return math.cos(ang), math.sin(ang)

    cx = cy = size / 2
    r_circle = size * 0.22
    r_front = size * 0.36
    r_back = size * 0.44
    parts = [f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {size} {size}' width='{size}' height='{size}'>",
             "<rect width='100%' height='100%' fill='white'/>"]
    # Back atom substituents: from circle edge outward (drawn first so front covers them).
    back_subs = [nb.GetIdx() for nb in mol.GetAtomWithIdx(back).GetNeighbors() if nb.GetIdx() != front]
    for idx in back_subs:
        dx, dy = project(idx, back, rotate_deg)
        x1, y1 = cx + dx * r_circle, cy - dy * r_circle
        x2, y2 = cx + dx * r_back, cy - dy * r_back
        sym = mol.GetAtomWithIdx(idx).GetSymbol()
        parts.append(f"<line x1='{x1:.1f}' y1='{y1:.1f}' x2='{x2:.1f}' y2='{y2:.1f}' stroke='#94a3b8' stroke-width='3'/>")
        parts.append(f"<text x='{cx + dx * (r_back + 18):.1f}' y='{cy - dy * (r_back + 18) + 5:.1f}' text-anchor='middle' font-size='15' fill='{COLORS.get(sym, '#1a1d29')}' font-family='sans-serif'>{_label(mol.GetAtomWithIdx(idx), back)}</text>")
    parts.append(f"<circle cx='{cx}' cy='{cy}' r='{r_circle}' fill='white' stroke='#1a1d29' stroke-width='2.5'/>")
    front_subs = [nb.GetIdx() for nb in mol.GetAtomWithIdx(front).GetNeighbors() if nb.GetIdx() != back]
    for idx in front_subs:
        dx, dy = project(idx, front, 0.0)
        x2, y2 = cx + dx * r_front, cy - dy * r_front
        sym = mol.GetAtomWithIdx(idx).GetSymbol()
        parts.append(f"<line x1='{cx}' y1='{cy}' x2='{x2:.1f}' y2='{y2:.1f}' stroke='#1a1d29' stroke-width='3'/>")
        parts.append(f"<text x='{cx + dx * (r_front + 18):.1f}' y='{cy - dy * (r_front + 18) + 5:.1f}' text-anchor='middle' font-size='15' font-weight='600' fill='{COLORS.get(sym, '#1a1d29')}' font-family='sans-serif'>{_label(mol.GetAtomWithIdx(idx), front)}</text>")
    # Dihedral between the first substituent of each end, after the user's rotation.
    dihedral = None
    if front_subs and back_subs:
        fx, fy = project(front_subs[0], front, 0.0)
        bx, by = project(back_subs[0], back, rotate_deg)
        dihedral = round(math.degrees(math.atan2(fx * by - fy * bx, fx * bx + fy * by)) % 360, 1)
    parts.append(f"<text x='12' y='{size - 12}' font-size='12' fill='#6b7280' font-family='sans-serif'>front: {mol.GetAtomWithIdx(front).GetSymbol()}{front + 1}, back: {mol.GetAtomWithIdx(back).GetSymbol()}{back + 1}</text>")
    parts.append("</svg>")
    return {"svg": "".join(parts), "dihedral": dihedral, "front_subs": front_subs, "back_subs": back_subs}


# --- chair diagrams -------------------------------------------------------

@dataclass
class ChairSub:
    ring_pos: int  # 0..5 around the ring
    atom_idx: int
    label: str
    axial: bool
    up: bool


def chair_rings(molblock: str) -> list[list[int]]:
    """Saturated six-membered carbocycles / heterocycles with all sp3 atoms."""
    mol = _mol3d(molblock)
    rings = []
    for ring in mol.GetRingInfo().AtomRings():
        if len(ring) != 6:
            continue
        if all(mol.GetAtomWithIdx(i).GetHybridization() == Chem.HybridizationType.SP3 for i in ring):
            rings.append(list(ring))
    return rings


def chair_analysis(molblock: str, ring: list[int]) -> dict:
    """Axial/equatorial assignment for each ring substituent from the 3D
    conformer. `flipped=True` describes the other chair (axial and
    equatorial swap, up/down stay)."""
    mol = _mol3d(molblock)
    pos = mol.GetConformer().GetPositions()
    if len(ring) != 6 or any(not (0 <= i < mol.GetNumAtoms()) for i in ring):
        raise ChemError("Not a six-membered ring.")
    # Order ring atoms by connectivity so neighbours in the list are bonded.
    ordered = [ring[0]]
    ring_set = set(ring)
    while len(ordered) < 6:
        cur = mol.GetAtomWithIdx(ordered[-1])
        nxt = next(n.GetIdx() for n in cur.GetNeighbors() if n.GetIdx() in ring_set and n.GetIdx() not in ordered)
        ordered.append(nxt)
    centre = pos[ordered].mean(axis=0)
    # Ring mean-plane normal via SVD.
    _, _, vt = np.linalg.svd(pos[ordered] - centre)
    normal = vt[2]
    subs: list[ChairSub] = []
    ring_hs = 0
    for k, idx in enumerate(ordered):
        atom = mol.GetAtomWithIdx(idx)
        for nb in atom.GetNeighbors():
            if nb.GetIdx() in ring_set:
                continue
            d = pos[nb.GetIdx()] - pos[idx]
            d /= np.linalg.norm(d)
            cos = float(np.dot(d, normal))
            axial = abs(cos) > 0.7  # ~45 deg: axial bonds are near-parallel to the normal
            if nb.GetAtomicNum() == 1:
                ring_hs += 1
                continue
            subs.append(ChairSub(k, nb.GetIdx(), _label(nb, idx), axial, cos > 0))
    return {
        "ring": ordered,
        "_positions": [[float(x) for x in pos[i]] for i in ordered],
        "substituents": [s.__dict__ for s in subs],
        "axial_count": sum(1 for s in subs if s.axial),
        "equatorial_count": sum(1 for s in subs if not s.axial),
    }


def chair_svg(analysis: dict, flipped: bool = False, size: int = 360) -> str:
    """Chair drawn by projecting the ring's own geometry from a low viewing
    angle. Substituent bonds use ideal axial (along the ring normal) and
    equatorial (outward, slightly tilted) directions so the diagram is
    clean. The flipped chair mirrors the ring through its mean plane, which
    inverts the pucker, and swaps axial and equatorial for every group."""
    w, h = size, int(size * 0.62)
    pos = np.array(analysis["_positions"])  # ring atom positions in ring order
    centre = pos.mean(axis=0)
    _, _, vt = np.linalg.svd(pos - centre)
    normal = vt[2]
    if np.dot(normal, pos[1] - centre) < np.dot(normal, pos[0] - centre):
        pass
    ring = pos - centre
    if flipped:
        ring = ring - 2 * np.outer(ring @ normal, normal)  # reflect through the mean plane
    # Viewing direction: low angle above the ring, looking across the C0-C3 axis
    # (the classic chair drawing shows that axis running left to right).
    e1 = ring[0] - ring[3]
    e1 -= np.dot(e1, normal) * normal
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(normal, e1)
    theta = math.radians(75)
    view = math.cos(theta) * normal + math.sin(theta) * e2
    up = normal - np.dot(normal, view) * view
    up /= np.linalg.norm(up)
    right = np.cross(up, view)
    right /= np.linalg.norm(right)

    def to2d(p: np.ndarray) -> tuple[float, float]:
        return float(np.dot(p, right)), float(-np.dot(p, up))

    pts2 = [to2d(p) for p in ring]
    # substituent directions
    subs2 = []
    for s_ in analysis["substituents"]:
        k = s_["ring_pos"]
        axial = (not s_["axial"]) if flipped else s_["axial"]
        sign = 1.0 if s_["up"] else -1.0
        prev_, next_ = ring[(k - 1) % 6], ring[(k + 1) % 6]
        bis = (prev_ - ring[k]) + (next_ - ring[k])
        outward = -bis / np.linalg.norm(bis)
        outward -= np.dot(outward, normal) * normal
        outward /= np.linalg.norm(outward)
        d = sign * normal if axial else (outward + 0.35 * sign * normal)
        d = d / np.linalg.norm(d) * 1.05
        subs2.append((k, to2d(ring[k] + d), axial, s_["label"]))

    xs = [p[0] for p in pts2] + [q[1][0] for q in subs2]
    ys = [p[1] for p in pts2] + [q[1][1] for q in subs2]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    pad = 48
    scale = min((w - 2 * pad) / max(maxx - minx, 1e-6), (h - 2 * pad) / max(maxy - miny, 1e-6))
    ox = pad + ((w - 2 * pad) - (maxx - minx) * scale) / 2
    oy = pad + ((h - 2 * pad) - (maxy - miny) * scale) / 2

    def px(p: tuple[float, float]) -> tuple[float, float]:
        return ox + (p[0] - minx) * scale, oy + (p[1] - miny) * scale

    P = [px(p) for p in pts2]
    parts = [f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {w} {h}' width='{w}' height='{h}'>",
             "<rect width='100%' height='100%' fill='white'/>"]
    # Back bonds thinner, front bonds bold: front = larger screen y (closer to viewer at low angle).
    for k in range(6):
        a, b = P[k], P[(k + 1) % 6]
        front = (a[1] + b[1]) / 2 > (sum(p[1] for p in P) / 6)
        parts.append(f"<line x1='{a[0]:.1f}' y1='{a[1]:.1f}' x2='{b[0]:.1f}' y2='{b[1]:.1f}' stroke='#1a1d29' stroke-width='{3.2 if front else 2}'/>")
    for k, end, axial, label in subs2:
        a, b = P[k], px(end)
        colour = "#2563eb" if axial else "#047857"
        parts.append(f"<line x1='{a[0]:.1f}' y1='{a[1]:.1f}' x2='{b[0]:.1f}' y2='{b[1]:.1f}' stroke='{colour}' stroke-width='2.5'/>")
        dx, dy = b[0] - a[0], b[1] - a[1]
        n_ = math.hypot(dx, dy) or 1.0
        tx, ty = b[0] + dx / n_ * 14, b[1] + dy / n_ * 14 + 5
        anchor = "middle" if abs(dx) < 0.3 * n_ else ("start" if dx > 0 else "end")
        parts.append(f"<text x='{tx:.1f}' y='{ty:.1f}' text-anchor='{anchor}' font-size='14' font-weight='600' fill='{colour}' font-family='sans-serif'>{label}</text>")
        parts.append(f"<text x='{tx:.1f}' y='{ty + 12:.1f}' text-anchor='{anchor}' font-size='10' fill='#6b7280' font-family='sans-serif'>{'ax' if axial else 'eq'}</text>")
    parts.append(f"<text x='10' y='14' font-size='11' fill='#6b7280' font-family='sans-serif'>{'ring-flipped chair' if flipped else 'chair from the 3D conformer'} \u00b7 blue axial, green equatorial</text>")
    parts.append("</svg>")
    return "".join(parts)
