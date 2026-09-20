"""EI mass-spectrum fragmentation tree.

Primary ions come from single-bond cleavages (spectra.ms_fragments), the
McLafferty rearrangement and characteristic neutral losses (H2O, CO, HCN,
CO2, HX, NH3). The strongest primary ions fragment once more (acylium loses
CO, benzyl/tropylium loses C2H2, alkyl chains lose C2H4). Each node carries
the ion's atoms for highlighting, a small drawing, and its isotope cluster
when Cl or Br make it informative.
"""

from __future__ import annotations

from rdkit import Chem
from rdkit.Chem import rdDepictor
from rdkit.Chem.Draw import rdMolDraw2D

from . import spectra as _sp

MAX_PRIMARY = 8
MAX_SECONDARY = 6

# (loss, SMARTS, indices of the SMARTS match that leave with it, why)
_LOSSES: list[tuple[str, str, tuple[int, ...], str]] = [
    ("H2O", "[CX4][OX2H1]", (1,), "alcohol dehydrates (1,2- or 1,4-elimination)"),
    ("CO", "[CX3H1](=O)[#6]", (0, 1), "aldehyde loses CO"),
    ("CO", "c[OX2H1]", (0, 1), "phenol loses CO"),
    ("HCN", "[CX2]#[NX1]", (0, 1), "nitrile loses HCN"),
    ("HCN", "n:c", (0, 1), "aromatic N-heterocycle loses HCN"),
    ("CO2", "[CX3](=O)[OX2H1]", (0, 1, 2), "carboxylic acid loses CO2"),
    ("HCl", "[CX4]Cl", (1,), "alkyl chloride loses HCl"),
    ("HBr", "[CX4]Br", (1,), "alkyl bromide loses HBr"),
    ("NH3", "[CX4][NX3H2]", (1,), "primary amine loses NH3"),
    ("C2H4", "[CX3](=O)O[CH2][CH3]", (3, 4), "ethyl ester loses ethene (McLafferty type)"),
]
_LOSS_COUNTS = {
    "H2O": {"H": 2, "O": 1},
    "CO": {"C": 1, "O": 1},
    "HCN": {"H": 1, "C": 1, "N": 1},
    "CO2": {"C": 1, "O": 2},
    "HCl": {"H": 1, "Cl": 1},
    "HBr": {"H": 1, "Br": 1},
    "NH3": {"H": 3, "N": 1},
    "C2H4": {"C": 2, "H": 4},
    "C2H2": {"C": 2, "H": 2},
}
_LOSS_COMPILED = [(n, Chem.MolFromSmarts(s), leave, why) for n, s, leave, why in _LOSSES]
_MCLAFFERTY = Chem.MolFromSmarts("[#6X3](=O)[#6][#6][#6;!H0]")


def _sub(counts: dict[str, int], loss: dict[str, int]) -> dict[str, int] | None:
    out = dict(counts)
    for k, v in loss.items():
        if out.get(k, 0) < v:
            return None
        out[k] -= v
        if out[k] == 0:
            del out[k]
    return out


def _svg(mol: Chem.Mol, atoms: list[int], charged: int | None, radical: bool) -> str:
    """Small drawing of the ion: the kept atoms, with + (and a dot) on the
    charge-bearing atom. Falls back to '' if the fragment cannot be drawn."""
    try:
        rw = Chem.RWMol(mol)
        for a in rw.GetAtoms():
            a.SetNoImplicit(False)
        keep = set(atoms)
        for idx in sorted((a.GetIdx() for a in rw.GetAtoms() if a.GetIdx() not in keep), reverse=True):
            rw.RemoveAtom(idx)
        if charged is not None and not radical:
            # A real charge keeps the hydrogen count right (CH3+, not CH4).
            rw.GetAtomWithIdx(sorted(keep).index(charged)).SetFormalCharge(1)
        m = rw.GetMol()
        m.UpdatePropertyCache(strict=False)
        Chem.SanitizeMol(m, Chem.SanitizeFlags.SANITIZE_ALL ^ Chem.SanitizeFlags.SANITIZE_PROPERTIES, catchErrors=True)
        rdDepictor.Compute2DCoords(m)
        if charged is not None and radical:
            m.GetAtomWithIdx(sorted(keep).index(charged)).SetProp("atomNote", "+•")
        d = rdMolDraw2D.MolDraw2DSVG(180, 120)
        o = d.drawOptions()
        o.clearBackground = False
        o.bondLineWidth = 1.5
        o.annotationFontScale = 0.9
        o.padding = 0.12
        d.DrawMolecule(m)
        d.FinishDrawing()
        return d.GetDrawingText()
    except Exception:  # noqa: BLE001 - drawing is optional
        return ""


