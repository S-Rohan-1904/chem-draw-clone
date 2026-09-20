"""Spectra for the built molecule: 1H/13C NMR, IR and mass spectrum.

Predicted parts are computed here from the structure (symmetry-exact signal
counts, additive shift rules, characteristic IR bands, isotope patterns and
simple bond cleavages). Better NMR shifts come from the nmrshiftdb2 HOSE-code
service when reachable; experimental IR and MS come from the NIST Chemistry
WebBook (SRD 69). Both are optional: with CHEM_SPECTRA_LOOKUP=0 everything is
computed locally.
"""

from __future__ import annotations

import math
import os
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from urllib.parse import quote

import httpx

from . import couplings
from rdkit import Chem
from rdkit.Chem import Descriptors, rdMolDescriptors

NMRSHIFTDB = "https://nmrshiftdb.nmr.uni-koeln.de/NmrshiftdbServlet/nmrshiftdbaction/predict/smiles/{}/spectrumtype/{}"
NIST_SEARCH = "https://webbook.nist.gov/cgi/cbook.cgi?InChI={}&Units=SI"
NIST_JCAMP = "https://webbook.nist.gov/cgi/cbook.cgi?JCAMP={}&Type={}&Index={}"
NIST_PAGE = "https://webbook.nist.gov/cgi/cbook.cgi?ID={}&Units=SI&Type={}"

NMR_NOTE = "Shifts predicted with HOSE codes by nmrshiftdb2 (nmrshiftdb.nmr.uni-koeln.de)."
RULES_NOTE = "Shifts estimated from additive substituent rules; expect +/- 0.5 ppm (1H) and +/- 10 ppm (13C)."
NIST_NOTE = "Experimental spectrum from the NIST Chemistry WebBook, NIST Standard Reference Database 69."

_MULT = {0: "s", 1: "d", 2: "t", 3: "q", 4: "quint", 5: "sext", 6: "sept"}


def enabled() -> bool:
    return os.environ.get("CHEM_SPECTRA_LOOKUP", "1") not in ("0", "false", "no")


def _timeout() -> float:
    return float(os.environ.get("CHEM_SPECTRA_TIMEOUT", "10"))


# ---------------------------------------------------------------- symmetry

def equivalence(mol: Chem.Mol) -> tuple[Chem.Mol, list[int]]:
    """(mol with explicit H, canonical rank per atom). Equal rank = symmetry
    equivalent, so one NMR signal."""
    mh = Chem.AddHs(mol)
    return mh, list(Chem.CanonicalRankAtoms(mh, breakTies=False))


def _classes(mh: Chem.Mol, ranks: list[int], atomic_num: int) -> list[list[int]]:
    groups: dict[int, list[int]] = defaultdict(list)
    for a in mh.GetAtoms():
        if a.GetAtomicNum() == atomic_num:
            groups[ranks[a.GetIdx()]].append(a.GetIdx())
    return sorted(groups.values(), key=lambda g: g[0])


# ---------------------------------------------------------------- NMR rules

def _is_carbonyl_c(a: Chem.Atom) -> bool:
    return a.GetAtomicNum() == 6 and any(
        b.GetBondType() == Chem.BondType.DOUBLE and b.GetOtherAtom(a).GetAtomicNum() == 8 for b in a.GetBonds()
    )


def _carbonyl_kind(c: Chem.Atom) -> str:
    """acid | ester | amide | acyl halide | anhydride | aldehyde | ketone."""
    nbrs = [n for n in c.GetNeighbors() if not (n.GetAtomicNum() == 8 and c.GetOwningMol().GetBondBetweenAtoms(c.GetIdx(), n.GetIdx()).GetBondType() == Chem.BondType.DOUBLE)]
    for n in nbrs:
        if n.GetAtomicNum() == 8:
            if n.GetTotalNumHs(includeNeighbors=True) > 0:
                return "acid"
            if any(_is_carbonyl_c(m) and m.GetIdx() != c.GetIdx() for m in n.GetNeighbors()):
                return "anhydride"
            return "ester"
        if n.GetAtomicNum() == 7:
            return "amide"
        if n.GetAtomicNum() in (9, 17, 35, 53):
            return "acyl halide"
    if c.GetTotalNumHs(includeNeighbors=True) > 0:
        return "aldehyde"
    return "ketone"


