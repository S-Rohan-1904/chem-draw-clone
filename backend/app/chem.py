"""Chemistry core: IUPAC name / SMILES -> 2D SVG, 3D mol block, stereo report.

All stereochemistry comes from the input. OPSIN encodes descriptors in the
input name (R/S, E/Z, cis/trans, D/L, ...) into the SMILES; nothing is guessed.
Unspecified centres are reported as "?" so the UI can warn the user.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from rdkit import Chem, RDLogger

from . import groups as _groups
from . import opsin
from rdkit.Chem import AllChem, Descriptors, rdCIPLabeler, rdDepictor, rdMolDescriptors
from rdkit.Chem.Draw import rdMolDraw2D
from rdkit.Chem.EnumerateStereoisomers import EnumerateStereoisomers, StereoEnumerationOptions

RDLogger.DisableLog("rdApp.*")
rdDepictor.SetPreferCoordGen(True)


_UNICODE_MAP = str.maketrans({
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-",
    "\u2018": "'", "\u2019": "'", "\u2032": "'", "\u201c": '"', "\u201d": '"',
    "\u00a0": " ", "\u2009": " ", "\u202f": " ",
})


def normalise_name(text: str) -> str:
    """Clean up copy-paste artefacts: unicode dashes/quotes, stray spaces, trailing punctuation."""
    text = text.translate(_UNICODE_MAP)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip("\"'")
    text = re.sub(r"[.,;:!?]+$", "", text).strip()
    return text


class ChemError(ValueError):
    """Raised when input cannot be interpreted as a name or SMILES."""

    def __init__(self, message: str, opsin_error: str = ""):
        super().__init__(message)
        self.opsin_error = opsin_error


@dataclass
class Resolved:
    smiles: str
    source: str  # "iupac" | "smiles" | "molfile"
    warnings: list[str] = field(default_factory=list)
    normalised: str = ""


@dataclass
class StereoCenter:
    atom_idx: int
    symbol: str
    label: str  # "R" | "S" | "r" | "s" (pseudo-asymmetric) | "?"


@dataclass
class StereoBond:
    bond_idx: int
    atoms: tuple[int, int]
    label: str  # "E" | "Z" | "e" | "z" | "?"


@dataclass
class StereoReport:
    centers: list[StereoCenter] = field(default_factory=list)
    double_bonds: list[StereoBond] = field(default_factory=list)

    @property
    def unspecified(self) -> bool:
        return any(c.label == "?" for c in self.centers) or any(
            b.label == "?" for b in self.double_bonds
        )


@dataclass
class MoleculeResult:
    input_text: str
    source: str  # "iupac" | "smiles"
    smiles: str
    svg: str
    molblock: str
    stereo: StereoReport
    formula: str
    mw: float
    inchi: str
    inchikey: str
    warnings: list[str] = field(default_factory=list)
    normalised_input: str = ""
    properties: dict = field(default_factory=dict)
    groups: list[dict] = field(default_factory=list)


def _looks_like_smiles(text: str) -> bool:
    return " " not in text and Chem.MolFromSmiles(text) is not None


def _stereo_note(opsin_error: str) -> str:
    m = re.search(r'value="([A-Za-z]+)"', opsin_error)
    loc = re.search(r'locant="([^"]*)"', opsin_error)
    desc = f"({loc.group(1)}{m.group(1)})" if (m and loc) else (f"({m.group(1)})" if m else "A stereo descriptor")
    where = f"position {loc.group(1)}" if loc else "that position"
    return f"{desc} ignored: {where} is not a stereocentre or stereogenic double bond in this name."


def _is_molfile(text: str) -> bool:
    return "M  END" in text or "V2000" in text or "V3000" in text


def resolve_molfile(text: str) -> Resolved:
    """Molfile from the editor -> Resolved. Wedge/hash bonds define stereo."""
    # Molfiles start with a title line that may be blank; only trim trailing space.
    mol = Chem.MolFromMolBlock(text.lstrip("\r\n ").rstrip() if not text.startswith("\n") else text.rstrip(), sanitize=True, removeHs=True)
    if mol is None:
        mol = Chem.MolFromMolBlock("\n" + text.strip(), sanitize=True, removeHs=True)
    if mol is None:
        raise ChemError("Could not read the drawn structure.")
    if mol.GetNumAtoms() == 0:
        raise ChemError("Nothing drawn yet.")
    Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
    return Resolved(Chem.MolToSmiles(mol, isomericSmiles=True), "molfile", [], "")


def resolve_full(text: str) -> Resolved:
    """Name, SMILES or molfile -> Resolved. OPSIN strict first, then OPSIN
    ignoring bad stereo (with a warning), then SMILES."""
    if _is_molfile(text):
        return resolve_molfile(text)
    raw = text.strip()
    text = normalise_name(raw)
    if not text:
        raise ChemError("Input is empty.")

    smiles, opsin_error = opsin.strict.convert(text)
    if smiles:
        return Resolved(smiles, "iupac", [], text)

    if "stereoChemistry" in opsin_error or "stereo" in opsin_error.lower():
        smiles, lenient_error = opsin.lenient_stereo.convert(text)
        if smiles:
            return Resolved(smiles, "iupac", [_stereo_note(lenient_error or opsin_error)], text)

    if _looks_like_smiles(text):
        return Resolved(text, "smiles", [], text)

    raise ChemError(
        f"Could not interpret '{text}' as an IUPAC name or SMILES. {opsin_error}".strip(),
        opsin_error,
    )


def resolve(text: str) -> tuple[str, str]:
    """Return (smiles, source). Kept for callers that only need the pair."""
    r = resolve_full(text)
    return r.smiles, r.source


_CW, _CCW = Chem.ChiralType.CHI_TETRAHEDRAL_CW, Chem.ChiralType.CHI_TETRAHEDRAL_CCW
_MAX_ENUM_CANDIDATES = 8


def _flip_changes_molecule(mol: Chem.Mol, idx: int) -> bool:
    """True if setting this atom CW vs CCW (others untouched) gives two different molecules."""
    seen = set()
    for tag in (_CW, _CCW):
        c = Chem.Mol(mol)
        c.GetAtomWithIdx(idx).SetChiralTag(tag)
        Chem.AssignStereochemistry(c, cleanIt=True, force=True)
        seen.add(Chem.MolToSmiles(c))
    return len(seen) == 2


def _unspecified_centres(mol: Chem.Mol) -> list[int]:
    """Untagged atoms that are genuinely stereogenic.

    RDKit's candidate finder flags bridgeheads in cages (norbornane, adamantane,
    cubane) and dependent ring positions. Cheap check first: flipping the atom
    alone yields a different molecule. Otherwise enumerate stereoisomers over
    the remaining candidates with 3D embedding; more than one embeddable
    isomer means the stereo is real (decalin, 1,4-disubstituted rings).
    """
    candidates = [
        i for i, label in Chem.FindMolChiralCenters(mol, includeUnassigned=True, useLegacyImplementation=False)
        if label == "?"
    ]
    if not candidates:
        return []
    bridgeheads = _small_bridgeheads(mol, candidates)
    real = [i for i in candidates if i not in bridgeheads and _flip_changes_molecule(mol, i)]
    rest = [i for i in candidates if i not in real]
    if not rest:
        return real
    if len(rest) > _MAX_ENUM_CANDIDATES:
        return candidates  # too many to enumerate; treat as unspecified
    probe = Chem.Mol(mol)
    for i in real:  # fix the independent ones so only the dependent set varies
        probe.GetAtomWithIdx(i).SetChiralTag(_CW)
    opts = StereoEnumerationOptions(tryEmbedding=False, onlyUnassigned=True, unique=True, maxIsomers=64)
    energies: dict[str, float] = {}
    for iso in EnumerateStereoisomers(probe, options=opts):
        e = _embed_energy(iso)
        if e is not None:
            key = Chem.MolToSmiles(iso)
            energies[key] = min(e, energies.get(key, e))
    if not energies:
        return real
    # Distance geometry can still find coordinates for strained in/out
    # bridged isomers; ignore anything far above the best isomer.
    floor = min(energies.values())
    feasible = [k for k, e in energies.items() if e <= floor + _STRAIN_WINDOW]
    return real + rest if len(feasible) > 1 else real


_STRAIN_WINDOW = 40.0  # kcal/mol


def _small_bridgeheads(mol: Chem.Mol, candidates: list[int]) -> set[int]:
    """Bridgehead pairs of small bridged bicycles (norbornane, bicyclo[3.3.1]).

    The single-atom flip test is meaningless for these (flipping one
    bridgehead alone gives an impossible in/out isomer), so they always go
    through the joint enumeration with embedding.
    """
    rings = [set(r) for r in mol.GetRingInfo().AtomRings()]
    out: set[int] = set()
    for a in candidates:
        for b in candidates:
            if b <= a or mol.GetBondBetweenAtoms(a, b) is not None:
                continue
            shared = [r for r in rings if a in r and b in r]
            if len(shared) >= 2 and max(len(r) for r in shared) <= 8:
                out.update((a, b))
    return out


def _embed_energy(mol: Chem.Mol) -> float | None:
    """MMFF energy of an embedded geometry reproducing the mol's stereo, or None."""
    try:
        mh = embed_3d(mol, max_tries=2)
    except ChemError:
        return None
    props = AllChem.MMFFGetMoleculeProperties(mh)
    if props is None:
        return 0.0
    return AllChem.MMFFGetMoleculeForceField(mh, props).CalcEnergy()


