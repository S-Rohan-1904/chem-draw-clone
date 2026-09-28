"""Structure analysis endpoints: bonding, projections (Fischer, Haworth),
conformer scans, acid/base sites, isotopes, reaction tools."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from rdkit import Chem
from sqlalchemy.orm import Session

from .. import analysis, cache, chem, ratelimit, resolver
from ..db import get_db

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


class SmilesIn(BaseModel):
    smiles: str = Field(min_length=1, max_length=4000)


def _molblock(db: Session, smiles: str, request: Request) -> str:
    ratelimit.charge_unbuilt(request, db, smiles)
    data, _ = cache.get_or_build(db, smiles)
    return data["molblock"]


@router.post("/bonding")
def bonding(body: SmilesIn, request: Request, db: Session = Depends(get_db)):
    try:
        return analysis.bonding(body.smiles, _molblock(db, body.smiles, request))
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


class AcidBaseIn(BaseModel):
    smiles: str = Field(min_length=1, max_length=4000)
    ph: float = Field(default=7.4, ge=-2, le=16)


@router.post("/acidbase")
def acid_base(body: AcidBaseIn):
    from .. import acidbase

    try:
        return acidbase.analyse(body.smiles, body.ph)
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


class IsotopeLabel(BaseModel):
    atom_idx: int
    isotope: str = Field(max_length=6)
    count: int = Field(default=1, ge=1, le=12)


class IsotopesIn(BaseModel):
    smiles: str = Field(min_length=1, max_length=4000)
    labels: list[IsotopeLabel] = Field(default_factory=list, max_length=50)


@router.post("/isotopes")
def isotopes_apply(body: IsotopesIn):
    from .. import isotopes

    try:
        mol = chem.mol_from_smiles(body.smiles)
        out = isotopes.apply_labels(body.smiles, [lab.model_dump() for lab in body.labels])
        out["options"] = isotopes.options_for(mol)
        return out
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/sugars")
def sugar_projections(body: SmilesIn, request: Request, db: Session = Depends(get_db)):
    from .. import sugars

    try:
        return sugars.projections(_molblock(db, body.smiles, request))
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


class ScanIn(BaseModel):
    smiles: str = Field(min_length=1, max_length=4000)
    front: int
    back: int
    step: int = Field(default=10, ge=5, le=30)


@router.post("/scan", dependencies=[Depends(ratelimit.check)])
def torsion_scan(body: ScanIn, request: Request, db: Session = Depends(get_db)):
    from .. import conformers

    try:
        return conformers.torsion_scan(_molblock(db, body.smiles, request), body.front, body.back, body.step)
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


class ChairEnergyIn(BaseModel):
    smiles: str = Field(min_length=1, max_length=4000)
    ring: list[int] = Field(min_length=6, max_length=6)


@router.post("/chair-energy", dependencies=[Depends(ratelimit.check)])
def chair_energy(body: ChairEnergyIn, request: Request, db: Session = Depends(get_db)):
    from .. import conformers

    try:
        return conformers.chair_energies(_molblock(db, body.smiles, request), body.ring)
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/reactions", dependencies=[Depends(ratelimit.check)])
def recorded_reactions(body: SmilesIn):
    """Top recorded reactions for the molecule (as reactant and as product) from the USPTO index."""
    from .. import reactiondb

    try:
        return reactiondb.lookup(body.smiles)
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


class ClassifyIn(BaseModel):
    reactants: list[str] = Field(min_length=1, max_length=10)
    products: list[str] = Field(min_length=1, max_length=10)


@router.post("/classify")
def classify_reaction(body: ClassifyIn):
    from .. import reaction

    try:
        return reaction.classify(body.reactants, body.products)
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


class LiteratureIn(BaseModel):
    smiles: str = Field(min_length=1, max_length=4000)
    name: str = Field(default="", max_length=300)


@router.post("/literature", dependencies=[Depends(ratelimit.check)])
def literature_search(body: LiteratureIn, db: Session = Depends(get_db)):
    """Top ChemRxiv preprints for the molecule, searched by its common name."""
    from .. import literature

    try:
        key = Chem.MolToInchiKey(chem.mol_from_smiles(body.smiles))
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    row = cache.lookup_name(db, key) if key else None
    # PubChem's title first (usually the common name), then what the user typed, then the
    # systematic name; the stereo-free record's title only if all of those find nothing.
    names = [n for n in ((row.title if row and row.found else ""), body.name.strip(), (row.iupac if row and row.found else "")) if n]
    return cache.get_literature(db, key, lambda: literature.search(names, more=lambda: [resolver.title_for_skeleton(key)]))


@router.get("/mechanisms")
def mechanisms_list():
    from .. import mechanisms

    return {"mechanisms": mechanisms.list_mechanisms()}


@router.get("/mechanisms/{mech_id}")
def mechanism_detail(mech_id: str):
    from .. import mechanisms

    try:
        return mechanisms.get_mechanism(mech_id)
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
