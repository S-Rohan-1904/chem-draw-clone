"""Name-the-structure quiz. Questions come from molecules already in the
cache (the prewarmed common-names list), so no new computation is needed."""

from __future__ import annotations

import json
import random
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import chem
from ..auth import current_user
from ..db import MoleculeCache, NameCache, QuizAttempt, User, get_db

router = APIRouter(prefix="/api/quiz", tags=["quiz"])
_bearer = HTTPBearer(auto_error=False)

# Names that are trivial rather than systematic are poor quiz answers to reveal.
_TRIVIAL = re.compile(r"^(?:[DL]-|\(\+\)|\(-\))|^[a-z]+$")


_SYSTEMATIC_SUFFIX = ("ane", "ene", "yne", "ol", "al", "one", "oic acid", "amine", "amide", "nitrile", "oate", "ide", "ether", "benzene", "phenol")


def _systematic(name: str) -> bool:
    if name.startswith(("D-", "L-", "(+)", "(-)")):
        return False
    return bool(re.search(r"\d|-|\(", name)) or name.lower().endswith(_SYSTEMATIC_SUFFIX)


def _level_ok(level: int, data: dict) -> bool:
    p = data.get("properties", {})
    heavy = p.get("heavy_atoms", 99)
    stereo = len(data["stereo"]["centers"]) + len(data["stereo"]["double_bonds"])
    if data["stereo"]["unspecified"] or data.get("warnings"):
        return False
    if level == 1:
        return heavy <= 8 and stereo == 0
    if level == 2:
        return 6 <= heavy <= 16 and stereo == 0
    if level == 4:
        return heavy <= 12
    return stereo >= 1 and heavy <= 20


def _answers_for(db: Session, smiles: str) -> list[str]:
    rows = db.scalars(select(NameCache).where(NameCache.smiles == smiles, NameCache.source == "iupac")).all()
    names = [r.normalised or r.key for r in rows]
    return sorted(names, key=lambda n: (not _systematic(n), len(n)))


class Question(BaseModel):
    id: str  # inchikey
    svg: str = ""
    name: str = ""  # level 4 (draw it): the name to draw instead of a picture
    formula: str
    level: int
    stereo_count: int


@router.get("/question", response_model=Question)
def question(level: int = 1, exclude: str = "", db: Session = Depends(get_db)):
    level = max(1, min(4, level))
    skip = set(exclude.split(",")) if exclude else set()
    rows = db.scalars(select(MoleculeCache).where(MoleculeCache.inchikey != "")).all()
    random.shuffle(rows)
    for row in rows:
        if row.inchikey in skip:
            continue
        data = json.loads(row.result_json)
        if data.get("source") != "iupac" and not _answers_for(db, row.smiles):
            continue
        if not _level_ok(level, data):
            continue
        names = _answers_for(db, row.smiles)
        if not names:
            continue
        stereo_count = len(data["stereo"]["centers"]) + len(data["stereo"]["double_bonds"])
        if level == 4:
            systematic = [n for n in names if _systematic(n)]
            if not systematic:
                continue
            return Question(id=row.inchikey, name=systematic[0], formula=data["formula"], level=level, stereo_count=stereo_count)
        return Question(id=row.inchikey, svg=data["svg"], formula=data["formula"], level=level, stereo_count=stereo_count)
    raise HTTPException(status.HTTP_404_NOT_FOUND, "No questions available at this level yet.")


class AnswerIn(BaseModel):
    id: str = Field(min_length=10, max_length=40)
    answer: str = Field(min_length=1, max_length=200_000)  # a name, or a molfile for draw questions
    attempt: int = Field(default=1, ge=1, le=10)
    reveal: bool = False


class AnswerOut(BaseModel):
    correct: bool
    verdict: str  # exact | stereo | wrong | unparsed | revealed
    message: str
    accepted: list[str] = []
    your_formula: str | None = None


def _optional_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)) -> User | None:
    if creds is None:
        return None
    try:
        return current_user(creds, db)
    except HTTPException:
        return None


@router.post("/answer", response_model=AnswerOut)
def answer(body: AnswerIn, db: Session = Depends(get_db), user: User | None = Depends(_optional_user)):
    target = db.scalar(select(MoleculeCache).where(MoleculeCache.inchikey == body.id))
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown question.")
    accepted = _answers_for(db, target.smiles)

    def record(correct: bool) -> None:
        if user is not None:
            db.add(QuizAttempt(user_id=user.id, inchikey=body.id, correct=correct, attempts=body.attempt))
            db.commit()

    if body.reveal:
        record(False)
        return AnswerOut(correct=False, verdict="revealed", message="Answer revealed.", accepted=accepted)

    try:
        resolved = chem.resolve_full(body.answer)
        mol = chem.mol_from_smiles(resolved.smiles)
    except chem.ChemError as e:
        what = "structure" if chem._is_molfile(body.answer) else "name"
        return AnswerOut(correct=False, verdict="unparsed", message=f"That is not a readable {what}: {str(e).split('.')[0]}.")

    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors

    key = Chem.MolToInchiKey(mol)
    formula = rdMolDescriptors.CalcMolFormula(mol)
    if key == body.id:
        record(True)
        return AnswerOut(correct=True, verdict="exact", message="Correct.", accepted=accepted, your_formula=formula)
    if key.split("-")[0] == body.id.split("-")[0]:
        msg = "Right skeleton, wrong or missing stereochemistry."
        if resolved.warnings:
            msg += " " + resolved.warnings[0]
        return AnswerOut(correct=False, verdict="stereo", message=msg, your_formula=formula)
    hint = "Same formula, different connectivity." if formula == json.loads(target.result_json)["formula"] else f"Your name gives {formula}."
    return AnswerOut(correct=False, verdict="wrong", message=f"Not this molecule. {hint}", your_formula=formula)


@router.get("/stats")
def stats(user: User = Depends(current_user), db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(QuizAttempt).where(QuizAttempt.user_id == user.id)) or 0
    correct = db.scalar(select(func.count()).select_from(QuizAttempt).where(QuizAttempt.user_id == user.id, QuizAttempt.correct.is_(True))) or 0
    recent = db.scalars(select(QuizAttempt).where(QuizAttempt.user_id == user.id).order_by(QuizAttempt.created_at.desc()).limit(20)).all()
    streak = 0
    for r in recent:
        if not r.correct:
            break
        streak += 1
    names: dict[str, str] = {}
    for r in recent:
        if r.inchikey in names:
            continue
        row = db.scalar(select(MoleculeCache).where(MoleculeCache.inchikey == r.inchikey))
        if row is not None:
            ans = _answers_for(db, row.smiles)
            names[r.inchikey] = ans[0] if ans else row.smiles
    return {
        "total": total,
        "correct": correct,
        "streak": streak,
        "recent": [{"inchikey": r.inchikey, "name": names.get(r.inchikey, ""), "correct": r.correct, "attempts": r.attempts, "at": r.created_at} for r in recent],
    }
