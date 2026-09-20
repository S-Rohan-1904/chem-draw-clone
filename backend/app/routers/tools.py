"""Utility endpoints: elemental analysis, sequences, conformer ensemble,
minimisation, and search over the user's saved molecules."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import cache, chem, ratelimit, tools
from ..auth import current_user
from ..db import SavedMolecule, User, get_db

router = APIRouter(prefix="/api/tools", tags=["tools"])


class SmilesIn(BaseModel):
    smiles: str = Field(min_length=1, max_length=4000)


@router.post("/elemental")
def elemental(body: SmilesIn):
    try:
        return tools.elemental(body.smiles)
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


class SequenceIn(BaseModel):
    kind: str = Field(pattern="^(peptide|d-peptide|dna|rna|helm)$")
    sequence: str = Field(min_length=1, max_length=2000)


@router.post("/sequence")
def sequence(body: SequenceIn):
    try:
        return tools.from_sequence(body.kind, body.sequence)
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


class ConformersIn(BaseModel):
    smiles: str = Field(min_length=1, max_length=4000)
    n: int = Field(default=8, ge=2, le=12)


@router.post("/conformers", dependencies=[Depends(ratelimit.check)])
def conformers(body: ConformersIn):
    try:
        return tools.conformers(body.smiles, body.n)
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/minimise", dependencies=[Depends(ratelimit.check)])
def minimise(body: SmilesIn, db: Session = Depends(get_db)):
    try:
        data, _ = cache.get_or_build(db, body.smiles)
        return tools.minimise(data["molblock"])
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


class SearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    mode: str = Field(default="auto", pattern="^(auto|substructure|similarity)$")


@router.post("/search")
def search_saved(body: SearchIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(SavedMolecule.id, SavedMolecule.smiles).where(SavedMolecule.user_id == user.id)).all()
    try:
        return tools.search(body.query, [(r.id, r.smiles) for r in rows], body.mode)
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
