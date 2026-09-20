"""Structure analysis endpoints: bonding, projections (Fischer, Haworth),
conformer scans, acid/base sites, isotopes, reaction tools."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import analysis, cache, chem, ratelimit
from ..db import get_db

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


class SmilesIn(BaseModel):
    smiles: str = Field(min_length=1, max_length=4000)


def _molblock(db: Session, smiles: str) -> str:
    data, _ = cache.get_or_build(db, smiles)
    return data["molblock"]


@router.post("/bonding")
def bonding(body: SmilesIn, db: Session = Depends(get_db)):
    try:
        return analysis.bonding(body.smiles, _molblock(db, body.smiles))
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
def sugar_projections(body: SmilesIn, db: Session = Depends(get_db)):
    from .. import sugars

    try:
        return sugars.projections(_molblock(db, body.smiles))
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


class ScanIn(BaseModel):
    smiles: str = Field(min_length=1, max_length=4000)
    front: int
    back: int
    step: int = Field(default=10, ge=5, le=30)


@router.post("/scan", dependencies=[Depends(ratelimit.check)])
def torsion_scan(body: ScanIn, db: Session = Depends(get_db)):
    from .. import conformers

    try:
        return conformers.torsion_scan(_molblock(db, body.smiles), body.front, body.back, body.step)
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


class ChairEnergyIn(BaseModel):
    smiles: str = Field(min_length=1, max_length=4000)
    ring: list[int] = Field(min_length=6, max_length=6)


@router.post("/chair-energy", dependencies=[Depends(ratelimit.check)])
def chair_energy(body: ChairEnergyIn, db: Session = Depends(get_db)):
    from .. import conformers

    try:
        return conformers.chair_energies(_molblock(db, body.smiles), body.ring)
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