def _node(mol: Chem.Mol, counts: dict[str, int], *, parent: int, loss: str, why: str, atoms: list[int], charged: int | None, radical: bool, score: float) -> dict:
    mono = _sp._mono_mass(counts)
    iso = _sp.isotope_pattern(counts, threshold=0.05)
    return {
        "parent": parent,
        "mz": round(mono - _sp._ELECTRON, 4),
        "nominal": int(round(mono)),
        "formula": _sp._formula(counts) + ("+•" if radical else "+"),
        "loss": loss,
        "why": why,
        "atoms": atoms,
        "svg": _svg(mol, atoms, charged, radical) if atoms else "",
        "isotopes": [{"nominal": p["nominal"], "rel": p["rel"]} for p in iso] if any(k in counts for k in ("Cl", "Br")) else [],
        "score": score,
    }


def _mclafferty(mol: Chem.Mol) -> list[dict]:
    out = []
    seen = set()
    for match in mol.GetSubstructMatches(_MCLAFFERTY):
        c_co, _o, c_a, c_b, c_g = match
        bond = mol.GetBondBetweenAtoms(c_a, c_b)
        if bond is None or bond.IsInRing():
            continue
        frag = Chem.FragmentOnBonds(mol, [bond.GetIdx()], addDummies=False)
        pieces = Chem.GetMolFrags(frag, asMols=False, sanitizeFrags=False)
        ion_atoms = next((list(p) for p in pieces if c_co in p), None)
        if ion_atoms is None or len(pieces) != 2:
            continue
        counts = _sp._element_counts(mol, ion_atoms)
        counts["H"] = counts.get("H", 0) + 1  # gamma-H moves to the carbonyl O
        neutral = [i for i in range(mol.GetNumAtoms()) if i not in ion_atoms]
        ncounts = _sp._element_counts(mol, neutral)
        ncounts["H"] -= 1
        key = _sp._formula(counts)
        if key in seen:
            continue
        seen.add(key)
        out.append(_node(mol, counts, parent=0, loss=_sp._formula(ncounts), why="McLafferty rearrangement: gamma-H to the carbonyl O, alkene lost", atoms=sorted(ion_atoms), charged=_o, radical=True, score=3.5))
    return out


def _neutral_losses(mol: Chem.Mol, mcounts: dict[str, int]) -> list[dict]:
    out = []
    seen = set()
    for name, patt, leave, why in _LOSS_COMPILED:
        match = mol.GetSubstructMatch(patt)
        if not match:
            continue
        counts = _sub(mcounts, _LOSS_COUNTS[name])
        if counts is None or (name, why) in seen:
            continue
        seen.add((name, why))
        leaving = {match[i] for i in leave}
        atoms = [i for i in range(mol.GetNumAtoms()) if i not in leaving]
        out.append(_node(mol, counts, parent=0, loss=name, why=why, atoms=atoms, charged=None, radical=True, score=2.5))
    return out


