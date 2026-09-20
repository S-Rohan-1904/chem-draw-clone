"""Fischer and Haworth projections drawn from the 3D conformer.

Fischer: the longest acyclic carbon chain that carries every stereocentre
is drawn vertically with the most oxidised end on top; left/right for each
substituent is read from the conformer's chirality. D/L follows the lowest
stereocentre. Haworth: a five or six membered ring with one oxygen and an
anomeric carbon; up/down comes from which side of the ring plane each
substituent sits on. Alpha/beta compares the anomeric group with the
reference substituent.
"""

from __future__ import annotations

import numpy as np
from rdkit import Chem

from .analysis import oxidation_states
from .chem import ChemError

COLOURS = {"C": "#1a1d29", "O": "#dc2626", "N": "#2563eb", "S": "#ca8a04", "Cl": "#16a34a", "Br": "#9a3412", "F": "#16a34a", "I": "#7c3aed", "H": "#6b7280", "P": "#ea580c"}


def _mol3d(molblock: str) -> Chem.Mol:
    mol = Chem.MolFromMolBlock(molblock, removeHs=False)
    if mol is None or mol.GetNumConformers() == 0:
        raise ChemError("No 3D geometry available.")
    Chem.AssignStereochemistryFrom3D(mol)
    return mol


_SUB = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def group_label(atom: Chem.Atom, parent: int, depth: int = 0) -> str:
    """Condensed formula of the branch starting at `atom`, e.g. CHO, COOH, CH2OH, NH2."""
    if atom.GetAtomicNum() == 1:
        return "H"
    if atom.IsInRing():
        return "Ph" if atom.GetIsAromatic() and atom.GetSymbol() == "C" else "R"
    if depth > 6:
        return "R"
    sym = atom.GetSymbol()
    hs = sum(1 for n in atom.GetNeighbors() if n.GetAtomicNum() == 1) + atom.GetNumImplicitHs()
    text = sym + ("H" + (str(hs) if hs > 1 else "") if hs else "")
    children = []
    for b in atom.GetBonds():
        nb = b.GetOtherAtom(atom)
        if nb.GetIdx() == parent or nb.GetAtomicNum() == 1:
            continue
        order = b.GetBondTypeAsDouble()
        label = group_label(nb, atom.GetIdx(), depth + 1)
        children.append((0 if order > 1 else 1, label))
    children.sort()
    # Double-bonded partners are written bare right after the atom (CHO, COOH).
    text += "".join(c[1] for c in children if c[0] == 0)
    labels = [c[1] for c in children if c[0] == 1]
    if not labels:
        return text
    if len(labels) == 1:
        return text + labels[0]
    if len(set(labels)) == 1:
        return f"{text}({labels[0]}){len(labels)}"
    return text + "".join(f"({l})" for l in labels[:-1]) + labels[-1]


def _sub(text: str) -> str:
    return "".join(c.translate(_SUB) if c.isdigit() else c for c in text)


# --- Fischer ---------------------------------------------------------------

def _carbon_chains(mol: Chem.Mol) -> list[list[int]]:
    """All simple paths of non-ring carbons, longest first."""
    carbons = [a.GetIdx() for a in mol.GetAtoms() if a.GetSymbol() == "C" and not a.IsInRing()]
    cset = set(carbons)
    best: list[list[int]] = []

    def dfs(path: list[int], seen: set[int]) -> None:
        extended = False
        for n in mol.GetAtomWithIdx(path[-1]).GetNeighbors():
            j = n.GetIdx()
            if j in cset and j not in seen:
                extended = True
                dfs(path + [j], seen | {j})
        if not extended:
            best.append(path)

    for c in carbons:
        dfs([c], {c})
    best.sort(key=len, reverse=True)
    return best


