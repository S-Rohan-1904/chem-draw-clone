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
