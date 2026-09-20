"""Usage statistics for the site owner. No per-user browsing data is stored;
counts come from the cache, quiz and assignment tables."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import admin_user
from ..db import Assignment, AssignmentProgress, FailedInput, MoleculeCache, NameCache, QuizAttempt, User, get_db

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(admin_user)])


def _per_day(db: Session, column, days: int) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    day = func.date(column)
    rows = db.execute(select(day, func.count()).where(column >= since).group_by(day).order_by(day)).all()
    return [{"day": str(d), "count": int(c)} for d, c in rows]


@router.get("/stats")
def stats(days: int = 14, db: Session = Depends(get_db)):
    days = max(1, min(90, days))
    total_mols = db.scalar(select(func.count()).select_from(MoleculeCache)) or 0
    total_names = db.scalar(select(func.count()).select_from(NameCache)) or 0
    total_hits = db.scalar(select(func.coalesce(func.sum(MoleculeCache.hits), 0))) or 0
    users = db.scalar(select(func.count()).select_from(User)) or 0
    quiz_total = db.scalar(select(func.count()).select_from(QuizAttempt)) or 0
    quiz_correct = db.scalar(select(func.count()).select_from(QuizAttempt).where(QuizAttempt.correct.is_(True))) or 0
    assignments = db.scalar(select(func.count()).select_from(Assignment)) or 0
    top = db.scalars(select(MoleculeCache).where(MoleculeCache.hits > 0).order_by(MoleculeCache.hits.desc()).limit(15)).all()
    failing = db.scalars(select(FailedInput).order_by(FailedInput.count.desc(), FailedInput.last_at.desc()).limit(20)).all()
    return {
        "totals": {
            "molecules_cached": total_mols,
            "names_cached": total_names,
            "cache_hits": int(total_hits),
            "users": users,
            "quiz_attempts": quiz_total,
            "quiz_correct": quiz_correct,
            "assignments": assignments,
            "assignment_completions": db.scalar(select(func.count()).select_from(AssignmentProgress)) or 0,
        },
        "new_molecules_per_day": _per_day(db, MoleculeCache.created_at, days),
        "quiz_attempts_per_day": _per_day(db, QuizAttempt.created_at, days),
        "signups_per_day": _per_day(db, User.created_at, days),
        "top_molecules": [
            {"smiles": r.smiles, "hits": r.hits, "name": (db.scalar(select(NameCache.normalised).where(NameCache.smiles == r.smiles)) or "")}
            for r in top
        ],
        "top_failures": [{"text": f.text, "count": f.count, "reason": f.last_reason, "last_at": f.last_at} for f in failing],
    }