def fischer(molblock: str, size: int = 360) -> dict | None:
    mol = _mol3d(molblock)
    heavy = Chem.RemoveHs(mol)
    centres = [a.GetIdx() for a in heavy.GetAtoms() if a.GetChiralTag() in (Chem.ChiralType.CHI_TETRAHEDRAL_CW, Chem.ChiralType.CHI_TETRAHEDRAL_CCW)]
    if not centres or heavy.GetNumHeavyAtoms() > 40:
        return None
    chains = [c for c in _carbon_chains(heavy) if set(centres) <= set(c) and len(c) >= 2]
    if not chains:
        return None
    ox = {o["idx"]: o["oxidation_state"] for o in oxidation_states(heavy)}
    longest = len(chains[0])
    chains = [c for c in chains if len(c) == longest]

    def end_score(c: list[int]) -> tuple:
        return (max(ox[c[0]], ox[c[-1]]),)

    chain = max(chains, key=end_score)
    if ox[chain[-1]] > ox[chain[0]] or (ox[chain[-1]] == ox[chain[0]] and _hetero_count(heavy, chain[-1]) > _hetero_count(heavy, chain[0])):
        chain = chain[::-1]
    pos = mol.GetConformer().GetPositions()
    rows = []
    for k, idx in enumerate(chain):
        atom = mol.GetAtomWithIdx(idx)
        subs = [n for n in atom.GetNeighbors() if n.GetIdx() not in chain]
        if k == 0 or k == len(chain) - 1:
            rows.append({"idx": idx, "kind": "end", "label": group_label(mol.GetAtomWithIdx(idx), chain[1] if k == 0 else chain[-2]), "left": None, "right": None})
            continue
        up, down = chain[k - 1], chain[k + 1]
        if len(subs) != 2:
            rows.append({"idx": idx, "kind": "mid", "label": "", "left": None, "right": None, "note": "not a simple centre"})
            continue
        a, b = subs
        is_centre = idx in centres
        if is_centre:
            u, d, s = pos[up] - pos[idx], pos[down] - pos[idx], pos[a.GetIdx()] - pos[idx]
            vol = float(np.dot(u, np.cross(d, s)))
            left, right = (a, b) if vol > 0 else (b, a)
        else:
            # Not a stereocentre: order is arbitrary, put the heavier group on the right.
            left, right = sorted(subs, key=lambda n: n.GetAtomicNum())
        rows.append({
            "idx": idx,
            "kind": "centre" if is_centre else "mid",
            "label": "",
            "left": {"idx": left.GetIdx(), "text": group_label(left, idx), "symbol": left.GetSymbol()},
            "right": {"idx": right.GetIdx(), "text": group_label(right, idx), "symbol": right.GetSymbol()},
        })
    # D/L from the lowest stereocentre bearing O or N, when the top is a carbonyl or carboxyl.
    dl = None
    top_label = rows[0]["label"]
    lowest = next((r for r in reversed(rows) if r["kind"] == "centre"), None)
    # Amino acids: the alpha carbon (C2, bearing N under a COOH) decides, as in the usual convention.
    if top_label == "COOH" and len(rows) > 2 and rows[1]["kind"] == "centre" and any(rows[1][side] and rows[1][side]["symbol"] == "N" for side in ("left", "right")):
        lowest = rows[1]
    if lowest and (top_label in ("CHO", "COOH", "COO-") or (top_label.startswith("C") and "O" in top_label and len(rows) > 2 and rows[1]["kind"] != "centre")):
        for side in ("right", "left"):
            s = lowest[side]
            if s and s["symbol"] in ("O", "N"):
                dl = "D" if side == "right" else "L"
                break
    return {
        "chain": chain,
        "rows": rows,
        "dl": dl,
        "dl_reason": (f"{dl}: the heteroatom on C{rows.index(lowest) + 1} points {'right' if dl == 'D' else 'left'}." if dl else None),
        "svg": _fischer_svg(rows, size),
    }


def _hetero_count(mol: Chem.Mol, idx: int) -> int:
    return sum(1 for n in mol.GetAtomWithIdx(idx).GetNeighbors() if n.GetAtomicNum() not in (1, 6))