def _stereo_report(mol: Chem.Mol) -> StereoReport:
    Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
    rdCIPLabeler.AssignCIPLabels(mol)
    report = StereoReport()
    for atom in mol.GetAtoms():
        cip = atom.GetPropsAsDict().get("_CIPCode", "")
        if cip in ("R", "S", "r", "s"):
            report.centers.append(StereoCenter(atom.GetIdx(), atom.GetSymbol(), cip))
    for idx in _unspecified_centres(mol):
        report.centers.append(StereoCenter(idx, mol.GetAtomWithIdx(idx).GetSymbol(), "?"))
    report.centers.sort(key=lambda c: c.atom_idx)
    for bond in mol.GetBonds():
        if bond.GetBondType() != Chem.BondType.DOUBLE:
            continue
        cip = bond.GetPropsAsDict().get("_CIPCode", "")
        if cip in ("E", "Z", "e", "z"):
            label = cip
        elif bond.GetStereo() == Chem.BondStereo.STEREONONE and _is_stereogenic_double(bond):
            label = "?"
        else:
            continue
        report.double_bonds.append(
            StereoBond(bond.GetIdx(), (bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()), label)
        )
    return report


def _is_stereogenic_double(bond: Chem.Bond) -> bool:
    """Acyclic C=C whose ends each carry two different substituents (rough check)."""
    if bond.IsInRing():
        return False
    for atom in (bond.GetBeginAtom(), bond.GetEndAtom()):
        if atom.GetAtomicNum() != 6:
            return False
        nbrs = [n for n in atom.GetNeighbors() if n.GetIdx() not in (bond.GetBeginAtomIdx(), bond.GetEndAtomIdx())]
        if atom.GetTotalNumHs() >= 2 or len(nbrs) < 1:
            return False
        if len(nbrs) == 2 and _same_substituent(atom, nbrs[0], nbrs[1]):
            return False
    return True


