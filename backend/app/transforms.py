"""Reaction templates for three teaching tools:

* predict_products: apply textbook reactions to the current molecule;
* retrosynthesis: one disconnection back from the current molecule;
* classify: name the reaction in a reactant>>product pair.

Templates are RDKit reaction SMARTS. Regiochemistry (Markovnikov, Zaitsev,
ortho/para) is decided in code after the template has produced every
regioisomer, so each rule states what it prefers and why.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rdkit import Chem
from rdkit.Chem import AllChem, rdDepictor
from rdkit.Chem.Draw import rdMolDraw2D

from .chem import ChemError, mol_from_smiles


@dataclass
class Template:
    name: str
    smarts: str
    reagents: str
    category: str
    regio: str = ""  # markovnikov | anti_markovnikov | zaitsev | hofmann | aromatic
    note: str = ""
    rxn: object = field(default=None, repr=False)

    def __post_init__(self):
        self.rxn = AllChem.ReactionFromSmarts(self.smarts)
        self.rxn.Initialize()


FORWARD: list[Template] = [
    # Alkenes
    Template("Hydrogenation", "[C:1]=[C:2]>>[C:1][C:2]", "H2, Pd/C", "addition", note="Syn addition of H2 across the double bond."),
    Template("Hydrohalogenation (Markovnikov)", "[C:1]=[C:2]>>[C:1][C:2]Br", "HBr", "addition", "markovnikov", "Br ends up on the more substituted carbon: the more stable carbocation forms first."),
    Template("Hydrobromination with peroxides (anti-Markovnikov)", "[C:1]=[C:2]>>[C:1][C:2]Br", "HBr, ROOR", "addition", "anti_markovnikov", "Radical chain: the bromine radical adds to the less substituted carbon."),
    Template("Acid-catalysed hydration (Markovnikov)", "[C:1]=[C:2]>>[C:1][C:2]O", "H2O, H2SO4", "addition", "markovnikov", "OH on the more substituted carbon, via the more stable carbocation."),
    Template("Hydroboration-oxidation (anti-Markovnikov)", "[C:1]=[C:2]>>[C:1][C:2]O", "1. BH3·THF  2. H2O2, NaOH", "addition", "anti_markovnikov", "Syn addition; OH on the less substituted carbon."),
    Template("Bromination", "[C:1]=[C:2]>>Br[C:1][C:2]Br", "Br2, CH2Cl2", "addition", note="Anti addition through a bromonium ion."),
    Template("Epoxidation", "[C:1]=[C:2]>>[C:1]1[C:2]O1", "mCPBA", "addition", note="Syn addition of one oxygen."),
    Template("Syn dihydroxylation", "[C:1]=[C:2]>>O[C:1][C:2]O", "OsO4, then NaHSO3 (or cold dilute KMnO4)", "addition", note="Both OH groups add to the same face."),
    Template("Ozonolysis", "[C:1]=[C:2]>>[C:1]=O.[C:2]=O", "1. O3  2. Me2S", "oxidation", note="The double bond is cut; each carbon becomes a carbonyl."),
    Template("Diels-Alder with ethene", "[C:1]=[C:2][C:3]=[C:4]>>[C:1]1[C:2]=[C:3][C:4]CC1", "ethene, heat", "cycloaddition", note="The conjugated diene (s-cis) and a dienophile form a cyclohexene in one step."),
    # Alkynes
    Template("Hydrogenation of an alkyne", "[C:1]#[C:2]>>[C:1][C:2]", "H2 (excess), Pd/C", "addition"),
    Template("Partial hydrogenation to the cis alkene", "[C:1]#[C:2]>>[C:1]=[C:2]", "H2, Lindlar catalyst", "addition", note="Syn addition of one H2 gives the cis (Z) alkene."),
    Template("Alkyne hydration (Markovnikov)", "[C:1]#[CH:2]>>[C:1](=O)[CH3:2]", "H2O, H2SO4, HgSO4", "addition", note="The enol tautomerises to the methyl ketone."),
    Template("Alkyne hydroboration-oxidation", "[C:1]#[CH:2]>>[CH2:1][CH:2]=O", "1. Sia2BH  2. H2O2, NaOH", "addition", note="Anti-Markovnikov: the terminal alkyne gives an aldehyde."),
    # Alcohols
    Template("Oxidation of a primary alcohol to an aldehyde", "[CH2;$(C[#6]):1][OH:2]>>[CH1:1]=[O:2]", "PCC, CH2Cl2", "oxidation", note="PCC stops at the aldehyde because no water is present."),
    Template("Oxidation of a primary alcohol to a carboxylic acid", "[CH2;$(C[#6]):1][OH:2]>>[C:1](=[O:2])O", "KMnO4 or CrO3/H2SO4 (Jones)", "oxidation"),
    Template("Oxidation of a secondary alcohol to a ketone", "[CH1;$(C([#6])[#6]):1][OH:2]>>[C:1]=[O:2]", "CrO3/H2SO4 (Jones) or PCC", "oxidation"),
    Template("Dehydration of an alcohol", "[CX4;!H0:1][CX4:2][OH]>>[C:1]=[C:2]", "H2SO4, heat", "elimination", "zaitsev", "E1 for secondary and tertiary alcohols; the more substituted alkene dominates."),
    Template("Alcohol to alkyl bromide", "[CX4:1][OH]>>[C:1]Br", "HBr (or PBr3)", "substitution", note="PBr3 works with inversion for primary and secondary alcohols."),
    Template("Alcohol to alkyl chloride", "[CX4:1][OH]>>[C:1]Cl", "SOCl2, pyridine", "substitution"),
    Template("Williamson ether synthesis (methyl ether)", "[CX4:1][OH:2]>>[C:1][O:2]C", "1. NaH  2. CH3I", "substitution", note="The alkoxide displaces iodide by SN2."),
    # Carbonyls
    Template("Reduction of an aldehyde or ketone", "[CX3;!$(C(=O)[O,N,S,F,Cl,Br,I]):1]=[O:2]>>[C:1][O:2]", "NaBH4, MeOH", "reduction", note="Hydride adds to the carbonyl carbon."),
    Template("Wolff-Kishner reduction", "[CX3;$(C([#6])[#6,#1]);!$(C(=O)[O,N,S,F,Cl,Br,I]):1]=O>>[C:1]", "H2NNH2, KOH, heat", "reduction", note="C=O becomes CH2 (Clemmensen with Zn(Hg)/HCl does the same)."),
    Template("Cyanohydrin formation", "[CX3;!$(C(=O)[O,N,S,F,Cl,Br,I]):1]=[O:2]>>[C:1]([O:2])C#N", "HCN (NaCN, HCl)", "addition"),
    Template("Imine formation with methylamine", "[CX3;!$(C(=O)[O,N,S,F,Cl,Br,I]):1]=[O:2]>>[C:1]=NC", "CH3NH2, mild acid", "condensation", note="Loses water; other primary amines work the same way."),
    Template("Grignard addition of methylmagnesium bromide", "[CX3;!$(C(=O)[O,N,S,F,Cl,Br,I]):1]=[O:2]>>[C:1]([O:2])C", "1. CH3MgBr, ether  2. H3O+", "addition", note="Any Grignard reagent adds this way; the alcohol gains one carbon here."),
    Template("Oxidation of an aldehyde to a carboxylic acid", "[CH1:1](=[O:2])[#6]>>[C:1](=[O:2])O", "Ag(NH3)2+ (Tollens) or Jones", "oxidation"),
    # Acids and derivatives
    Template("Fischer esterification with methanol", "[C:1](=[O:2])[OH]>>[C:1](=[O:2])OC", "CH3OH, H2SO4 (cat.)", "condensation", note="Reversible; excess alcohol drives it forward."),
    Template("Acid chloride formation", "[C:1](=[O:2])[OH]>>[C:1](=[O:2])Cl", "SOCl2", "substitution"),
    Template("Amide formation", "[C:1](=[O:2])[OH]>>[C:1](=[O:2])N", "1. SOCl2  2. NH3", "condensation", note="Via the acid chloride; direct heating with an amine also works."),
    Template("Reduction of a carboxylic acid", "[C:1](=[O:2])[OH]>>[CH2:1][O:2]", "1. LiAlH4  2. H3O+", "reduction"),
    Template("Ester hydrolysis", "[C:1](=[O:2])[O:3][#6:4]>>[C:1](=[O:2])O.[O:3][#6:4]", "NaOH, H2O, heat (saponification) or H3O+", "hydrolysis"),
    Template("Ester reduction", "[C:1](=[O:2])[O:3][#6:4]>>[CH2:1][O:2].[O:3][#6:4]", "1. LiAlH4  2. H3O+", "reduction", note="Both the acyl and the alkoxy part end up as alcohols."),
    Template("Amide hydrolysis", "[C:1](=[O:2])[NX3:3]>>[C:1](=[O:2])O.[N:3]", "H3O+, heat", "hydrolysis"),
    Template("Amide reduction", "[C:1](=[O:2])[NX3:3]>>[CH2:1][N:3]", "1. LiAlH4  2. H2O", "reduction", note="The carbonyl becomes CH2: an amine forms."),
    Template("Nitrile hydrolysis", "[C:1]#[N]>>[C:1](=O)O", "H3O+, heat", "hydrolysis"),
    Template("Nitrile reduction", "[C:1]#[N:2]>>[CH2:1][NH2:2]", "1. LiAlH4  2. H2O", "reduction"),
    # Alkyl halides
    Template("Substitution by hydroxide", "[CX4:1][Cl,Br,I]>>[C:1]O", "NaOH, H2O", "substitution", note="SN2 for methyl and primary halides; tertiary halides go by SN1 with water instead."),
    Template("Substitution by cyanide", "[CX4;H2,H3:1][Cl,Br,I]>>[C:1]C#N", "NaCN, DMSO", "substitution", note="SN2; one carbon is added."),
    Template("Substitution by ammonia", "[CX4;H2,H3:1][Cl,Br,I]>>[C:1]N", "NH3 (excess)", "substitution", note="SN2; excess ammonia limits over-alkylation."),
    Template("Dehydrohalogenation (Zaitsev)", "[CX4;!H0:1][CX4:2][Cl,Br,I]>>[C:1]=[C:2]", "NaOEt, EtOH, heat", "elimination", "zaitsev", "E2 with a small strong base gives the more substituted alkene."),
    Template("Dehydrohalogenation (Hofmann)", "[CX4;!H0:1][CX4:2][Cl,Br,I]>>[C:1]=[C:2]", "KOtBu, tBuOH", "elimination", "hofmann", "A bulky base removes the most accessible hydrogen: the less substituted alkene."),
    # Aromatic
    Template("Nitration", "[cH:1]>>[c:1][N+](=O)[O-]", "HNO3, H2SO4", "aromatic substitution", "aromatic"),
    Template("Bromination of the ring", "[cH:1]>>[c:1]Br", "Br2, FeBr3", "aromatic substitution", "aromatic"),
    Template("Friedel-Crafts acylation", "[cH:1]>>[c:1]C(C)=O", "CH3COCl, AlCl3", "aromatic substitution", "aromatic", "Fails on strongly deactivated rings (nitro) and on anilines."),
    Template("Friedel-Crafts alkylation", "[cH:1]>>[c:1]C", "CH3Cl, AlCl3", "aromatic substitution", "aromatic", "Prone to polyalkylation and to rearrangement of the alkyl group."),
    Template("Sulfonation", "[cH:1]>>[c:1]S(=O)(=O)O", "fuming H2SO4", "aromatic substitution", "aromatic", "Reversible: dilute acid and heat remove the SO3H group."),
    Template("Reduction of a nitro group", "[c:1][N+](=O)[O-]>>[c:1]N", "Sn, HCl (or H2, Pd/C)", "reduction"),
]

RETRO: list[Template] = [
    Template("Hydration of an alkene", "[CX4:1]([OH])[CX4;!H0:2]>>[C:1]=[C:2]", "H2O, H2SO4 (Markovnikov) or BH3 then H2O2/NaOH (anti-Markovnikov)", "alcohol"),
    Template("Reduction of a carbonyl", "[CX4;!H0;!$(C(O)[O,N]):1][OH:2]>>[C:1]=[O:2]", "NaBH4 or LiAlH4", "alcohol"),
    Template("Substitution of an alkyl halide", "[CX4:1][OH]>>[C:1]Br", "NaOH (SN2) or H2O (SN1)", "alcohol"),
    Template("Grignard addition to a carbonyl", "[CX4;!$(C(O)[O,N]):1]([OH:2])[#6:3]>>[C:1]=[O:2].[#6:3][Mg]Br", "R-MgBr, then H3O+", "alcohol", note="Disconnect one carbon-carbon bond next to the carbinol carbon."),
    Template("Dehydration of an alcohol", "[C:1]=[C:2]>>[C:1](O)[C:2]", "H2SO4, heat", "alkene"),
    Template("Elimination of an alkyl halide", "[C:1]=[C:2]>>[C:1](Br)[C:2]", "NaOEt, heat (E2)", "alkene"),
    Template("Partial hydrogenation of an alkyne", "[C;!H0:1]=[C;!H0:2]>>[C:1]#[C:2]", "H2, Lindlar (cis) or Na/NH3 (trans)", "alkene"),
    Template("Wittig reaction", "[C:1]=[C;!$(C=[C]=*):2]>>[C:1]=O.[C:2]Br", "Ph3P=CR2 from the halide, with the carbonyl", "alkene", note="Either carbon of the alkene can come from the carbonyl."),
    Template("Oxidation of a secondary alcohol", "[#6][C:1](=[O:2])[#6]>>[#6][C:1]([O:2])[#6]", "Jones or PCC", "ketone"),
    Template("Hydration of an alkyne", "[#6:1][C:2](=O)[CH3:3]>>[#6:1][C:2]#[CH:3]", "H2O, H2SO4, HgSO4", "ketone"),
    Template("Friedel-Crafts acylation", "[c:1][C:2](=[O:3])[#6:4]>>[cH:1].Cl[C:2](=[O:3])[#6:4]", "RCOCl, AlCl3", "ketone"),
    Template("Oxidation of a primary alcohol", "[CH1:1](=[O:2])[#6]>>[CH2:1][O:2]", "PCC", "aldehyde"),
    Template("Ozonolysis of an alkene", "[CH1:1](=O)[#6]>>[CH1:1]=C", "O3, then Me2S", "aldehyde"),
    Template("Oxidation of a primary alcohol", "[C:1](=O)[OH:2]>>[CH2:1][O:2]", "KMnO4 or Jones", "carboxylic acid"),
    Template("Hydrolysis of a nitrile", "[C:1](=O)[OH]>>[C:1]#N", "H3O+, heat", "carboxylic acid"),
    Template("Grignard with carbon dioxide", "[C:1](=O)[OH]>>[C:1]Br", "1. Mg, ether  2. CO2  3. H3O+", "carboxylic acid", note="The halide loses one carbon: CO2 supplies the carboxyl carbon."),
    Template("Esterification", "[C:1](=[O:2])[O:3][#6:4]>>[C:1](=[O:2])O.[O:3][#6:4]", "acid + alcohol, H2SO4 (Fischer)", "ester"),
    Template("Amide from an acid chloride", "[C:1](=[O:2])[NX3:3]>>[C:1](=[O:2])Cl.[N:3]", "RCOCl + amine", "amide"),
    Template("Williamson ether synthesis", "[CX4:1][O;!$(OC=O):2][#6:3]>>[C:1]Br.[O:2][#6:3]", "alkoxide + alkyl halide (SN2)", "ether", note="Put the halide on the less hindered carbon."),
    Template("Halogenation of an alcohol", "[CX4:1][Cl,Br]>>[C:1]O", "HBr, PBr3 or SOCl2", "alkyl halide"),
    Template("Hydrohalogenation of an alkene", "[CX4:1]([Br,Cl])[CX4;!H0:2]>>[C:1]=[C:2]", "HBr (Markovnikov) or HBr/ROOR (anti-Markovnikov)", "alkyl halide"),
    Template("Radical halogenation of an alkane", "[CX4;$(C([#6])):1][Br]>>[C:1]", "Br2, light", "alkyl halide", note="Bromine is selective for the most substituted C-H."),
    Template("Cyanide substitution", "[CX4:1]C#N>>[C:1]Br", "NaCN", "nitrile"),
    Template("Reduction of a nitrile", "[CX4:1][NH2:2]>>[C:1]#[N:2]", "LiAlH4", "amine", note="Removes the CH2 next to nitrogen: the nitrile carbon becomes it."),
    Template("Reduction of an amide", "[CX4;H2:1][NX3:2]>>[C:1](=O)[N:2]", "LiAlH4", "amine"),
    Template("Reductive amination", "[CX4;!H0:1][NX3;!$(NC=O):2]>>[C:1]=O.[N:2]", "carbonyl + amine, NaBH3CN", "amine"),
    Template("Reduction of a nitro group", "[c:1][NH2]>>[c:1][N+](=O)[O-]", "Sn, HCl", "aniline"),
    Template("Hydrogenation of an alkene", "[CX4;!H0;!$(C[O,N,S,F,Cl,Br,I]):1][CX4;!H0;!$(C[O,N,S,F,Cl,Br,I]):2]>>[C:1]=[C:2]", "H2, Pd/C", "alkane", note="Any C-C single bond with hydrogens on both carbons could come from an alkene."),
    Template("Epoxidation of an alkene", "[C:1]1[C:2]O1>>[C:1]=[C:2]", "mCPBA", "epoxide"),
    Template("Syn dihydroxylation", "[CX4:1]([OH])[CX4:2][OH]>>[C:1]=[C:2]", "OsO4 (syn) or epoxide then H3O+ (anti)", "diol"),
    Template("Diels-Alder", "[C:1]1[C:2]=[C:3][C:4][C:5][C:6]1>>[C:1]=[C:2][C:3]=[C:4].[C:5]=[C:6]", "diene + dienophile, heat", "cyclohexene"),
    Template("Nitration of the ring", "[c:1][N+](=O)[O-]>>[cH:1]", "HNO3, H2SO4", "nitroarene"),
    Template("Bromination of the ring", "[c:1]Br>>[cH:1]", "Br2, FeBr3", "aryl halide"),
]


def _svg(mol: Chem.Mol, width: int = 220, height: int = 150) -> str:
    m = Chem.Mol(mol)
    rdDepictor.Compute2DCoords(m)
    d = rdMolDraw2D.MolDraw2DSVG(width, height)
    d.drawOptions().clearBackground = False
    d.drawOptions().bondLineWidth = 1.6
    d.DrawMolecule(m)
    d.FinishDrawing()
    return d.GetDrawingText()


def _clean(products) -> list[str] | None:
    """Sanitise a product tuple; None if any part is not a valid molecule."""
    out = []
    for p in products:
        try:
            p.UpdatePropertyCache(strict=False)
            Chem.SanitizeMol(p)
            smi = Chem.MolToSmiles(p)
            if Chem.MolFromSmiles(smi) is None:
                return None
            out.append(smi)
        except Exception:  # noqa: BLE001
            return None
    return out


def _run(t: Template, mol: Chem.Mol) -> list[tuple[list[str], tuple[int, ...]]]:
    """Every distinct product set, with the reactant atoms it came from."""
    results = []
    seen: set[tuple[str, ...]] = set()
    for prods in t.rxn.RunReactants((mol,)):
        smis = _clean(prods)
        if smis is None:
            continue
        key = tuple(sorted(smis))
        if key in seen:
            continue
        seen.add(key)
        # Atoms the template matched (unmatched reactant atoms are copied over too, but carry no old_mapno).
        used = tuple(sorted({int(a.GetProp("react_atom_idx")) for p in prods for a in p.GetAtoms() if a.HasProp("old_mapno") and a.HasProp("react_atom_idx")}))
        results.append((smis, used))
    return results


# --- regiochemistry filters ------------------------------------------------

def _added_atom_partner(reactant: Chem.Mol, product: Chem.Mol) -> int | None:
    """Reactant index of the carbon that received the new group (the mapped atom bonded to an unmapped one)."""
    for a in product.GetAtoms():
        if a.HasProp("react_atom_idx"):
            continue
        for nb in a.GetNeighbors():
            if nb.HasProp("react_atom_idx"):
                return int(nb.GetProp("react_atom_idx"))
    return None


def _markovnikov(t: Template, mol: Chem.Mol) -> list[dict]:
    """Rank regioisomers by the H count of the carbon that takes the new group."""
    out = []
    seen = set()
    for prods in t.rxn.RunReactants((mol,)):
        smis = _clean(prods)
        if smis is None or tuple(smis) in seen:
            continue
        seen.add(tuple(smis))
        carbon = _added_atom_partner(mol, prods[0])
        if carbon is None:
            continue
        hs = mol.GetAtomWithIdx(carbon).GetTotalNumHs()
        out.append({"smiles": smis, "hs": hs, "atoms": [carbon]})
    if not out:
        return []
    key = min if t.regio == "markovnikov" else max
    target = key(o["hs"] for o in out)
    chosen = [o for o in out if o["hs"] == target]
    tie = len(chosen) > 1 and len(out) > 1
    return [{"smiles": o["smiles"], "atoms": o["atoms"], "tie": tie} for o in chosen]


def _alkene_substitution(smiles: str) -> int:
    m = Chem.MolFromSmiles(smiles)
    best = 0
    for b in m.GetBonds():
        if b.GetBondType() == Chem.BondType.DOUBLE and b.GetBeginAtom().GetSymbol() == "C" and b.GetEndAtom().GetSymbol() == "C":
            subs = sum(1 for a in (b.GetBeginAtom(), b.GetEndAtom()) for n in a.GetNeighbors() if n.GetAtomicNum() > 1) - 2
            best = max(best, subs)
    return best


def _zaitsev(t: Template, mol: Chem.Mol) -> list[dict]:
    runs = _run(t, mol)
    if not runs:
        return []
    scored = [(max(_alkene_substitution(s) for s in smis), smis, used) for smis, used in runs]
    target = (max if t.regio == "zaitsev" else min)(s[0] for s in scored)
    chosen = [s for s in scored if s[0] == target]
    return [{"smiles": smis, "atoms": list(used), "tie": len(chosen) > 1 and len(runs) > 1} for _, smis, used in chosen]


_OP_DIRECTORS = Chem.MolFromSmarts("[$([OX2]),$([NX3;!$(N=O);!$([N+])]),$([CX4]),$([F,Cl,Br,I]),$(c)]")
_META_DIRECTORS = Chem.MolFromSmarts("[$([CX3]=O),$([CX2]#N),$([N+](=O)[O-]),$([SX4](=O)=O),$([CX4](F)(F)F)]")


def _ring_position(mol: Chem.Mol, ring: tuple[int, ...], a: int, b: int) -> str:
    order = list(ring)
    i, j = order.index(a), order.index(b)
    d = min((i - j) % len(order), (j - i) % len(order))
    return {1: "ortho", 2: "meta", 3: "para"}.get(d, "")


def _aromatic(t: Template, mol: Chem.Mol) -> list[dict]:
    runs = _run(t, mol)
    if not runs:
        return []
    # Find substituents on benzene rings and their directing effect.
    ring_info = mol.GetRingInfo()
    rings = [r for r in ring_info.AtomRings() if len(r) == 6 and all(mol.GetAtomWithIdx(i).GetIsAromatic() for i in r)]
    directors = []  # (ring, ring atom, type)
    for r in rings:
        for i in r:
            for nb in mol.GetAtomWithIdx(i).GetNeighbors():
                if nb.GetIdx() in r:
                    continue
                kind = None
                if mol.HasSubstructMatch(_META_DIRECTORS) and any(nb.GetIdx() == m[0] for m in mol.GetSubstructMatches(_META_DIRECTORS)):
                    kind = "meta"
                elif any(nb.GetIdx() == m[0] for m in mol.GetSubstructMatches(_OP_DIRECTORS)):
                    kind = "op"
                if kind:
                    directors.append((r, i, kind))
    out = []
    for smis, used in runs:
        site = used[0] if used else None
        positions = []
        for r, at, kind in directors:
            if site in r:
                positions.append((kind, _ring_position(mol, r, site, at)))
        ok = True
        why = []
        for kind, posn in positions:
            if kind == "op" and posn == "meta":
                ok = False
            if kind == "meta" and posn != "meta":
                ok = False
            why.append(f"{posn} to {'an ortho/para' if kind == 'op' else 'a meta'} director")
        if ok:
            out.append({"smiles": smis, "atoms": [site] if site is not None else [], "why": ", ".join(why), "tie": False})
    if not out:  # conflicting directors: show everything
        out = [{"smiles": smis, "atoms": list(used), "why": "directors disagree", "tie": True} for smis, used in runs]
    return out


def predict_products(smiles: str) -> dict:
    mol = mol_from_smiles(smiles)
    if mol.GetNumHeavyAtoms() > 60:
        raise ChemError("Product prediction is limited to 60 heavy atoms.")
    reactions = []
    for t in FORWARD:
        if t.regio in ("markovnikov", "anti_markovnikov"):
            outs = _markovnikov(t, mol)
        elif t.regio in ("zaitsev", "hofmann"):
            outs = _zaitsev(t, mol)
        elif t.regio == "aromatic":
            outs = _aromatic(t, mol)
        else:
            outs = [{"smiles": smis, "atoms": list(used), "tie": False} for smis, used in _run(t, mol)]
        if not outs:
            continue
        products = []
        seen = set()
        for o in outs[:6]:
            key = tuple(sorted(o["smiles"]))
            if key in seen:
                continue
            seen.add(key)
            products.append({
                "smiles": o["smiles"],
                "svgs": [_svg(Chem.MolFromSmiles(s)) for s in o["smiles"]],
                "atoms": o.get("atoms", []),
                "why": o.get("why", ""),
            })
        note = t.note
        if any(o.get("tie") for o in outs) and t.regio:
            note = (note + " " if note else "") + "Both regioisomers are equally likely here."
        reactions.append({"name": t.name, "reagents": t.reagents, "category": t.category, "note": note, "products": products})
    return {"reactions": reactions, "count": len(reactions)}


def retrosynthesis(smiles: str) -> dict:
    mol = mol_from_smiles(smiles)
    if mol.GetNumHeavyAtoms() > 60:
        raise ChemError("Retrosynthesis is limited to 60 heavy atoms.")
    routes = []
    for t in RETRO:
        outs = _run(t, mol)
        if not outs:
            continue
        seen = set()
        precursors = []
        for smis, used in outs[:4]:
            key = tuple(sorted(smis))
            if key in seen:
                continue
            seen.add(key)
            precursors.append({"smiles": smis, "svgs": [_svg(Chem.MolFromSmiles(s)) for s in smis], "atoms": list(used)})
        routes.append({"name": t.name, "reagents": t.reagents, "target_group": t.category, "note": t.note, "precursors": precursors})
    return {"routes": routes, "count": len(routes)}


# --- classification --------------------------------------------------------

_CATEGORY_TEXT = {
    "addition": "Addition: the pi bond is replaced by two new sigma bonds.",
    "elimination": "Elimination: two groups leave and a pi bond forms.",
    "substitution": "Substitution: one group replaces another on a saturated carbon.",
    "aromatic substitution": "Electrophilic aromatic substitution: an electrophile replaces a ring hydrogen.",
    "oxidation": "Oxidation: the carbon gains bonds to oxygen or loses bonds to hydrogen.",
    "reduction": "Reduction: the carbon gains bonds to hydrogen or loses bonds to oxygen.",
    "condensation": "Condensation: two molecules join with loss of a small molecule such as water.",
    "hydrolysis": "Hydrolysis: water splits the molecule.",
    "cycloaddition": "Cycloaddition: two pi systems form a ring in one step.",
}


def _degree_note(mol: Chem.Mol, atoms: list[int], category: str) -> str:
    """SN1/SN2 or E1/E2 hint from the substitution pattern of the reacting carbon."""
    if category not in ("substitution", "elimination"):
        return ""
    carbons = [mol.GetAtomWithIdx(i) for i in atoms if mol.GetAtomWithIdx(i).GetSymbol() == "C"]
    leaving = [a for a in carbons if any(n.GetSymbol() in ("Cl", "Br", "I", "O") for n in a.GetNeighbors())]
    if not leaving:
        return ""
    deg = max(sum(1 for n in a.GetNeighbors() if n.GetSymbol() == "C") for a in leaving)
    word = {0: "methyl", 1: "primary", 2: "secondary", 3: "tertiary"}.get(deg, "")
    if category == "substitution":
        mech = "SN2" if deg <= 1 else "SN1 or SN2 depending on conditions" if deg == 2 else "SN1"
    else:
        mech = "E2" if deg <= 1 else "E1 or E2 depending on conditions" if deg == 2 else "E1 (or E2 with a strong base)"
    return f"The carbon bearing the leaving group is {word}, so {mech} is expected."


def classify(reactant_smiles: list[str], product_smiles: list[str]) -> dict:
    """Try every forward template on each reactant; a hit whose product matches a listed product names the reaction."""
    reactants = [mol_from_smiles(s) for s in reactant_smiles]
    targets = {Chem.MolToSmiles(mol_from_smiles(s)) for s in product_smiles}
    plain_targets = {Chem.MolToSmiles(mol_from_smiles(s), isomericSmiles=False) for s in product_smiles}
    hits = []
    for mol in reactants:
        for t in FORWARD:
            for smis, used in _run(t, mol):
                canon = {Chem.MolToSmiles(Chem.MolFromSmiles(s), isomericSmiles=False) for s in smis}
                if canon & plain_targets:
                    hits.append({
                        "name": t.name,
                        "reagents": t.reagents,
                        "category": t.category,
                        "explanation": _CATEGORY_TEXT.get(t.category, ""),
                        "note": t.note,
                        "mechanism_note": _degree_note(mol, list(used), t.category),
                        "reactant": Chem.MolToSmiles(mol),
                        "atoms": list(used),
                    })
                    break
    # Fallback: describe what changed.
    from . import groups as _groups

    before = {}
    after = {}
    for m in reactants:
        for g in _groups.find_groups(m):
            before[g["name"]] = before.get(g["name"], 0) + len(g["atoms"])
    for s in product_smiles:
        for g in _groups.find_groups(mol_from_smiles(s)):
            after[g["name"]] = after.get(g["name"], 0) + len(g["atoms"])
    lost = [f"{k} ({before[k] - after.get(k, 0)})" for k in before if before[k] > after.get(k, 0)]
    gained = [f"{k} ({after[k] - before.get(k, 0)})" for k in after if after[k] > before.get(k, 0)]
    guess = ""
    if not hits:
        if any("Alkene" in g or "Alkyne" in g for g in lost) and not any("Alkene" in g or "Alkyne" in g for g in gained):
            guess = "Looks like an addition to a multiple bond."
        elif any("Alkene" in g for g in gained):
            guess = "Looks like an elimination: a double bond is formed."
        elif any("halide" in g for g in lost) and gained:
            guess = "Looks like a nucleophilic substitution: the halide is replaced."
        elif any(g.startswith("Alcohol") for g in lost) and any(("Aldehyde" in g or "Ketone" in g or "acid" in g) for g in gained):
            guess = "Looks like an oxidation of the alcohol."
        elif any(("Aldehyde" in g or "Ketone" in g) for g in lost) and any(g.startswith("Alcohol") for g in gained):
            guess = "Looks like a reduction of the carbonyl group."
        elif any("Ester" in g for g in gained) and any("acid" in g for g in lost):
            guess = "Looks like an esterification."
        elif any("Ester" in g for g in lost) and any("acid" in g for g in gained):
            guess = "Looks like an ester hydrolysis."
        elif len(reactants) == 2 and len(product_smiles) == 1:
            guess = "Two reactants give one product: an addition or a condensation."
        else:
            guess = "No template matched. Compare the functional groups lost and gained."
    return {"matches": hits, "groups_lost": lost, "groups_gained": gained, "guess": guess}