def _fischer_svg(rows: list[dict], size: int) -> str:
    n = len(rows)
    h = max(size, 70 * n + 40)
    w = size
    cx = w / 2
    step = (h - 80) / max(1, n - 1)
    parts = [f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {w} {h}' font-family='sans-serif'>",
             "<rect width='100%' height='100%' fill='white'/>"]
    ys = [40 + k * step for k in range(n)]
    parts.append(f"<line x1='{cx}' y1='{ys[0]}' x2='{cx}' y2='{ys[-1]}' stroke='#1a1d29' stroke-width='2.5'/>")
    arm = min(70, w * 0.2)
    for k, r in enumerate(rows):
        y = ys[k]
        parts.append(f"<text x='{cx + arm + 34}' y='{y - 12}' font-size='10' fill='#9ca3af' text-anchor='middle'>C{k + 1}</text>")
        if r["kind"] == "end":
            anchor_y = y + (5 if k == 0 else 5)
            parts.append(f"<rect x='{cx - 30}' y='{y - 11}' width='60' height='22' fill='white'/>")
            parts.append(f"<text x='{cx}' y='{anchor_y}' font-size='16' font-weight='600' text-anchor='middle' fill='#1a1d29'>{_sub(r['label'])}</text>")
            continue
        parts.append(f"<line x1='{cx - arm}' y1='{y}' x2='{cx + arm}' y2='{y}' stroke='#1a1d29' stroke-width='2.5'/>")
        if r["left"]:
            parts.append(f"<text x='{cx - arm - 6}' y='{y + 5}' font-size='15' text-anchor='end' fill='{COLOURS.get(r['left']['symbol'], '#1a1d29')}'>{_sub(r['left']['text'])}</text>")
        if r["right"]:
            parts.append(f"<text x='{cx + arm + 6}' y='{y + 5}' font-size='15' text-anchor='start' fill='{COLOURS.get(r['right']['symbol'], '#1a1d29')}'>{_sub(r['right']['text'])}</text>")
        if r["kind"] == "mid" and r.get("note"):
            parts.append(f"<text x='{cx + arm + 6}' y='{y + 5}' font-size='11' fill='#9ca3af'>{r['note']}</text>")
    parts.append("</svg>")
    return "".join(parts)


# --- Haworth ----------------------------------------------------------------

_PYRANOSE = {"O": (0.55, 0.45), 1: (1.0, 0.0), 2: (0.55, -0.45), 3: (-0.55, -0.45), 4: (-1.0, 0.0), 5: (-0.55, 0.45)}
_FURANOSE = {"O": (0.0, 0.5), 1: (0.85, 0.12), 2: (0.5, -0.5), 3: (-0.5, -0.5), 4: (-0.85, 0.12)}


def sugar_rings(mol: Chem.Mol) -> list[dict]:
    """Rings that look like a cyclic sugar: 5 or 6 atoms, one ring O, sp3 carbons, an anomeric carbon."""
    ri = mol.GetRingInfo()
    out = []
    for ring in ri.AtomRings():
        if len(ring) not in (5, 6):
            continue
        os_ = [i for i in ring if mol.GetAtomWithIdx(i).GetSymbol() == "O"]
        cs = [i for i in ring if mol.GetAtomWithIdx(i).GetSymbol() == "C"]
        if len(os_) != 1 or len(cs) != len(ring) - 1:
            continue
        if any(mol.GetAtomWithIdx(i).GetHybridization() != Chem.HybridizationType.SP3 for i in cs):
            continue
        if any(ri.NumAtomRings(i) > 1 for i in ring):
            continue
        o = os_[0]
        ring_set = set(ring)
        anomeric = []
        for n in mol.GetAtomWithIdx(o).GetNeighbors():
            exo = [x for x in n.GetNeighbors() if x.GetIdx() not in ring_set and x.GetSymbol() in ("O", "N")]
            if exo:
                anomeric.append((n.GetIdx(), exo[0].GetIdx()))
        if len(anomeric) != 1:
            continue
        c1, exo_o = anomeric[0]
        # Walk the ring from C1 away from O.
        order = [c1]
        prev = o
        while len(order) < len(ring) - 1:
            cur = mol.GetAtomWithIdx(order[-1])
            nxt = next(x.GetIdx() for x in cur.GetNeighbors() if x.GetIdx() in ring_set and x.GetIdx() != prev and x.GetIdx() != o)
            prev = order[-1]
            order.append(nxt)
        out.append({"ring": order, "oxygen": o, "anomeric": c1, "anomeric_sub": exo_o})
    return out