def _h_shift(parent: Chem.Atom, mh: Chem.Mol) -> tuple[float, str, bool]:
    """(shift, environment label, exchangeable) for hydrogens on `parent`."""
    z = parent.GetAtomicNum()
    heavy = [n for n in parent.GetNeighbors() if n.GetAtomicNum() > 1]
    if z == 8:
        if any(_is_carbonyl_c(n) for n in heavy):
            return 11.5, "COOH", True
        if any(n.GetIsAromatic() for n in heavy):
            return 5.5, "Ar-OH", True
        return 2.5, "OH", True
    if z == 7:
        if any(_is_carbonyl_c(n) for n in heavy):
            return 7.5, "amide NH", True
        if any(n.GetIsAromatic() for n in heavy):
            return 4.0, "Ar-NH", True
        return 1.5, "NH", True
    if z == 16:
        return 1.5, "SH", True
    if z != 6:
        return 3.0, parent.GetSymbol() + "-H", False
    if _is_carbonyl_c(parent):
        return 9.7, "CHO", False
    if parent.GetIsAromatic():
        shift = 7.3
        # crude ortho effects from the ring neighbours' substituents
        for n in heavy:
            if not n.GetIsAromatic():
                continue
            for s in n.GetNeighbors():
                if s.GetIdx() == parent.GetIdx() or s.GetAtomicNum() == 1 or s.GetIsAromatic():
                    continue
                if s.GetAtomicNum() in (7, 8) and not _is_carbonyl_c(s):
                    shift -= 0.4
                elif _is_carbonyl_c(s) or s.GetAtomicNum() == 7:
                    shift += 0.5
        return round(shift, 2), "Ar-H", False
    if parent.GetHybridization() == Chem.HybridizationType.SP:
        return 2.5, "C#C-H", False
    if parent.GetHybridization() == Chem.HybridizationType.SP2:
        shift = 5.4
        for n in heavy:
            if _is_carbonyl_c(n):
                shift += 0.6
            elif n.GetAtomicNum() == 8:
                shift += 1.0
        return round(shift, 2), "C=C-H", False
    nh = parent.GetTotalNumHs(includeNeighbors=True)
    shift = {3: 0.9, 2: 1.3, 1: 1.5}.get(nh, 1.5)
    label = {3: "CH3", 2: "CH2", 1: "CH"}.get(nh, "CH")
    tags: list[str] = []
    for n in heavy:
        zn = n.GetAtomicNum()
        if zn == 8:
            ester_o = any(_is_carbonyl_c(m) for m in n.GetNeighbors() if m.GetIdx() != parent.GetIdx())
            shift += 3.0 if ester_o else 2.4
            tags.append("O")
        elif zn == 7:
            nitro = n.GetFormalCharge() > 0
            shift += 3.4 if nitro else 1.6
            tags.append("NO2" if nitro else "N")
        elif zn == 9:
            shift += 3.2
            tags.append("F")
        elif zn == 17:
            shift += 2.2
            tags.append("Cl")
        elif zn == 35:
            shift += 1.9
            tags.append("Br")
        elif zn == 53:
            shift += 1.4
            tags.append("I")
        elif zn == 16:
            shift += 1.3
            tags.append("S")
        elif zn == 6:
            if _is_carbonyl_c(n):
                shift += 1.2
                tags.append("C=O")
            elif n.GetIsAromatic():
                shift += 1.4
                tags.append("Ar")
            elif n.GetHybridization() == Chem.HybridizationType.SP2:
                shift += 0.8
                tags.append("C=C")
            elif n.GetHybridization() == Chem.HybridizationType.SP:
                shift += 1.1
                tags.append("C#C" if n.GetDegree() == 2 and all(m.GetAtomicNum() == 6 for m in n.GetNeighbors()) else "CN")
    if tags:
        label += "-" + "/".join(tags)
    return round(min(shift, 6.5), 2), label, False


def _multiplicity(parent: Chem.Atom, mh: Chem.Mol, ranks: list[int], exchangeable: bool) -> str:
    """n+1 rule over hydrogens on neighbouring carbons that are not
    equivalent to the observed ones."""
    if exchangeable:
        return "s"
    own = ranks[[n.GetIdx() for n in parent.GetNeighbors() if n.GetAtomicNum() == 1][0]]
    sets: list[int] = []
    for n in parent.GetNeighbors():
        if n.GetAtomicNum() != 6:
            continue
        hs = [h for h in n.GetNeighbors() if h.GetAtomicNum() == 1 and ranks[h.GetIdx()] != own]
        if hs:
            sets.append(len(hs))
    if not sets:
        return "s"
    if len({ranks[h.GetIdx()] for n in parent.GetNeighbors() if n.GetAtomicNum() == 6 for h in n.GetNeighbors() if h.GetAtomicNum() == 1 and ranks[h.GetIdx()] != own}) > 1:
        return "m"
    return _MULT.get(sum(sets), "m")


