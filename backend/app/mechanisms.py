"""Curved-arrow mechanism library. Each step is a set of species written as
mapped SMILES; arrows refer to atoms (a<map>) or bonds (b<map>-<map>).
RDKit draws the species, and the arrows are laid over the SVG from the
drawing coordinates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from rdkit import Chem
from rdkit.Chem import rdDepictor
from rdkit.Chem.Draw import rdMolDraw2D

from .chem import ChemError


@dataclass
class Step:
    smiles: str
    caption: str
    arrows: list[tuple[str, str]] = field(default_factory=list)  # (from, to)
    half: bool = False  # fishhook arrows (radicals)


@dataclass
class Mechanism:
    id: str
    name: str
    category: str
    summary: str
    steps: list[Step]


LIBRARY: list[Mechanism] = [
    Mechanism("sn2", "SN2 substitution", "Substitution", "Bromomethane and hydroxide: one concerted step with inversion.", [
        Step("[OH-:1].[CH3:2][Br:3]", "The nucleophile attacks the carbon from the side opposite the leaving group while the C-Br bond breaks. One step, no intermediate.", [("a1", "a2"), ("b2-3", "a3")]),
        Step("[CH3:2][OH:1].[Br-:3]", "Methanol and bromide. The carbon is turned inside out (inversion of configuration) when it is a stereocentre."),
    ]),
    Mechanism("sn1", "SN1 substitution", "Substitution", "tert-Butyl bromide and water: ionisation, capture, deprotonation.", [
        Step("[CH3:4][C:2]([CH3:5])([CH3:6])[Br:3]", "Slow step: the C-Br bond breaks on its own. Both electrons go to bromine and a tertiary carbocation forms.", [("b2-3", "a3")]),
        Step("[CH3:4][C+:2]([CH3:5])[CH3:6].[Br-:3].[OH2:1]", "Fast step: water attacks the planar carbocation. Either face is possible, so a stereocentre would be racemised.", [("a1", "a2")]),
        Step("[CH3:4][C:2]([CH3:5])([CH3:6])[O+:1]([H:8])[H:9].[OH2:7]", "A second water molecule removes a proton from the oxonium ion.", [("a7", "a8"), ("b1-8", "a1")]),
        Step("[CH3:4][C:2]([CH3:5])([CH3:6])[OH:1].[OH3+:7].[Br-:3]", "tert-Butanol, hydronium and bromide."),
    ]),
    Mechanism("e2", "E2 elimination", "Elimination", "2-Bromopropane and ethoxide: base removes a proton as the halide leaves.", [
        Step("[CH3:7][CH2:8][O-:1].[H:9][CH2:4][CH:2]([CH3:5])[Br:3]", "The base takes the beta hydrogen, its electrons become the new pi bond, and the C-Br bond breaks, all at once. The H and Br must be anti-periplanar.", [("a1", "a9"), ("b4-9", "b4-2"), ("b2-3", "a3")]),
        Step("[CH3:7][CH2:8][OH:1].[CH2:4]=[CH:2][CH3:5].[Br-:3]", "Propene, ethanol and bromide."),
    ]),
    Mechanism("e1", "E1 elimination", "Elimination", "tert-Butyl bromide heated in a weak base: ionisation, then loss of a proton.", [
        Step("[CH3:4][C:2]([CH3:5])([CH3:6])[Br:3]", "Slow step: the leaving group departs and the tertiary carbocation forms (the same first step as SN1).", [("b2-3", "a3")]),
        Step("[CH3:4][C+:2]([CH3:5])[CH2:6][H:7].[Br-:3].[OH2:8]", "A weak base removes a proton from the carbon next to the cation; the C-H electrons form the pi bond.", [("a8", "a7"), ("b6-7", "b6-2")]),
        Step("[CH3:4][C:2]([CH3:5])=[CH2:6].[OH3+:8].[Br-:3]", "2-Methylpropene. With more than one beta carbon the more substituted alkene forms (Zaitsev)."),
    ]),
    Mechanism("hbr_addition", "HBr addition to an alkene", "Addition", "Propene and HBr: protonation gives the more stable carbocation, then bromide adds.", [
        Step("[CH2:1]=[CH:2][CH3:3].[H:4][Br:5]", "The pi bond takes the proton on the terminal carbon, so the positive charge lands on the secondary carbon (Markovnikov).", [("b1-2", "a4"), ("b4-5", "a5")]),
        Step("[CH3:1][CH+:2][CH3:3].[Br-:5]", "Bromide adds to the carbocation.", [("a5", "a2")]),
        Step("[CH3:1][CH:2]([Br:5])[CH3:3]", "2-Bromopropane."),
    ]),
    Mechanism("hydration", "Acid-catalysed hydration", "Addition", "2-Methylpropene, water and acid: protonation, capture by water, deprotonation.", [
        Step("[CH2:1]=[C:2]([CH3:3])[CH3:4].[H:5][O+:6]([H])[H]", "Hydronium protonates the alkene at the CH2 end: the tertiary carbocation forms.", [("b1-2", "a5"), ("b5-6", "a6")]),
        Step("[CH3:1][C+:2]([CH3:3])[CH3:4].[OH2:7]", "Water attacks the carbocation.", [("a7", "a2")]),
        Step("[CH3:1][C:2]([CH3:3])([CH3:4])[O+:7]([H:8])[H].[OH2:9]", "Another water molecule removes the extra proton; the acid catalyst is regenerated.", [("a9", "a8"), ("b7-8", "a7")]),
        Step("[CH3:1][C:2]([CH3:3])([CH3:4])[OH:7].[OH3+:9]", "tert-Butanol."),
    ]),
    Mechanism("bromination", "Bromination of an alkene", "Addition", "Ethene and Br2 through a cyclic bromonium ion; anti addition.", [
        Step("[CH2:1]=[CH2:2].[Br:3][Br:4]", "The pi bond attacks one bromine; that bromine's lone pair bonds back to the other carbon while Br-Br breaks.", [("b1-2", "a3"), ("a3", "a2"), ("b3-4", "a4")]),
        Step("[CH2:1]1[CH2:2][Br+:3]1.[Br-:4]", "Bromide opens the bromonium ion from the opposite face.", [("a4", "a2"), ("b2-3", "a3")]),
        Step("[Br:3][CH2:1][CH2:2][Br:4]", "1,2-Dibromoethane. On a ring or a stereogenic alkene the two bromines end up anti."),
    ]),
    Mechanism("esterification", "Fischer esterification", "Carbonyl chemistry", "Acetic acid and methanol with an acid catalyst: six reversible steps.", [
        Step("[CH3:1][C:2](=[O:3])[OH:4].[H:5][O+:6]([H])[H]", "The carbonyl oxygen is protonated, which makes the carbon more electrophilic.", [("a3", "a5"), ("b5-6", "a6")]),
        Step("[CH3:1][C:2](=[O+:3][H:5])[OH:4].[OH2:6].[CH3:7][OH:8]", "Methanol attacks the carbonyl carbon; the pi electrons move onto oxygen.", [("a8", "a2"), ("b2-3", "a3")]),
        Step("[CH3:1][C:2]([O:3][H:5])([OH:4])[O+:8]([H:9])[CH3:7]", "Proton transfer: the oxonium proton moves to the OH that will leave.", [("a4", "a9"), ("b8-9", "a8")]),
        Step("[CH3:1][C:2]([O:3][H:5])([O:8][CH3:7])[O+:4]([H])[H]", "Water leaves as the oxygen lone pair reforms the carbonyl.", [("a3", "b2-3"), ("b2-4", "a4")]),
        Step("[CH3:1][C:2](=[O+:3][H:5])[O:8][CH3:7].[OH2:4]", "Water takes the proton off the carbonyl oxygen.", [("a4", "a5"), ("b3-5", "a3")]),
        Step("[CH3:1][C:2](=[O:3])[O:8][CH3:7].[OH3+:4]", "Methyl acetate. Every step is reversible: excess alcohol or removal of water drives the equilibrium."),
    ]),
    Mechanism("saponification", "Ester hydrolysis with hydroxide", "Carbonyl chemistry", "Methyl acetate and hydroxide: addition, elimination, then an irreversible proton transfer.", [
        Step("[CH3:1][C:2](=[O:3])[O:4][CH3:5].[OH-:6]", "Hydroxide adds to the carbonyl carbon.", [("a6", "a2"), ("b2-3", "a3")]),
        Step("[CH3:1][C:2]([O-:3])([OH:6])[O:4][CH3:5]", "The tetrahedral intermediate collapses: the carbonyl reforms and methoxide leaves.", [("a3", "b2-3"), ("b2-4", "a4")]),
        Step("[CH3:1][C:2](=[O:3])[O:6][H:7].[O-:4][CH3:5]", "Methoxide takes the acidic proton of the acid. This step is what makes the whole process irreversible.", [("a4", "a7"), ("b6-7", "a6")]),
        Step("[CH3:1][C:2](=[O:3])[O-:6].[OH:4][CH3:5]", "Acetate and methanol. Acidic workup gives acetic acid."),
    ]),
    Mechanism("cyanohydrin", "Cyanohydrin formation", "Carbonyl chemistry", "Acetone and cyanide: nucleophilic addition to a ketone.", [
        Step("[CH3:1][C:2](=[O:3])[CH3:4].[C-:5]#[N:6]", "Cyanide attacks the carbonyl carbon; the pi electrons move to oxygen.", [("a5", "a2"), ("b2-3", "a3")]),
        Step("[CH3:1][C:2]([O-:3])([CH3:4])[C:5]#[N:6].[H:7][C:8]#[N:9]", "The alkoxide takes a proton from HCN, regenerating cyanide.", [("a3", "a7"), ("b7-8", "a8")]),
        Step("[CH3:1][C:2]([OH:3])([CH3:4])[C:5]#[N:6].[C-:8]#[N:9]", "Acetone cyanohydrin."),
    ]),
    Mechanism("grignard", "Grignard addition", "Carbonyl chemistry", "Methylmagnesium bromide and formaldehyde, then aqueous workup.", [
        Step("[CH3:1][Mg:2][Br:3].[CH2:4]=[O:5]", "The polarised C-Mg bond delivers the methyl carbanion to the carbonyl carbon.", [("b1-2", "a4"), ("b4-5", "a5")]),
        Step("[CH3:1][CH2:4][O-:5].[Mg+:2][Br:3].[H:6][O+:7]([H])[H]", "Workup: the magnesium alkoxide is protonated by aqueous acid.", [("a5", "a6"), ("b6-7", "a7")]),
        Step("[CH3:1][CH2:4][OH:5].[OH2:7]", "Ethanol. Formaldehyde gives a primary alcohol; other aldehydes give secondary, ketones tertiary."),
    ]),
    Mechanism("nabh4", "Reduction with sodium borohydride", "Carbonyl chemistry", "Acetone and NaBH4 in methanol: hydride delivery, then protonation.", [
        Step("[CH3:1][C:2](=[O:3])[CH3:4].[H:5][B-:6]([H])([H])[H]", "A hydride is transferred from boron to the carbonyl carbon.", [("b5-6", "a2"), ("b2-3", "a3")]),
        Step("[CH3:1][CH:2]([O-:3])[CH3:4].[BH3:6].[H:7][O:8][CH3]", "The alkoxide is protonated by the solvent.", [("a3", "a7"), ("b7-8", "a8")]),
        Step("[CH3:1][CH:2]([OH:3])[CH3:4].[O-:8]C", "Propan-2-ol."),
    ]),
    Mechanism("imine", "Imine formation", "Carbonyl chemistry", "Acetone and methylamine with mild acid: addition, then dehydration.", [
        Step("[CH3:1][C:2](=[O:3])[CH3:4].[CH3:5][NH2:6]", "The amine nitrogen attacks the carbonyl carbon.", [("a6", "a2"), ("b2-3", "a3")]),
        Step("[CH3:1][C:2]([O-:3])([CH3:4])[N+:6]([H:7])([H:8])[CH3:5]", "Proton transfer from nitrogen to oxygen gives the carbinolamine.", [("a3", "a7"), ("b6-7", "a6")]),
        Step("[CH3:1][C:2]([O:3][H:7])([CH3:4])[N:6]([H:8])[CH3:5].[H:9][O+:10]([H])[H]", "Acid protonates the OH so it can leave as water.", [("a3", "a9"), ("b9-10", "a10")]),
        Step("[CH3:1][C:2]([O+:3]([H:7])[H:9])([CH3:4])[N:6]([H:8])[CH3:5]", "The nitrogen lone pair pushes water out: an iminium ion forms.", [("a6", "b2-6"), ("b2-3", "a3")]),
        Step("[CH3:1][C:2](=[N+:6]([H:8])[CH3:5])[CH3:4].[OH2:3].[OH2:10]", "Water removes the N-H proton.", [("a10", "a8"), ("b6-8", "a6")]),
        Step("[CH3:1][C:2](=[N:6][CH3:5])[CH3:4].[OH3+:10].[OH2:3]", "The imine (Schiff base). Fastest near pH 5: enough acid to activate the OH, enough free amine to attack."),
    ]),
    Mechanism("aldol", "Aldol addition", "Carbonyl chemistry", "Acetaldehyde with hydroxide: enolate formation, attack, protonation.", [
        Step("[OH-:1].[H:2][CH2:3][CH:4]=[O:5]", "Hydroxide removes an alpha hydrogen; the electrons delocalise onto oxygen to give the enolate.", [("a1", "a2"), ("b2-3", "b3-4"), ("b4-5", "a5")]),
        Step("[CH2:3]=[CH:4][O-:5].[CH3:6][CH:7]=[O:8].[OH2:1]", "The enolate carbon attacks the carbonyl of a second molecule.", [("b3-4", "a7"), ("b7-8", "a8")]),
        Step("[O:5]=[CH:4][CH2:3][CH:7]([O-:8])[CH3:6].[H:9][O:1][H]", "The alkoxide is protonated by water, regenerating hydroxide.", [("a8", "a9"), ("b9-1", "a1")]),
        Step("[O:5]=[CH:4][CH2:3][CH:7]([OH:8])[CH3:6].[OH-:1]", "3-Hydroxybutanal, the aldol. Heating dehydrates it to the conjugated enal."),
    ]),
    Mechanism("eas_bromination", "Bromination of benzene", "Aromatic", "Electrophilic aromatic substitution with Br2 and FeBr3.", [
        Step("[cH:1]1[cH:2][cH:3][cH:4][cH:5][cH:6]1.[Br:7][Br:8].Br[Fe:9](Br)Br", "The Lewis acid polarises Br2. The ring's pi electrons attack the outer bromine; aromaticity is lost temporarily.", [("b1-2", "a7"), ("b7-8", "a8"), ("a8", "a9")]),
        Step("[Br:7][C:1]1([H:10])[CH:2]=[CH:3][CH:4]=[CH:5][CH+:6]1.[Fe-:9](Br)(Br)(Br)[Br:8]", "The sigma complex (arenium ion). FeBr4- removes the proton and the aromatic ring is restored.", [("a8", "a10"), ("b1-10", "b1-6")]),
        Step("[Br:7][c:1]1[cH:2][cH:3][cH:4][cH:5][cH:6]1.[H:10][Br:8].Br[Fe:9](Br)Br", "Bromobenzene, HBr and the regenerated catalyst."),
    ]),
    Mechanism("nitration", "Nitration of benzene", "Aromatic", "Nitric and sulfuric acid make the nitronium ion, which the ring attacks.", [
        Step("[H:1][O:2][N+:3](=[O:4])[O-:5].[H:6][O:7][S:8](=O)(=O)[OH]", "Sulfuric acid protonates nitric acid.", [("a2", "a6"), ("b6-7", "a7")]),
        Step("[H:1][O+:2]([H:6])[N+:3](=[O:4])[O-:5].[O-:7][S:8](=O)(=O)[OH]", "Water leaves and the nitronium ion NO2+ forms.", [("b2-3", "a2"), ("a5", "b3-5")]),
        Step("[O:4]=[N+:3]=[O:5].[OH2:2].[cH:9]1[cH:10][cH:11][cH:12][cH:13][cH:14]1", "The ring attacks the nitrogen of NO2+.", [("b9-10", "a3"), ("b3-4", "a4")]),
        Step("[O-:4][N+:3](=[O:5])[C:9]1([H:15])[CH:10]=[CH:11][CH:12]=[CH:13][CH+:14]1.[OH2:2]", "The sigma complex loses a proton to water and aromaticity returns.", [("a2", "a15"), ("b9-15", "b9-14")]),
        Step("[O-:4][N+:3](=[O:5])[c:9]1[cH:10][cH:11][cH:12][cH:13][cH:14]1.[OH3+:2]", "Nitrobenzene."),
    ]),
    Mechanism("diels_alder", "Diels-Alder reaction", "Pericyclic", "Buta-1,3-diene and ethene: one concerted step, three arrows.", [
        Step("[CH2:1]=[CH:2][CH:3]=[CH2:4].[CH2:5]=[CH2:6]", "Six electrons move at once through a cyclic transition state: two new sigma bonds and one new pi bond. No intermediate.", [("b1-2", "b2-3"), ("b3-4", "b4-5"), ("b5-6", "b6-1")]),
        Step("[CH2:1]1[CH:2]=[CH:3][CH2:4][CH2:5][CH2:6]1", "Cyclohexene. The diene must be s-cis; substituents keep their relative configuration (suprafacial on both partners)."),
    ]),
    Mechanism("williamson", "Williamson ether synthesis", "Substitution", "Methoxide and iodomethane: an SN2 reaction on the halide.", [
        Step("[CH3:1][O-:2].[CH3:3][I:4]", "The alkoxide is the nucleophile; iodide leaves in one step.", [("a2", "a3"), ("b3-4", "a4")]),
        Step("[CH3:1][O:2][CH3:3].[I-:4]", "Dimethyl ether. Use a primary halide: secondary and tertiary halides eliminate instead."),
    ]),
    Mechanism("acid_chloride_amide", "Amide from an acid chloride", "Carbonyl chemistry", "Acetyl chloride and ammonia: addition, elimination of chloride, deprotonation.", [
        Step("[CH3:1][C:2](=[O:3])[Cl:4].[NH3:5]", "Ammonia attacks the carbonyl carbon.", [("a5", "a2"), ("b2-3", "a3")]),
        Step("[CH3:1][C:2]([O-:3])([Cl:4])[NH3+:5]", "The carbonyl reforms and chloride, the best leaving group, departs.", [("a3", "b2-3"), ("b2-4", "a4")]),
        Step("[CH3:1][C:2](=[O:3])[N+:5]([H:6])([H])[H].[Cl-:4]", "Chloride (or a second ammonia) removes the N-H proton.", [("a4", "a6"), ("b5-6", "a5")]),
        Step("[CH3:1][C:2](=[O:3])[NH2:5].[H:6][Cl:4]", "Acetamide and HCl. In practice two equivalents of amine are used, one to trap the HCl."),
    ]),
    Mechanism("radical_chlorination", "Radical chlorination of methane", "Radical", "Initiation, two propagation steps, termination. Fishhook arrows move one electron each.", [
        Step("[Cl:1][Cl:2]", "Initiation: light breaks Cl2 homolytically into two chlorine radicals.", [("b1-2", "a1"), ("b1-2", "a2")], half=True),
        Step("[Cl:1].[H:3][CH3:4]", "Propagation 1: a chlorine radical abstracts a hydrogen; a methyl radical is left.", [("a1", "a3"), ("b3-4", "a3"), ("b3-4", "a4")], half=True),
        Step("[H:3][Cl:1].[CH3:4].[Cl:5][Cl:6]", "Propagation 2: the methyl radical takes a chlorine from Cl2 and a new chlorine radical carries the chain.", [("a4", "a5"), ("b5-6", "a5"), ("b5-6", "a6")], half=True),
        Step("[CH3:4][Cl:5].[Cl:6]", "Chloromethane and a chlorine radical. Termination: any two radicals combine (Cl-Cl, CH3-Cl, CH3-CH3)."),
    ]),
]

_BY_ID = {m.id: m for m in LIBRARY}
_PARSE = Chem.SmilesParserParams()
_PARSE.removeHs = False


def list_mechanisms() -> list[dict]:
    return [{"id": m.id, "name": m.name, "category": m.category, "summary": m.summary, "steps": len(m.steps)} for m in LIBRARY]


def _endpoint(ref: str, coords: dict[int, tuple[float, float]]) -> tuple[float, float]:
    if ref.startswith("a"):
        return coords[int(ref[1:])]
    a, b = ref[1:].split("-")
    (x1, y1), (x2, y2) = coords[int(a)], coords[int(b)]
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def _arrow_svg(p: tuple[float, float], q: tuple[float, float], half: bool, colour: str = "#dc2626", bulge: float | None = None, trim: float | None = None) -> str:
    (x1, y1), (x2, y2) = p, q
    dx, dy = x2 - x1, y2 - y1
    dist = math.hypot(dx, dy) or 1.0
    # Shorten both ends so the arrow does not sit on the atom labels.
    ux, uy = dx / dist, dy / dist
    if trim is None:
        trim = min(9.0, dist * 0.15)
    x1, y1 = x1 + ux * trim, y1 + uy * trim
    x2, y2 = x2 - ux * trim, y2 - uy * trim
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    if bulge is None:
        bulge = max(26.0, min(45.0, dist * 0.4))
    cx, cy = mx - uy * bulge, my + ux * bulge
    # Tangent at the end of the quadratic curve points from the control point to the end.
    tx, ty = x2 - cx, y2 - cy
    tl = math.hypot(tx, ty) or 1.0
    tx, ty = tx / tl, ty / tl
    nx, ny = -ty, tx
    size = 8.0
    base_x, base_y = x2 - tx * size, y2 - ty * size
    if half:
        head = f"<polygon points='{x2:.1f},{y2:.1f} {base_x + nx * size * 0.6:.1f},{base_y + ny * size * 0.6:.1f} {base_x:.1f},{base_y:.1f}' fill='{colour}'/>"
    else:
        head = f"<polygon points='{x2:.1f},{y2:.1f} {base_x + nx * size * 0.55:.1f},{base_y + ny * size * 0.55:.1f} {base_x - nx * size * 0.55:.1f},{base_y - ny * size * 0.55:.1f}' fill='{colour}'/>"
    path = f"<path d='M{x1:.1f},{y1:.1f} Q{cx:.1f},{cy:.1f} {x2:.1f},{y2:.1f}' fill='none' stroke='{colour}' stroke-width='2.2' stroke-linecap='round'/>"
    return path + head


def _bond_atoms(ref: str) -> tuple[int, int] | None:
    if not ref.startswith("b"):
        return None
    a, b = ref[1:].split("-")
    return int(a), int(b)


def _arrow_for(src: str, dst: str, coords: dict[int, tuple[float, float]], half: bool) -> str:
    """Bond-to-its-own-atom arrows (a bond breaking onto one end, or a lone pair
    forming a bond to its own neighbour) are drawn as a loop beside the bond so
    they stay visible; everything else is a plain curve between the two points."""
    sb, db = _bond_atoms(src), _bond_atoms(dst)
    atom = None
    bond = None
    if sb and dst.startswith("a") and int(dst[1:]) in sb:
        bond, atom = sb, int(dst[1:])
        start_is_bond = True
    elif db and src.startswith("a") and int(src[1:]) in db:
        bond, atom = db, int(src[1:])
        start_is_bond = False
    if bond is None:
        return _arrow_svg(_endpoint(src, coords), _endpoint(dst, coords), half)
    (x1, y1), (x2, y2) = coords[bond[0]], coords[bond[1]]
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    ax, ay = coords[atom]
    dx, dy = x2 - x1, y2 - y1
    dist = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / dist, dx / dist
    p_bond = (mx + nx * 5, my + ny * 5)
    p_atom = (ax + nx * 18 - (ax - mx) / dist * 4, ay + ny * 18 - (ay - my) / dist * 4)
    if start_is_bond:
        return _arrow_svg(p_bond, p_atom, half, bulge=24.0, trim=0.0)
    return _arrow_svg(p_atom, p_bond, half, bulge=24.0, trim=0.0)


def render_step(step: Step, width: int = 620, height: int = 300) -> str:
    mol = Chem.MolFromSmiles(step.smiles, _PARSE)
    if mol is None:
        raise ChemError(f"Bad mechanism step: {step.smiles}")
    maps = {a.GetAtomMapNum(): a.GetIdx() for a in mol.GetAtoms() if a.GetAtomMapNum()}
    for a in mol.GetAtoms():
        a.SetAtomMapNum(0)
    rdDepictor.Compute2DCoords(mol)
    d = rdMolDraw2D.MolDraw2DSVG(width, height)
    opts = d.drawOptions()
    opts.clearBackground = False
    opts.bondLineWidth = 2
    opts.padding = 0.12
    opts.fixedBondLength = 60
    opts.fixedFontSize = 18
    d.DrawMolecule(mol)
    d.FinishDrawing()
    svg = d.GetDrawingText()
    coords = {}
    for m, idx in maps.items():
        p = d.GetDrawCoords(idx)
        coords[m] = (p.x, p.y)
    overlay = []
    for src, dst in step.arrows:
        try:
            overlay.append(_arrow_for(src, dst, coords, step.half))
        except KeyError as e:
            raise ChemError(f"Arrow refers to a missing atom map {e} in {step.smiles}")
    return svg.replace("</svg>", "".join(overlay) + "</svg>")


def get_mechanism(mech_id: str) -> dict:
    m = _BY_ID.get(mech_id)
    if m is None:
        raise ChemError("Unknown mechanism.")
    return {
        "id": m.id,
        "name": m.name,
        "category": m.category,
        "summary": m.summary,
        "steps": [{"svg": render_step(s), "caption": s.caption, "arrows": len(s.arrows), "half": s.half, "smiles": s.smiles} for s in m.steps],
    }
