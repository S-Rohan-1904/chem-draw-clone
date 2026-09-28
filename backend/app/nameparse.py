"""Best-effort breakdown of a systematic name into its parts (stereo
descriptors, locants, multipliers, substituents, parent, unsaturation,
suffix) with substituent atoms located on the structure by SMARTS.

This is a teaching aid, not a parser: OPSIN does the real parsing. Tokens
it does not recognise are returned as 'other'.
"""

from __future__ import annotations

import re

from rdkit import Chem

# Substituent prefix -> SMARTS for the group as attached to the parent.
SUBSTITUENTS: dict[str, str] = {
    "methyl": "[CH3;!$([CH3][OX2,SX2])]",
    "ethyl": "[CH2;!$([CH2][O,N,S])][CH3]",
    "propyl": "[CH2][CH2][CH3]",
    "isopropyl": "[CH1;!$([CH1][O,N,S])]([CH3])[CH3]",
    "butyl": "[CH2][CH2][CH2][CH3]",
    "isobutyl": "[CH2][CH1]([CH3])[CH3]",
    "sec-butyl": "[CH1]([CH3])[CH2][CH3]",
    "tert-butyl": "[CX4]([CH3])([CH3])[CH3]",
    "pentyl": "[CH2][CH2][CH2][CH2][CH3]",
    "hexyl": "[CH2][CH2][CH2][CH2][CH2][CH3]",
    "vinyl": "[CH]=[CH2]",
    "ethenyl": "[CH]=[CH2]",
    "allyl": "[CH2][CH]=[CH2]",
    "phenyl": "c1ccccc1",
    "benzyl": "[CH2]c1ccccc1",
    "fluoro": "[F]",
    "chloro": "[Cl]",
    "bromo": "[Br]",
    "iodo": "[I]",
    "hydroxy": "[OX2H1]",
    "oxo": "[OX1]=*",
    "amino": "[NX3H2]",
    "methylamino": "[NX3H1][CH3]",
    "dimethylamino": "[NX3]([CH3])[CH3]",
    "nitro": "[N+](=O)[O-]",
    "cyano": "[CX2]#[NX1]",
    "methoxy": "[OX2]([CH3])[#6]",
    "ethoxy": "[OX2]([CH2][CH3])[#6]",
    "phenoxy": "[OX2](c1ccccc1)[#6]",
    "acetyl": "[CX3](=O)[CH3]",
    "formyl": "[CX3H1]=O",
    "carboxy": "[CX3](=O)[OX2H1]",
    "sulfanyl": "[SX2H1]",
    "methylsulfanyl": "[SX2][CH3]",
    "mercapto": "[SX2H1]",
    "trifluoromethyl": "[CX4](F)(F)F",
}

PARENTS = [
    "meth", "eth", "prop", "but", "pent", "hex", "hept", "oct", "non", "dec", "undec", "dodec",
    "benzene", "benz", "naphthalene", "anthracene", "phenanthrene", "toluene", "phenol", "aniline", "pyridine", "pyrimidine", "pyrrole", "furan",
    "thiophene", "imidazole", "indole", "quinoline", "purine", "piperidine", "pyrrolidine", "morpholine", "piperazine", "oxirane", "oxolane", "oxane",
    "cyclopropane", "cyclobutane", "cyclopentane", "cyclohexane", "cycloheptane", "cyclooctane",
]
SUFFIXES = [
    "oic acid", "dioic acid", "carboxylic acid", "dicarboxylic acid", "carbaldehyde", "carbonitrile", "carboxamide", "carboxylate",
    "amide", "amine", "diamine", "nitrile", "oate", "dial", "dione", "diol", "triol", "one", "ol", "al", "ate", "ide", "ium",
]
MULTIPLIERS = ["tetrakis", "tris", "bis", "tetra", "penta", "hexa", "hepta", "octa", "tri", "di"]
INFIXES = ["adiene", "atriene", "adiyne", "enyne", "ene", "yne", "ane", "en", "yn", "an", "diene", "triene"]

_SUB_ALT = "|".join(sorted(map(re.escape, SUBSTITUENTS), key=len, reverse=True))
_PARENT_ALT = "|".join(sorted(map(re.escape, PARENTS), key=len, reverse=True))
_SUFFIX_ALT = "|".join(sorted(map(re.escape, SUFFIXES), key=len, reverse=True))
_MULT_ALT = "|".join(MULTIPLIERS)
_INFIX_ALT = "|".join(sorted(INFIXES, key=len, reverse=True))