def _same_substituent(center: Chem.Atom, a: Chem.Atom, b: Chem.Atom) -> bool:
    # Cheap symmetry check via canonical ranks.
    ranks = list(Chem.CanonicalRankAtoms(center.GetOwningMol(), breakTies=False))
    return ranks[a.GetIdx()] == ranks[b.GetIdx()]


def render_svg(mol: Chem.Mol, width: int = 480, height: int = 360) -> str:
    m = Chem.Mol(mol)
    rdDepictor.Compute2DCoords(m)
    Chem.WedgeMolBonds(m, m.GetConformer())
    drawer = rdMolDraw2D.MolDraw2DSVG(width, height)
    opts = drawer.drawOptions()
    opts.addStereoAnnotation = True
    opts.clearBackground = False
    opts.bondLineWidth = 2
    drawer.DrawMolecule(m)
    drawer.FinishDrawing()
    return drawer.GetDrawingText()


def render_svg_highlight(mol: Chem.Mol, atoms: list[int], colour: str, width: int = 480, height: int = 360) -> str:
    """2D depiction with the given atoms (and bonds between them) highlighted."""
    m = Chem.Mol(mol)
    rdDepictor.Compute2DCoords(m)
    Chem.WedgeMolBonds(m, m.GetConformer())
    atom_set = {a for a in atoms if 0 <= a < m.GetNumAtoms()}
    bonds = [b.GetIdx() for b in m.GetBonds() if b.GetBeginAtomIdx() in atom_set and b.GetEndAtomIdx() in atom_set]
    rgb = tuple(int(colour.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)) + (0.35,)
    drawer = rdMolDraw2D.MolDraw2DSVG(width, height)
    opts = drawer.drawOptions()
    opts.addStereoAnnotation = True
    opts.clearBackground = False
    opts.bondLineWidth = 2
    drawer.DrawMolecule(
        m,
        highlightAtoms=sorted(atom_set),
        highlightBonds=bonds,
        highlightAtomColors={a: rgb for a in atom_set},
        highlightBondColors={b: rgb for b in bonds},
    )
    drawer.FinishDrawing()
    return drawer.GetDrawingText()