def _secondary(mol: Chem.Mol, node: dict, node_id: int) -> list[dict]:
    """One further step for a cation: acylium -CO, benzyl -C2H2, alkyl -C2H4."""
    out = []
    counts = _sp._element_counts(mol, node["atoms"])
    why = node["why"]
    if "acylium" in why:
        c = _sub(counts, _LOSS_COUNTS["CO"])
        if c and c.get("C", 0) >= 2:
            cos = [i for i in node["atoms"] if _sp._is_carbonyl_c(mol.GetAtomWithIdx(i))]
            keep = [i for i in node["atoms"] if i not in cos and not (mol.GetAtomWithIdx(i).GetAtomicNum() == 8 and any(n.GetIdx() in cos for n in mol.GetAtomWithIdx(i).GetNeighbors()))]
            out.append(_node(mol, c, parent=node_id, loss="CO", why="acylium loses CO to the alkyl/aryl cation", atoms=keep, charged=None, radical=False, score=2))
    elif "benzylic" in why and counts.get("C") == 7 and counts.get("H") == 7:
        c = _sub(counts, _LOSS_COUNTS["C2H2"])
        if c:
            out.append(_node(mol, c, parent=node_id, loss="C2H2", why="tropylium (m/z 91) loses ethyne to C5H5+ (m/z 65)", atoms=[], charged=None, radical=False, score=1.5))
    elif why == "simple cleavage" and set(counts) <= {"C", "H"} and counts.get("C", 0) >= 3:
        c = _sub(counts, _LOSS_COUNTS["C2H4"])
        if c and c.get("C", 0) >= 2:
            out.append(_node(mol, c, parent=node_id, loss="C2H4", why="alkyl cation loses ethene (CnH2n+1 series: 29, 43, 57...)", atoms=[], charged=None, radical=False, score=1.5))
    return out


def tree(mol: Chem.Mol) -> dict:
    mcounts = _sp._element_counts(mol)
    root = _node(mol, mcounts, parent=-1, loss="", why="molecular ion", atoms=list(range(mol.GetNumAtoms())), charged=None, radical=True, score=0)
    root["svg"] = ""
    primary = []
    for f in _sp.ms_fragments(mol, limit=MAX_PRIMARY):
        bond = mol.GetBondWithIdx(f["bond"])
        charged = bond.GetBeginAtomIdx() if bond.GetBeginAtomIdx() in f["atoms"] else bond.GetEndAtomIdx()
        why = f["why"]
        if "benzylic" in why and f["formula"] == "C7H7+":
            why += "; rearranges to tropylium"
        counts = _sp._element_counts(mol, f["atoms"])
        primary.append(_node(mol, counts, parent=0, loss=f["loss"] + "•", why=why, atoms=f["atoms"], charged=charged, radical=False, score=f["score"]))
    primary += _mclafferty(mol) + _neutral_losses(mol, mcounts)
    primary.sort(key=lambda n: (-n["score"], -n["nominal"]))
    seen: set[str] = set()
    kept = []
    for n in primary:
        key = n["formula"]
        if key in seen:
            continue
        seen.add(key)
        kept.append(n)
        if len(kept) >= MAX_PRIMARY:
            break
    nodes = [root] + kept
    secondary = []
    for i, n in enumerate(kept, start=1):
        if n["atoms"] and not n["formula"].endswith("•"):
            secondary += _secondary(mol, n, i)
    # A second-step ion that already appears as a direct cleavage (benzoyl
    # 105 -> phenyl 77) is the same peak: hang the existing node under its
    # precursor instead of listing it twice.
    by_formula = {n["formula"]: n for n in kept}
    added = 0
    for sec in secondary:
        if sec["formula"] in by_formula:
            prev = by_formula[sec["formula"]]
            prev["parent"] = sec["parent"]
            prev["loss"] = sec["loss"]
            prev["why"] = f"{sec['why']}; also by direct cleavage ({prev['why']})"
        elif added < MAX_SECONDARY:
            nodes.append(sec)
            by_formula[sec["formula"]] = sec
            added += 1
    for i, n in enumerate(nodes):
        n["id"] = i
    return {"nodes": nodes}