def _c_shift(c: Chem.Atom) -> tuple[float, str]:
    heavy = [n for n in c.GetNeighbors() if n.GetAtomicNum() > 1]
    nh = c.GetTotalNumHs(includeNeighbors=True)
    kind = {3: "CH3", 2: "CH2", 1: "CH"}.get(nh, "C")
    if _is_carbonyl_c(c):
        ck = _carbonyl_kind(c)
        return {"acid": 178.0, "ester": 170.0, "amide": 172.0, "acyl halide": 170.0, "anhydride": 165.0, "aldehyde": 200.0, "ketone": 208.0}[ck], f"C=O ({ck})"
    if c.GetHybridization() == Chem.HybridizationType.SP:
        if any(n.GetAtomicNum() == 7 for n in heavy):
            return 118.0, "C#N"
        return 80.0, "C#C"
    if c.GetIsAromatic():
        shift = 128.0
        for n in heavy:
            if n.GetIsAromatic():
                continue
            if n.GetAtomicNum() == 8:
                shift += 27
            elif n.GetAtomicNum() == 7:
                shift += 18
            elif n.GetAtomicNum() == 17:
                shift += 6
            elif n.GetAtomicNum() == 6:
                shift += 9
        return round(shift, 1), f"aromatic {kind}"
    if c.GetHybridization() == Chem.HybridizationType.SP2:
        shift = 125.0
        for n in heavy:
            if n.GetAtomicNum() == 8:
                shift += 20
        return round(shift, 1), f"alkene {kind}"
    shift = {3: 15.0, 2: 25.0, 1: 35.0}.get(nh, 40.0)
    tags: list[str] = []
    for n in heavy:
        zn = n.GetAtomicNum()
        if zn == 8:
            shift += 35
            tags.append("O")
        elif zn == 7:
            shift += 20
            tags.append("N")
        elif zn == 17:
            shift += 25
            tags.append("Cl")
        elif zn == 35:
            shift += 20
            tags.append("Br")
        elif zn == 53:
            shift -= 10
            tags.append("I")
        elif zn == 9:
            shift += 70
            tags.append("F")
        elif zn == 16:
            shift += 15
            tags.append("S")
        elif zn == 6:
            if _is_carbonyl_c(n):
                shift += 10
                tags.append("C=O")
            elif n.GetIsAromatic():
                shift += 10
                tags.append("Ar")
            elif n.GetHybridization() == Chem.HybridizationType.SP2:
                shift += 8
                tags.append("C=C")
            else:
                shift += 3  # each extra alkyl carbon
    return round(shift, 1), kind + ("-" + "/".join(tags) if tags else "")


def nmr_local(mol: Chem.Mol) -> dict:
    """Rule-based 1H and 13C: {h: {peaks}, c: {peaks}}. Atom indices refer to
    the heavy-atom mol (hydrogens are reported through their parent)."""
    mh, ranks = equivalence(mol)
    conf = couplings.conformer(mh) if mol.GetNumHeavyAtoms() <= 60 else None
    h_peaks = []
    for cls in _classes(mh, ranks, 1):
        parent = mh.GetAtomWithIdx(cls[0]).GetNeighbors()[0]
        shift, label, exch = _h_shift(parent, mh)
        parents = sorted({mh.GetAtomWithIdx(i).GetNeighbors()[0].GetIdx() for i in cls})
        if exch:
            mult, js = "s", []
        else:
            mult, js = couplings.pattern(couplings.couplings(mh, ranks, conf, cls[0]))
        h_peaks.append({
            "shift": shift,
            "atoms": parents,
            "integration": len(cls),
            "multiplicity": mult,
            "couplings": js,
            "label": label,
            "exchangeable": exch,
        })
    c_peaks = []
    for cls in _classes(mh, ranks, 6):
        shift, label = _c_shift(mh.GetAtomWithIdx(cls[0]))
        c_peaks.append({"shift": shift, "atoms": cls, "integration": len(cls), "label": label})
    h_peaks.sort(key=lambda p: -p["shift"])
    c_peaks.sort(key=lambda p: -p["shift"])
    return {"h": {"peaks": h_peaks}, "c": {"peaks": c_peaks}, "source": "rules", "note": RULES_NOTE}


