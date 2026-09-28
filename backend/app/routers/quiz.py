"""Name-the-structure quiz. Questions come from molecules already in the
cache (the prewarmed common-names list), so no new computation is needed."""

from __future__ import annotations

import json
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import current_user, optional_user
from ..db import MoleculeCache, NameCache, QuizAttempt, User, get_db

router = APIRouter(prefix="/api/quiz", tags=["quiz"])

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
    skip = [k for k in exclude.split(",") if k][-200:]
    # Keys only, in random order, and only molecules that have a systematic
    # name to accept. Full rows (SVG, mol block) are loaded one at a time
    # until one fits the level.
    named = select(NameCache.smiles).where(NameCache.source == "iupac")
    keys = select(MoleculeCache.smiles).where(MoleculeCache.inchikey != "", MoleculeCache.smiles.in_(named))
    if skip:
        keys = keys.where(MoleculeCache.inchikey.not_in(skip))
    for smiles in db.scalars(keys.order_by(func.random())).all():
        row = db.get(MoleculeCache, smiles)
        data = json.loads(row.result_json)
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


@router.post("/answer", response_model=AnswerOut)
def answer(body: AnswerIn, db: Session = Depends(get_db), user: User | None = Depends(optional_user)):
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

    from ..grading import grade

    v = grade(body.answer, body.id, json.loads(target.result_json)["formula"])
    if v.correct:
        record(True)
    return AnswerOut(correct=v.correct, verdict=v.verdict, message=v.message, accepted=accepted if v.correct else [], your_formula=v.your_formula)


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
