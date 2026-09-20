from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import current_user
from ..chem import ChemError, mol_from_smiles
from ..db import SavedMolecule, User, get_db

router = APIRouter(prefix="/api/saved", tags=["saved"])


class SavedIn(BaseModel):
    label: str = Field(min_length=1, max_length=256)
    input_text: str = Field(min_length=1)
    smiles: str = Field(min_length=1)


class SavedOut(BaseModel):
    id: int
    label: str
    input_text: str
    smiles: str
    created_at: datetime


@router.get("", response_model=list[SavedOut])
def list_saved(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(SavedMolecule)
        .where(SavedMolecule.user_id == user.id)
        .order_by(SavedMolecule.created_at.desc())
    )
    return list(rows)


@router.post("", response_model=SavedOut, status_code=status.HTTP_201_CREATED)
def create_saved(body: SavedIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        mol_from_smiles(body.smiles)
    except ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    row = SavedMolecule(user_id=user.id, label=body.label, input_text=body.input_text, smiles=body.smiles)
    db.add(row)
    db.commit()
    return row


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved(item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.get(SavedMolecule, item_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    db.delete(row)
    db.commit()