# ---------------------------------------------------------------- nmrshiftdb2

def _cml_peaks(text: str) -> list[tuple[float, str]]:
    """[(shift, 'aN')] from a nmrshiftdb2 prediction (CML)."""
    root = ET.fromstring(text)
    out = []
    for peak in root.iter():
        if peak.tag.endswith("peak") and "xValue" in peak.attrib and "atomRefs" in peak.attrib:
            for ref in peak.attrib["atomRefs"].split():
                out.append((float(peak.attrib["xValue"]), ref))
    return out


def map_atom_refs(mol: Chem.Mol) -> dict[str, tuple[int, int]]:
    """'aN' -> (heavy atom index, parent heavy atom index). nmrshiftdb2 numbers
    heavy atoms in SMILES order, then appends hydrogens per heavy atom in order."""
    refs: dict[str, tuple[int, int]] = {}
    n = 1
    for a in mol.GetAtoms():
        refs[f"a{n}"] = (a.GetIdx(), a.GetIdx())
        n += 1
    for a in mol.GetAtoms():
        for _ in range(a.GetTotalNumHs(includeNeighbors=True)):
            refs[f"a{n}"] = (-1, a.GetIdx())
            n += 1
    return refs


def merge_nmrshiftdb(local: dict, h_text: str | None, c_text: str | None, mol: Chem.Mol) -> dict:
    """Replace rule shifts with nmrshiftdb2 ones where the service answered."""
    refs = map_atom_refs(mol)
    out = {"h": {"peaks": [dict(p) for p in local["h"]["peaks"]]}, "c": {"peaks": [dict(p) for p in local["c"]["peaks"]]}, "source": "rules", "note": RULES_NOTE}
    used = False
    if c_text:
        by_atom = {refs[r][0]: s for s, r in _cml_peaks(c_text) if r in refs and refs[r][0] >= 0}
        if by_atom:
            for p in out["c"]["peaks"]:
                vals = [by_atom[i] for i in p["atoms"] if i in by_atom]
                if vals:
                    p["shift"] = round(sum(vals) / len(vals), 1)
            out["c"]["peaks"].sort(key=lambda p: -p["shift"])
            used = True
    if h_text:
        by_parent: dict[int, list[float]] = defaultdict(list)
        for s, r in _cml_peaks(h_text):
            if r in refs and refs[r][0] < 0:
                by_parent[refs[r][1]].append(s)
        if by_parent:
            for p in out["h"]["peaks"]:
                vals = [v for i in p["atoms"] for v in by_parent.get(i, [])]
                if vals:
                    p["shift"] = round(sum(vals) / len(vals), 2)
            out["h"]["peaks"].sort(key=lambda p: -p["shift"])
            used = True
    if used:
        out["source"] = "nmrshiftdb2"
        out["note"] = NMR_NOTE
    return out


def nmr(smiles: str) -> tuple[dict, bool]:
    """(nmr dict, complete). complete is False when the lookup was wanted but failed."""
    mol = Chem.MolFromSmiles(smiles)
    local = nmr_local(mol)
    if not enabled() or "[H]" in smiles:
        return local, True
    h_text = c_text = None
    try:
        with httpx.Client(timeout=_timeout(), follow_redirects=True) as client:
            for kind in ("1H", "13C"):
                r = client.get(NMRSHIFTDB.format(quote(smiles, safe=""), kind))
                if r.status_code == 200 and r.text.lstrip().startswith("<cml"):
                    if kind == "1H":
                        h_text = r.text
                    else:
                        c_text = r.text
    except (httpx.HTTPError, ValueError):
        pass
    if not h_text and not c_text:
        return local, False
    try:
        return merge_nmrshiftdb(local, h_text, c_text, mol), bool(h_text and c_text)
    except (ET.ParseError, KeyError, IndexError):
        return local, False


# ---------------------------------------------------------------- IR

