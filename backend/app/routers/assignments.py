"""Assignments: a user creates a list of names, shares a short code, and
sees who has worked through it. Any account can create one."""

from __future__ import annotations

import secrets
import string
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import chem
from ..auth import current_user
from ..db import Assignment, AssignmentItem, AssignmentProgress, User, get_db

router = APIRouter(prefix="/api/assignments", tags=["assignments"])

_ALPHABET = string.ascii_uppercase.replace("O", "").replace("I", "") + string.digits.replace("0", "").replace("1", "")


def _code(db: Session) -> str:
    while True:
        code = "".join(secrets.choice(_ALPHABET) for _ in range(6))
        if db.scalar(select(Assignment).where(Assignment.code == code)) is None:
            return code


class AssignmentIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    names: list[str] = Field(min_length=1, max_length=100)


class ItemOut(BaseModel):
    id: int
    position: int
    name: str  # blank for students until they answer correctly
    smiles: str  # blank for students until they answer correctly
    svg: str = ""
    formula: str = ""
    done: bool = False
    attempts: int = 0


class AssignmentOut(BaseModel):
    id: int
    title: str
    code: str
    owner: str
    mine: bool
    created_at: datetime
    items: list[ItemOut]
    done_count: int = 0


class CreateOut(BaseModel):
    assignment: AssignmentOut
    rejected: list[dict]


def _svg_formula(db: Session, smiles: str, annotate: bool = True) -> tuple[str, str]:
    from .. import cache

    data, _ = cache.get_or_build(db, smiles)
    if annotate:
        return data["svg"], data["formula"]
    # Students get the drawing without R/S and E/Z labels: those are part of the answer.
    return chem.render_svg(chem.mol_from_smiles(smiles), annotate=False), data["formula"]


def _out(a: Assignment, user: User | None, db: Session) -> AssignmentOut:
    progress: dict[int, int] = {}
    if user is not None:
        rows = db.scalars(select(AssignmentProgress).where(AssignmentProgress.assignment_id == a.id, AssignmentProgress.user_id == user.id)).all()
        progress = {r.item_id: r.attempts for r in rows}
    owner = db.get(User, a.owner_id)
    mine = user is not None and a.owner_id == user.id
    items = []
    for i in a.items:
        done = i.id in progress
        reveal = mine or done
        svg, formula = _svg_formula(db, i.smiles, annotate=reveal)
        items.append(ItemOut(id=i.id, position=i.position, name=i.name if reveal else "", smiles=i.smiles if reveal else "", svg=svg, formula=formula, done=done, attempts=progress.get(i.id, 0)))
    return AssignmentOut(
        id=a.id,
        title=a.title,
        code=a.code,
        owner=owner.username if owner else "",
        mine=mine,
        created_at=a.created_at,
        items=items,
        done_count=len(progress),
    )


@router.post("", response_model=CreateOut, status_code=status.HTTP_201_CREATED)
def create(body: AssignmentIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    a = Assignment(owner_id=user.id, title=body.title.strip(), code=_code(db))
    rejected = []
    pos = 0
    for raw in body.names:
        name = raw.strip()
        if not name:
            continue
        try:
            resolved = chem.resolve_full(name)
            smiles = chem.canonical_smiles(resolved.smiles)
            from rdkit import Chem

            key = Chem.MolToInchiKey(Chem.MolFromSmiles(smiles))
        except chem.ChemError as e:
            rejected.append({"name": name, "reason": str(e).split(".")[0]})
            continue
        a.items.append(AssignmentItem(position=pos, name=name, smiles=smiles, inchikey=key))
        pos += 1
    if not a.items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "None of the names could be read.")
    db.add(a)
    db.commit()
    return CreateOut(assignment=_out(a, user, db), rejected=rejected)


@router.get("/mine", response_model=list[AssignmentOut])
def mine(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Assignment).where(Assignment.owner_id == user.id).order_by(Assignment.created_at.desc())).all()
    return [_out(a, user, db) for a in rows]


@router.get("/joined", response_model=list[AssignmentOut])
def joined(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ids = set(db.scalars(select(AssignmentProgress.assignment_id).where(AssignmentProgress.user_id == user.id)).all())
    rows = [db.get(Assignment, i) for i in ids]
    return [_out(a, user, db) for a in rows if a is not None]


@router.get("/{code}", response_model=AssignmentOut)
def get(code: str, db: Session = Depends(get_db), user: User | None = Depends(lambda: None)):
    a = db.scalar(select(Assignment).where(Assignment.code == code.strip().upper()))
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No assignment with that code.")
    return _out(a, user, db)


@router.get("/{code}/me", response_model=AssignmentOut)
def get_with_progress(code: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    a = db.scalar(select(Assignment).where(Assignment.code == code.strip().upper()))
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No assignment with that code.")
    return _out(a, user, db)


class AssignmentAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=200_000)
    attempt: int = Field(default=1, ge=1, le=50)


class AssignmentAnswerOut(BaseModel):
    correct: bool
    verdict: str
    message: str
    assignment: AssignmentOut


@router.post("/{code}/answer/{item_id}", response_model=AssignmentAnswerOut)
def answer_item(code: str, item_id: int, body: AssignmentAnswer, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Students name (or draw) the structure; a correct answer marks the item done."""
    from ..grading import grade

    a = db.scalar(select(Assignment).where(Assignment.code == code.strip().upper()))
    item = next((i for i in a.items), None) if a else None
    item = next((i for i in a.items if i.id == item_id), None) if a else None
    if a is None or item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    _, formula = _svg_formula(db, item.smiles)
    v = grade(body.answer, item.inchikey, formula)
    if v.correct:
        exists = db.scalar(select(AssignmentProgress).where(AssignmentProgress.user_id == user.id, AssignmentProgress.item_id == item_id))
        if exists is None:
            db.add(AssignmentProgress(assignment_id=a.id, user_id=user.id, item_id=item_id, attempts=body.attempt))
            db.commit()
    return AssignmentAnswerOut(correct=v.correct, verdict=v.verdict, message=v.message, assignment=_out(a, user, db))


@router.get("/{code}/progress")
def progress(code: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Owner view: every participant and which items they finished."""
    a = db.scalar(select(Assignment).where(Assignment.code == code.strip().upper()))
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    if a.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the owner can see progress.")
    rows = db.scalars(select(AssignmentProgress).where(AssignmentProgress.assignment_id == a.id)).all()
    by_user: dict[int, set[int]] = {}
    for r in rows:
        by_user.setdefault(r.user_id, set()).add(r.item_id)
    attempts = {(r.user_id, r.item_id): r.attempts for r in rows}
    users = {u.id: u.username for u in db.scalars(select(User).where(User.id.in_(by_user.keys()))).all()} if by_user else {}
    return {
        "items": [{"id": i.id, "name": i.name} for i in a.items],
        "participants": sorted(
            [
                {
                    "username": users.get(uid, "?"),
                    "done": sorted(items),
                    "attempts": {str(i): attempts[(uid, i)] for i in items},
                    "count": len(items),
                }
                for uid, items in by_user.items()
            ],
            key=lambda p: (-p["count"], p["username"]),
        ),
    }


@router.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT)
def delete(code: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    a = db.scalar(select(Assignment).where(Assignment.code == code.strip().upper()))
    if a is None or a.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    for r in db.scalars(select(AssignmentProgress).where(AssignmentProgress.assignment_id == a.id)).all():
        db.delete(r)
    db.delete(a)
    db.commit()