def render_png(mol: Chem.Mol, width: int = 1200, height: int = 900) -> bytes:
    m = Chem.Mol(mol)
    rdDepictor.Compute2DCoords(m)
    Chem.WedgeMolBonds(m, m.GetConformer())
    drawer = rdMolDraw2D.MolDraw2DCairo(width, height)
    opts = drawer.drawOptions()
    opts.addStereoAnnotation = True
    opts.bondLineWidth = 3
    drawer.DrawMolecule(m)
    drawer.FinishDrawing()
    return drawer.GetDrawingText()


def _cip_labels(mol: Chem.Mol) -> dict[str, str]:
    """{'a<idx>': 'R'|'S', 'b<idx>': 'E'|'Z'} for every labelled atom/bond."""
    m = Chem.Mol(mol)
    Chem.AssignStereochemistry(m, cleanIt=True, force=True)
    rdCIPLabeler.AssignCIPLabels(m)
    labels: dict[str, str] = {}
    for a in m.GetAtoms():
        cip = a.GetPropsAsDict().get("_CIPCode")
        if cip in ("R", "S", "r", "s"):
            labels[f"a{a.GetIdx()}"] = cip
    for b in m.GetBonds():
        cip = b.GetPropsAsDict().get("_CIPCode")
        if cip in ("E", "Z", "e", "z"):
            labels[f"b{b.GetIdx()}"] = cip
    return labels


EMBED_TIMEOUT_S = int(os.environ.get("CHEM_EMBED_TIMEOUT", "20"))


def embed_3d(mol: Chem.Mol, max_tries: int = 6) -> Chem.Mol:
    """Embed with ETKDG, optimise, and verify the 3D geometry reproduces the
    input stereo. Retries with different seeds if perception disagrees."""
    target = _cip_labels(mol)
    mh = Chem.AddHs(mol)
    last_err = (
        "no valid 3D geometry exists for this combination of stereo descriptors "
        "(e.g. impossible bridgehead configuration)"
    )
    for attempt in range(max_tries):
        ps = AllChem.ETKDGv3()
        ps.randomSeed = 42 + attempt * 7
        ps.enforceChirality = True
        ps.timeout = EMBED_TIMEOUT_S
        ps.useRandomCoords = attempt >= 2
        cid = AllChem.EmbedMolecule(mh, ps)
        if cid < 0:
            continue
        try:
            if AllChem.MMFFHasAllMoleculeParams(mh):
                AllChem.MMFFOptimizeMolecule(mh, maxIters=500)
            else:
                AllChem.UFFOptimizeMolecule(mh, maxIters=500)
        except Exception:  # noqa: BLE001 - optimisation failure is non-fatal
            pass
        check = Chem.Mol(mh)
        Chem.AssignStereochemistryFrom3D(check, replaceExistingTags=True)
        # AddHs appends hydrogens, so heavy-atom/bond indices match the input.
        # Only stereo specified in the input must be reproduced.
        got = _cip_labels(check)
        if all(got.get(k) == v for k, v in target.items()):
            return mh
        last_err = "3D geometry did not reproduce requested stereochemistry"
    raise ChemError(f"Could not build a 3D model: {last_err}.")