# (name, SMARTS, low, high, intensity, shape). Atoms of the match are highlighted.
IR_BANDS: list[tuple[str, str, int, int, str, str]] = [
    ("O-H stretch (carboxylic acid)", "[CX3](=O)[OX2H1]", 2500, 3300, "strong", "very broad"),
    ("O-H stretch (alcohol)", "[CX4][OX2H1]", 3200, 3550, "strong", "broad"),
    ("O-H stretch (phenol)", "c[OX2H1]", 3200, 3550, "strong", "broad"),
    ("N-H stretch (primary amine, two bands)", "[NX3H2][#6]", 3300, 3500, "medium", "sharp"),
    ("N-H stretch (secondary amine)", "[NX3H1]([#6])[#6]", 3300, 3500, "medium", "sharp"),
    ("N-H stretch (amide)", "[CX3](=O)[NX3H1,NX3H2]", 3200, 3500, "medium", "broad"),
    ("N-H stretch (pyrrole / indole)", "[nH]", 3400, 3500, "medium", "sharp"),
    ("C-H stretch (alkyne)", "[CX2]#[CX2H1]", 3260, 3330, "strong", "sharp"),
    ("C-H stretch (aromatic / alkene, sp2)", "[c,$([CX3]=[CX3])][H]", 3010, 3100, "medium", "sharp"),
    ("C-H stretch (alkyl, sp3)", "[CX4][H]", 2850, 2960, "strong", "sharp"),
    ("C-H stretch (aldehyde, two bands)", "[CX3H1](=O)", 2720, 2820, "weak", "sharp"),
    ("C#N stretch (nitrile)", "[CX2]#[NX1]", 2210, 2260, "medium", "sharp"),
    ("C#C stretch (alkyne)", "[CX2]#[CX2]", 2100, 2260, "weak", "sharp"),
    ("C=O stretch (anhydride, two bands)", "[CX3](=O)[OX2][CX3](=O)", 1750, 1820, "strong", "sharp"),
    ("C=O stretch (acyl halide)", "[CX3](=O)[F,Cl,Br,I]", 1780, 1815, "strong", "sharp"),
    ("C=O stretch (ester)", "[CX3](=O)[OX2][#6]", 1735, 1750, "strong", "sharp"),
    ("C=O stretch (aldehyde)", "[CX3H1](=O)[#6]", 1720, 1740, "strong", "sharp"),
    ("C=O stretch (ketone)", "[#6][CX3](=O)[#6]", 1705, 1725, "strong", "sharp"),
    ("C=O stretch (carboxylic acid)", "[CX3](=O)[OX2H1]", 1700, 1725, "strong", "sharp"),
    ("C=O stretch (amide)", "[CX3](=O)[NX3]", 1630, 1690, "strong", "sharp"),
    ("C=C stretch (alkene)", "[CX3]=[CX3]", 1620, 1680, "medium", "sharp"),
    ("C=N stretch (imine)", "[CX3]=[NX2]", 1640, 1690, "medium", "sharp"),
    ("N-H bend (amine)", "[NX3H2][#6]", 1560, 1640, "medium", "sharp"),
    ("N=O stretch (nitro, two bands)", "[NX3+](=O)[O-]", 1350, 1550, "strong", "sharp"),
    ("C=C stretch (aromatic ring)", "c1ccccc1", 1450, 1600, "medium", "sharp"),
    ("C-H bend (alkyl)", "[CX4H2,CX4H3]", 1375, 1470, "medium", "sharp"),
    ("S=O stretch (sulfonyl)", "[SX4](=O)(=O)", 1300, 1350, "strong", "sharp"),
    ("C-O stretch (ester)", "[CX3](=O)[OX2][#6]", 1000, 1300, "strong", "sharp"),
    ("C-O stretch (ether)", "[#6][OX2;!$(O-C=O)][#6]", 1050, 1250, "strong", "sharp"),
    ("C-O stretch (alcohol)", "[CX4][OX2H1]", 1000, 1260, "strong", "sharp"),
    ("C-N stretch (amine)", "[NX3;!$(NC=O)][CX4]", 1020, 1250, "medium", "sharp"),
    ("S=O stretch (sulfoxide)", "[#6][SX3](=O)[#6]", 1030, 1070, "strong", "sharp"),
    ("C-H bend (aromatic, out of plane)", "c[H]", 690, 900, "strong", "sharp"),
    ("C-Cl stretch", "[#6]Cl", 600, 800, "medium", "sharp"),
    ("C-Br stretch", "[#6]Br", 500, 600, "medium", "sharp"),
]
_IR_COMPILED = [(name, Chem.MolFromSmarts(s), lo, hi, inten, shape) for name, s, lo, hi, inten, shape in IR_BANDS]