TOKEN_RE = re.compile(
    r"(?P<stereo>\((?:\s*[0-9a-z]*[RSEZrsez]\s*,?)+\)|\b(?:cis|trans|meso|rac|rel)\b)"
    r"|(?P<locant>(?:\d+[a-z]?|(?-i:[NO]))(?:,(?:\d+[a-z]?|(?-i:[NO])))*(?=[-,]|$))"
    rf"|(?P<substituent>{_SUB_ALT})"
    r"|(?P<cyclo>cyclo|bicyclo|spiro)"
    rf"|(?P<suffix>{_SUFFIX_ALT})\b"
    rf"|(?P<parent>{_PARENT_ALT})(?=a|e|y|-|$|\b)"
    rf"|(?P<multiplier>{_MULT_ALT})(?=[a-z])"
    rf"|(?P<infix>{_INFIX_ALT})"
    r"|(?P<sep>[-\s,\[\]()]+)"
    r"|(?P<other>.)",
    re.IGNORECASE,
)

COLOURS = {
    "stereo": "#7c3aed",
    "locant": "#6b7280",
    "multiplier": "#0891b2",
    "substituent": "#dc2626",
    "cyclo": "#0369a1",
    "parent": "#0369a1",
    "infix": "#059669",
    "suffix": "#d97706",
    "sep": "",
    "other": "#9ca3af",
}

LEGEND = {
    "stereo": "Stereo descriptor: configuration at a centre or double bond",
    "locant": "Locant: position number on the parent chain or ring",
    "multiplier": "Multiplier: how many of the following group",
    "substituent": "Substituent: group attached to the parent",
    "cyclo": "Ring prefix",
    "parent": "Parent: longest chain or ring bearing the principal group",
    "infix": "Saturation: an = single bonds, en = double bond, yn = triple bond",
    "suffix": "Suffix: principal functional group",
    "other": "Not recognised by the breakdown (OPSIN may still read it)",
}


_MULT_COUNT = {"di": 2, "bis": 2, "tri": 3, "tris": 3, "tetra": 4, "tetrakis": 4, "penta": 5, "hexa": 6, "hepta": 7, "octa": 8}


def tokenize(name: str) -> list[dict]:
    tokens: list[dict] = []
    for m in TOKEN_RE.finditer(name):
        kind = m.lastgroup or "other"
        text = m.group(0)
        if kind == "other" and tokens and tokens[-1]["kind"] == "other":
            tokens[-1]["text"] += text  # merge runs of unrecognised letters
            continue
        tokens.append({"text": text, "kind": kind})
    return tokens


def breakdown(name: str, smiles: str) -> dict:
    mol = Chem.MolFromSmiles(smiles)
    tokens = tokenize(name)
    used: set[int] = set()
    # Locate substituents on the structure. Each token gets the next unused match.
    for tok in tokens:
        if tok["kind"] != "substituent" or mol is None:
            continue
        patt = Chem.MolFromSmarts(SUBSTITUENTS[tok["text"].lower()])
        matches = [set(m) for m in mol.GetSubstructMatches(patt)] if patt is not None else []
        fresh = [m for m in matches if not (m & used)]
        # a multiplier before this token means several copies: take them all
        idx = tokens.index(tok)
        prev = next((t for t in reversed(tokens[:idx]) if t["kind"] != "sep"), None)
        count = _MULT_COUNT.get(prev["text"].lower(), 1) if (prev and prev["kind"] == "multiplier") else 1
        # Prefer groups hanging off branch points: those are the substituents, chain ends are the parent.
        fresh.sort(key=lambda m: -max((n.GetDegree() for i in m for n in mol.GetAtomWithIdx(i).GetNeighbors() if n.GetIdx() not in m), default=0))
        take = fresh[:count]
        atoms: set[int] = set()
        for m in take:
            atoms |= m
        used |= atoms
        tok["atoms"] = sorted(atoms)
    parent_atoms = [a.GetIdx() for a in mol.GetAtoms() if a.GetIdx() not in used] if mol is not None else []
    for tok in tokens:
        if tok["kind"] in ("parent", "cyclo", "infix"):
            tok["atoms"] = parent_atoms
    kinds = sorted({t["kind"] for t in tokens if t["kind"] != "sep"})
    return {
        "tokens": tokens,
        "legend": [{"kind": k, "colour": COLOURS[k], "text": LEGEND[k]} for k in kinds if k in LEGEND],
        "colours": COLOURS,
    }