def mol_from_smiles(smiles: str) -> Chem.Mol:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ChemError(f"Invalid SMILES: {smiles}")
    return mol


def canonical_smiles(smiles: str) -> str:
    return Chem.MolToSmiles(mol_from_smiles(smiles), isomericSmiles=True)


def compute_properties(mol: Chem.Mol) -> dict:
    """Common descriptors for the properties panel."""
    from rdkit.Chem import Crippen, Lipinski, QED

    mw = Descriptors.MolWt(mol)
    logp = Crippen.MolLogP(mol)
    hbd = Lipinski.NumHDonors(mol)
    hba = Lipinski.NumHAcceptors(mol)
    return {
        "exact_mass": round(Descriptors.ExactMolWt(mol), 4),
        "logp": round(logp, 2),
        "tpsa": round(rdMolDescriptors.CalcTPSA(mol), 1),
        "hbd": hbd,
        "hba": hba,
        "rotatable_bonds": Lipinski.NumRotatableBonds(mol),
        "heavy_atoms": mol.GetNumHeavyAtoms(),
        "rings": rdMolDescriptors.CalcNumRings(mol),
        "aromatic_rings": rdMolDescriptors.CalcNumAromaticRings(mol),
        "stereocentres": len(Chem.FindMolChiralCenters(mol, includeUnassigned=True, useLegacyImplementation=False)),
        "charge": Chem.GetFormalCharge(mol),
        "qed": round(QED.qed(mol), 2),
        "lipinski_violations": sum([mw > 500, logp > 5, hbd > 5, hba > 10]),
    }


MAX_HEAVY_ATOMS = int(os.environ.get("CHEM_MAX_HEAVY_ATOMS", "150"))


def build_from_smiles(smiles: str, input_text: str = "", source: str = "smiles") -> MoleculeResult:
    # Canonical order first, so every atom index in the result (stereo report,
    # groups, mol block, SVG) refers to the returned SMILES.
    smiles = canonical_smiles(smiles)
    mol = mol_from_smiles(smiles)
    if mol.GetNumHeavyAtoms() > MAX_HEAVY_ATOMS:
        raise ChemError(
            f"Molecule too large: {mol.GetNumHeavyAtoms()} heavy atoms (limit {MAX_HEAVY_ATOMS})."
        )
    stereo = _stereo_report(mol)
    svg = render_svg(mol)
    mol3d = embed_3d(mol)
    return MoleculeResult(
        input_text=input_text or smiles,
        source=source,
        smiles=Chem.MolToSmiles(mol, isomericSmiles=True),
        svg=svg,
        molblock=Chem.MolToMolBlock(mol3d),
        stereo=stereo,
        formula=rdMolDescriptors.CalcMolFormula(mol),
        mw=round(Descriptors.MolWt(mol), 3),
        inchi=Chem.MolToInchi(mol),
        inchikey=Chem.MolToInchiKey(mol),
        properties=compute_properties(mol),
        groups=_groups.find_groups(mol),
    )


def build(text: str) -> MoleculeResult:
    r = resolve_full(text)
    result = build_from_smiles(r.smiles, input_text=text.strip(), source=r.source)
    result.warnings = r.warnings
    result.normalised_input = r.normalised
    return result