def ir_bands(mol: Chem.Mol) -> list[dict]:
    mh = Chem.AddHs(mol)
    out = []
    for name, patt, lo, hi, inten, shape in _IR_COMPILED:
        matches = mh.GetSubstructMatches(patt)
        if not matches:
            continue
        atoms = sorted({i for m in matches for i in m if i < mol.GetNumAtoms()})
        out.append({"name": name, "low": lo, "high": hi, "centre": (lo + hi) // 2, "intensity": inten, "shape": shape, "atoms": atoms})
    return out


# ---------------------------------------------------------------- MS

ISOTOPES: dict[str, list[tuple[float, float]]] = {
    "H": [(1.007825, 0.999885), (2.014102, 0.000115)],
    "C": [(12.0, 0.9893), (13.003355, 0.0107)],
    "N": [(14.003074, 0.99636), (15.000109, 0.00364)],
    "O": [(15.994915, 0.99757), (16.999132, 0.00038), (17.999160, 0.00205)],
    "F": [(18.998403, 1.0)],
    "P": [(30.973762, 1.0)],
    "S": [(31.972071, 0.9499), (32.971459, 0.0075), (33.967867, 0.0425), (35.967081, 0.0001)],
    "Cl": [(34.968853, 0.7576), (36.965903, 0.2424)],
    "Br": [(78.918337, 0.5069), (80.916291, 0.4931)],
    "I": [(126.904473, 1.0)],
    "Si": [(27.976927, 0.92223), (28.976495, 0.04685), (29.973770, 0.03092)],
    "B": [(10.012937, 0.199), (11.009305, 0.801)],
    "Na": [(22.989770, 1.0)],
    "K": [(38.963707, 0.932581), (40.961826, 0.067302)],
    "Mg": [(23.985042, 0.7899), (24.985837, 0.1000), (25.982593, 0.1101)],
    "Fe": [(53.939611, 0.05845), (55.934938, 0.91754), (56.935394, 0.02119), (57.933276, 0.00282)],
    "Zn": [(63.929142, 0.4917), (65.926034, 0.2773), (66.927128, 0.0404), (67.924845, 0.1845), (69.925319, 0.0061)],
    "Cu": [(62.929598, 0.6915), (64.927790, 0.3085)],
}
_PT = Chem.GetPeriodicTable()


def _element_counts(mol: Chem.Mol, atoms: list[int] | None = None) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    idxs = range(mol.GetNumAtoms()) if atoms is None else atoms
    for i in idxs:
        a = mol.GetAtomWithIdx(i)
        counts[a.GetSymbol()] += 1
        counts["H"] += a.GetTotalNumHs(includeNeighbors=True)
    return dict(counts)


def isotope_pattern(counts: dict[str, int], threshold: float = 0.001) -> list[dict]:
    """Molecular-ion isotope cluster: [{mz (exact, abundance weighted),
    nominal, rel (% of base)}] aggregated per nominal mass."""
    # Work in exact masses (binned to 0.01 Da); aggregate per nominal mass at the end.
    peaks: list[tuple[float, float]] = [(0.0, 1.0)]
    for sym, n in counts.items():
        iso = ISOTOPES.get(sym) or [(_PT.GetMostCommonIsotopeMass(sym), 1.0)]
        for _ in range(n):
            nxt: dict[int, tuple[float, float]] = {}
            for m, p in peaks:
                for im, ip in iso:
                    mm, pp = m + im, p * ip
                    if pp < 1e-7:
                        continue
                    key = round(mm * 100)
                    if key in nxt:
                        om, op = nxt[key]
                        nxt[key] = ((om * op + mm * pp) / (op + pp), op + pp)
                    else:
                        nxt[key] = (mm, pp)
            peaks = list(nxt.values())
    by_nominal: dict[int, tuple[float, float]] = {}
    for m, p in peaks:
        k = int(round(m))
        if k in by_nominal:
            om, op = by_nominal[k]
            by_nominal[k] = ((om * op + m * p) / (op + p), op + p)
        else:
            by_nominal[k] = (m, p)
    top = max(p for _, p in by_nominal.values())
    out = [
        {"mz": round(m, 4), "nominal": k, "rel": round(100 * p / top, 2)}
        for k, (m, p) in sorted(by_nominal.items())
        if p / top >= threshold
    ]
    return out


def _formula(counts: dict[str, int]) -> str:
    order = ["C", "H"] + sorted(k for k in counts if k not in ("C", "H"))
    return "".join(f"{s}{counts[s] if counts[s] > 1 else ''}" for s in order if counts.get(s))


def _mono_mass(counts: dict[str, int]) -> float:
    return sum((ISOTOPES.get(s) or [(_PT.GetMostCommonIsotopeMass(s), 1.0)])[0][0] * n for s, n in counts.items())


_ELECTRON = 0.000549


def ms_fragments(mol: Chem.Mol, limit: int = 8) -> list[dict]:
    """Cations from single acyclic bond cleavages, ranked by a crude
    stability score (resonance, alpha-heteroatom, acylium, substitution)."""
    out: list[dict] = []
    for bond in mol.GetBonds():
        if bond.IsInRing() or bond.GetBondType() != Chem.BondType.SINGLE:
            continue
        a, b = bond.GetBeginAtom(), bond.GetEndAtom()
        if a.GetAtomicNum() == 1 or b.GetAtomicNum() == 1:
            continue
        frag = Chem.FragmentOnBonds(mol, [bond.GetIdx()], addDummies=False)
        pieces = Chem.GetMolFrags(frag, asMols=False, sanitizeFrags=False)
        if len(pieces) != 2:
            continue
        for cation_atoms, neutral_atoms in (pieces, pieces[::-1]):
            cation_atoms, neutral_atoms = list(cation_atoms), list(neutral_atoms)
            charged = a if a.GetIdx() in cation_atoms else b
            score = 0.0
            reasons = []
            if _is_carbonyl_c(charged):
                score += 3
                reasons.append("acylium")
            if any(n.GetIsAromatic() or n.GetHybridization() == Chem.HybridizationType.SP2 for n in charged.GetNeighbors() if n.GetIdx() in cation_atoms and n.GetAtomicNum() == 6):
                score += 3
                reasons.append("resonance stabilised (benzylic/allylic)")
            if any(n.GetAtomicNum() in (7, 8, 16) for n in charged.GetNeighbors() if n.GetIdx() in cation_atoms) and not _is_carbonyl_c(charged):
                score += 2.5
                reasons.append("alpha-cleavage (heteroatom lone pair)")
            if charged.GetIsAromatic():
                score += 1
                reasons.append("aryl cation")
            heavy_nbrs = sum(1 for n in charged.GetNeighbors() if n.GetIdx() in cation_atoms and n.GetAtomicNum() > 1)
            score += {0: 0, 1: 0.5, 2: 1.0}.get(heavy_nbrs, 1.5)
            if charged.GetAtomicNum() in (17, 35, 53, 9):
                score -= 3  # halonium unlikely
            cc = _element_counts(mol, cation_atoms)
            nc = _element_counts(mol, neutral_atoms)
            out.append({
                "mz": round(_mono_mass(cc) - _ELECTRON, 4),
                "nominal": int(round(_mono_mass(cc))),
                "formula": _formula(cc) + "+",
                "loss": _formula(nc),
                "atoms": sorted(cation_atoms),
                "score": round(score, 1),
                "why": ", ".join(reasons) or "simple cleavage",
                "bond": bond.GetIdx(),
            })
    out.sort(key=lambda f: (-f["score"], -f["nominal"]))
    seen: set[tuple[int, str]] = set()
    uniq = []
    for f in out:
        key = (f["nominal"], f["formula"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f)
        if len(uniq) >= limit:
            break
    return uniq


def ms_predict(mol: Chem.Mol) -> dict:
    from . import msfrag

    counts = _element_counts(mol)
    return {
        "formula": rdMolDescriptors.CalcMolFormula(mol),
        "exact_mass": round(Descriptors.ExactMolWt(mol), 4),
        "nominal_mass": int(round(_mono_mass(counts))),
        "isotopes": isotope_pattern(counts),
        "fragments": ms_fragments(mol),
        "tree": msfrag.tree(mol)["nodes"],
    }


# ---------------------------------------------------------------- NIST WebBook

_NUM = re.compile(r"[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")


def parse_jcamp(text: str) -> dict:
    """Minimal JCAMP-DX reader for NIST files: headers plus XYDATA
    (X++(Y..Y)) or PEAK TABLE (XY..XY). Returns {headers, x, y}."""
    headers: dict[str, str] = {}
    x: list[float] = []
    y: list[float] = []
    mode = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("##"):
            key, _, val = line[2:].partition("=")
            key = key.strip().upper()
            val = val.strip()
            if key in ("XYDATA", "PEAK TABLE"):
                mode = "xy" if "X++" in val else "pairs"
                continue
            if key == "END":
                mode = None
            headers[key] = val
            continue
        if line.startswith("$$") or mode is None:
            continue
        nums = [float(t) for t in _NUM.findall(line)]
        if mode == "xy" and len(nums) >= 2:
            xf = float(headers.get("XFACTOR", "1") or 1)
            yf = float(headers.get("YFACTOR", "1") or 1)
            x0 = nums[0] * xf
            ys = nums[1:]
            first = float(headers.get("FIRSTX", "0") or 0)
            last = float(headers.get("LASTX", "0") or 0)
            npts = int(float(headers.get("NPOINTS", "0") or 0))
            dx = (last - first) / (npts - 1) if npts > 1 else float(headers.get("DELTAX", "1") or 1)
            for i, yv in enumerate(ys):
                x.append(x0 + i * dx)
                y.append(yv * yf)
        elif mode == "pairs":
            for i in range(0, len(nums) - 1, 2):
                x.append(nums[i])
                y.append(nums[i + 1])
    return {"headers": headers, "x": x, "y": y}


def _downsample(x: list[float], y: list[float], limit: int = 1500) -> tuple[list[float], list[float]]:
    if len(x) <= limit:
        return x, y
    step = math.ceil(len(x) / limit)
    return x[::step], y[::step]


def _nist_id(client: httpx.Client, inchi: str) -> str | None:
    r = client.get(NIST_SEARCH.format(quote(inchi, safe="")))
    if r.status_code != 200:
        return None
    # The compound's own section links carry Mask=; earlier ID= links can be
    # related species (isotopologues) listed under "Other data".
    for patt in (r"ID=(C\d+)&(?:amp;)?Units=SI&(?:amp;)?Mask=", r"ID=(C\d+)&(?:amp;)?Type=", r"ID=(C\d+)"):
        m = re.search(patt, r.text)
        if m:
            return m.group(1)
    return None


def _nist_ir(client: httpx.Client, nist_id: str) -> dict | None:
    for idx in range(5):
        r = client.get(NIST_JCAMP.format(nist_id, "IR", idx))
        if r.status_code != 200 or "##TITLE" not in r.text:
            break
        data = parse_jcamp(r.text)
        if not data["x"]:
            continue
        h = data["headers"]
        y = data["y"]
        if h.get("YUNITS", "").upper().startswith("ABSORBANCE"):
            y = [10 ** (-max(v, 0.0)) for v in y]
        else:
            top = max(y) or 1.0
            y = [v / top if top > 1.5 else v for v in y]  # some files use percent
        xs, ys = _downsample(data["x"], [round(v, 4) for v in y])
        return {
            "x": [round(v, 1) for v in xs],
            "y": ys,
            "state": h.get("STATE", "").lower() or None,
            "title": h.get("TITLE", ""),
            "url": NIST_PAGE.format(nist_id, "IR-SPEC"),
        }
    return None


def _nist_ms(client: httpx.Client, nist_id: str) -> dict | None:
    r = client.get(NIST_JCAMP.format(nist_id, "Mass", 0))
    if r.status_code != 200 or "##TITLE" not in r.text:
        return None
    data = parse_jcamp(r.text)
    if not data["x"]:
        return None
    top = max(data["y"]) or 1.0
    peaks = [{"mz": round(m, 1), "rel": round(100 * i / top, 1)} for m, i in zip(data["x"], data["y"]) if i / top >= 0.005]
    return {"peaks": peaks, "url": NIST_PAGE.format(nist_id, "Mass")}


def nist(mol: Chem.Mol, kind: str) -> tuple[dict | None, bool]:
    """Experimental spectrum ('ir' or 'ms') from NIST, or None. Second value
    is False when the lookup could not be completed (network trouble)."""
    if not enabled():
        return None, True
    inchi = Chem.MolToInchi(mol)
    if not inchi:
        return None, True
    try:
        with httpx.Client(timeout=_timeout(), follow_redirects=True, headers={"User-Agent": "chem-draw-clone (educational)"}) as client:
            nist_id = _nist_id(client, inchi)
            if nist_id is None:
                return None, True
            return (_nist_ir if kind == "ir" else _nist_ms)(client, nist_id), True
    except (httpx.HTTPError, ValueError):
        return None, False


# ---------------------------------------------------------------- entry points

def build(smiles: str, kind: str) -> tuple[dict, bool]:
    """(payload, complete). kind is 'nmr' | 'ir' | 'ms'."""
    if kind == "nmr":
        return nmr(smiles)
    mol = Chem.MolFromSmiles(smiles)
    experimental, complete = nist(mol, kind)
    note = NIST_NOTE if experimental else ("No experimental spectrum for this compound in the NIST WebBook." if enabled() else "")
    if kind == "ir":
        return {"predicted": ir_bands(mol), "experimental": experimental, "note": note}, complete
    data = ms_predict(mol)
    data["experimental"] = experimental
    data["note"] = note
    return data, complete