def haworth(molblock: str, ring_info: dict | None = None, size: int = 380) -> dict | None:
    mol = _mol3d(molblock)
    rings = sugar_rings(mol)
    if not rings:
        return None
    info = ring_info or rings[0]
    order = info["ring"]
    o = info["oxygen"]
    pos = mol.GetConformer().GetPositions()
    cyc = order + [o]
    n = np.zeros(3)
    for i in range(len(cyc)):
        n += np.cross(pos[cyc[i]], pos[cyc[(i + 1) % len(cyc)]])
    up_vec = -n / (np.linalg.norm(n) or 1.0)
    template = _PYRANOSE if len(order) == 5 else _FURANOSE
    atoms = []
    ring_set = set(cyc)
    # Ketoses (fructose): the anomeric carbon carries a carbon too and is C2.
    offset = 1 if any(nb.GetSymbol() == "C" and nb.GetIdx() not in ring_set for nb in mol.GetAtomWithIdx(order[0]).GetNeighbors()) else 0
    for k, idx in enumerate(order, start=1):
        atom = mol.GetAtomWithIdx(idx)
        subs = []
        for nb in atom.GetNeighbors():
            if nb.GetIdx() in ring_set:
                continue
            d = pos[nb.GetIdx()] - pos[idx]
            up = bool(np.dot(d, up_vec) > 0)
            subs.append({"idx": nb.GetIdx(), "text": group_label(nb, idx), "symbol": nb.GetSymbol(), "up": up, "h": nb.GetAtomicNum() == 1})
        subs.sort(key=lambda s: s["h"])
        atoms.append({"num": k, "label": k + offset, "idx": idx, "subs": subs})
    # Reference carbon: the last ring carbon with a non-H substituent.
    ref = next((a for a in reversed(atoms) if any(not s["h"] for s in a["subs"])), None)
    anomeric_up = next((s["up"] for s in atoms[0]["subs"] if s["idx"] == info["anomeric_sub"]), None)
    anomer = None
    dl = None
    ref_sub = None
    if ref is not None and ref is not atoms[0]:
        ref_sub = next(s for s in ref["subs"] if not s["h"])
        # C5 CH2OH up = D. For a reference OH (pentopyranoses) the D form has it down.
        if ref_sub["symbol"] == "C":
            dl = "D" if ref_sub["up"] else "L"
        elif ref_sub["symbol"] == "O":
            dl = "D" if not ref_sub["up"] else "L"
        # In the D series the alpha anomer has the anomeric group down; L is the mirror image.
        if anomeric_up is not None and dl is not None:
            anomer = "alpha" if anomeric_up != (dl == "D") else "beta"
    return {
        "ring": order,
        "oxygen": o,
        "size": len(cyc),
        "kind": "pyranose" if len(cyc) == 6 else "furanose",
        "atoms": atoms,
        "anomer": anomer,
        "anomeric_up": anomeric_up,
        "reference": {"num": ref["label"], "text": ref_sub["text"], "up": ref_sub["up"]} if ref_sub else None,
        "dl": dl,
        "svg": _haworth_svg(atoms, o, template, size),
        "rings_available": len(rings),
    }


def _haworth_svg(atoms: list[dict], o: int, template: dict, size: int) -> str:
    w, h = size, int(size * 0.8)
    cx, cy = w / 2, h / 2
    sx, sy = w * 0.3, h * 0.3
    def P(key):
        x, d = template[key]
        return cx + x * sx, cy - d * sy
    parts = [f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {w} {h}' font-family='sans-serif'>",
             "<rect width='100%' height='100%' fill='white'/>"]
    keys = [a["num"] for a in atoms] + ["O"]
    for i in range(len(keys)):
        a, b = keys[i], keys[(i + 1) % len(keys)]
        x1, y1 = P(a)
        x2, y2 = P(b)
        front = template[a][1] < 0 and template[b][1] < 0
        width = 7 if front else 2
        parts.append(f"<line x1='{x1:.1f}' y1='{y1:.1f}' x2='{x2:.1f}' y2='{y2:.1f}' stroke='#1a1d29' stroke-width='{width}' stroke-linecap='round'/>")
    ox, oy = P("O")
    parts.append(f"<rect x='{ox - 10}' y='{oy - 10}' width='20' height='20' fill='white'/>")
    parts.append(f"<text x='{ox}' y='{oy + 5}' font-size='16' font-weight='600' text-anchor='middle' fill='#dc2626'>O</text>")
    arm = h * 0.15
    for a in atoms:
        x, y = P(a["num"])
        parts.append(f"<text x='{x + 9}' y='{y + 12}' font-size='9' fill='#9ca3af'>{a['label']}</text>")
        for s in a["subs"]:
            ey = y - arm if s["up"] else y + arm
            parts.append(f"<line x1='{x:.1f}' y1='{y:.1f}' x2='{x:.1f}' y2='{ey:.1f}' stroke='#1a1d29' stroke-width='2'/>")
            ty = ey - 5 if s["up"] else ey + 15
            colour = COLOURS.get(s["symbol"], "#1a1d29")
            weight = "600" if not s["h"] else "400"
            fs = 14 if not s["h"] else 12
            parts.append(f"<text x='{x:.1f}' y='{ty:.1f}' font-size='{fs}' font-weight='{weight}' text-anchor='middle' fill='{colour}'>{_sub(s['text'])}</text>")
    parts.append("</svg>")
    return "".join(parts)


def projections(molblock: str) -> dict:
    return {"fischer": fischer(molblock), "haworth": haworth(molblock)}
