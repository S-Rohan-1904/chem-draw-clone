"""SQLite persistence: users, saved molecules and the request cache."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

DB_PATH = os.environ.get("CHEM_DB_PATH", str(Path(__file__).resolve().parent.parent / "data.db"))
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    molecules: Mapped[list["SavedMolecule"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class SavedMolecule(Base):
    __tablename__ = "saved_molecules"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    label: Mapped[str] = mapped_column(String(256))
    input_text: Mapped[str] = mapped_column(Text)
    smiles: Mapped[str] = mapped_column(Text)
    collection: Mapped[str] = mapped_column(String(128), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    user: Mapped[User] = relationship(back_populates="molecules")


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    items: Mapped[list["AssignmentItem"]] = relationship(back_populates="assignment", cascade="all, delete-orphan", order_by="AssignmentItem.position")


class AssignmentItem(Base):
    __tablename__ = "assignment_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(Text)
    smiles: Mapped[str] = mapped_column(Text)
    inchikey: Mapped[str] = mapped_column(String(32), default="")

    assignment: Mapped[Assignment] = relationship(back_populates="items")


class AssignmentProgress(Base):
    __tablename__ = "assignment_progress"

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("assignment_items.id"), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    done_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class FailedInput(Base):
    """Inputs the parser rejected, counted without any user information."""

    __tablename__ = "failed_inputs"

    text: Mapped[str] = mapped_column(String(300), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=1)
    last_reason: Mapped[str] = mapped_column(Text, default="")
    last_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    inchikey: Mapped[str] = mapped_column(String(32))
    correct: Mapped[bool] = mapped_column(Boolean, default=False)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class NameLookup(Base):
    """Reverse lookups (InChIKey -> names) from PubChem; misses cached too."""

    __tablename__ = "name_lookup"

    inchikey: Mapped[str] = mapped_column(String(32), primary_key=True)
    iupac: Mapped[str] = mapped_column(Text, default="")
    title: Mapped[str] = mapped_column(Text, default="")
    cid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    found: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class NameCache(Base):
    """Normalised input text -> SMILES. Skips the OPSIN JVM call on a hit."""

    __tablename__ = "name_cache"

    key: Mapped[str] = mapped_column(String(2000), primary_key=True)
    smiles: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16))
    warning: Mapped[str] = mapped_column(Text, default="")
    normalised: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class MoleculeCache(Base):
    """Canonical SMILES -> full build result (SVG, 3D mol block, stereo, props)."""

    __tablename__ = "molecule_cache"

    smiles: Mapped[str] = mapped_column(String(4000), primary_key=True)
    result_json: Mapped[str] = mapped_column(Text)
    inchikey: Mapped[str] = mapped_column(String(32), default="", index=True)
    hits: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class SpectraCache(Base):
    """Canonical SMILES + kind ('nmr' | 'ir' | 'ms') -> spectra payload.
    Only complete results are stored; a failed lookup is retried next time."""

    __tablename__ = "spectra_cache"

    smiles: Mapped[str] = mapped_column(String(4000), primary_key=True)
    kind: Mapped[str] = mapped_column(String(8), primary_key=True)
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


PREWARM_PATH = os.environ.get("CHEM_PREWARM_PATH", str(Path(__file__).resolve().parent.parent / "prewarm.db"))


def init_db() -> None:
    Base.metadata.create_all(engine)
    _add_missing_columns()
    _backfill_inchikeys()
    import_prewarm()


def import_prewarm(path: str | None = None) -> int:
    """Copy cache rows from a prebuilt database (see scripts/prewarm.py) that
    the live database does not have yet. Returns rows added."""
    import sqlite3

    path = path or PREWARM_PATH
    live = engine.url.database or DB_PATH
    if not os.path.exists(path) or os.path.abspath(path) == os.path.abspath(live):
        return 0
    added = 0
    con = sqlite3.connect(live)
    try:
        con.execute("ATTACH DATABASE ? AS pre", (path,))
        for table in ("name_cache", "molecule_cache"):
            cols = [r[1] for r in con.execute(f"PRAGMA pre.table_info({table})").fetchall()]
            collist = ", ".join(cols)
            cur = con.execute(f"INSERT OR IGNORE INTO {table} ({collist}) SELECT {collist} FROM pre.{table}")
            added += max(cur.rowcount, 0)
        con.commit()
        con.execute("DETACH DATABASE pre")
    finally:
        con.close()
    return added


def _backfill_inchikeys() -> None:
    """Rows cached before the inchikey column existed."""
    import json

    with Session(engine) as db:
        rows = db.query(MoleculeCache).filter((MoleculeCache.inchikey == "") | (MoleculeCache.inchikey.is_(None))).all()
        for row in rows:
            row.inchikey = json.loads(row.result_json).get("inchikey", "")
        if rows:
            db.commit()


def _add_missing_columns() -> None:
    """Tiny forward-only migration: add columns that exist in the models but
    not yet in an older SQLite file."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name not in existing:
                    ddl = f'ALTER TABLE {table.name} ADD COLUMN {col.name} {col.type.compile(engine.dialect)}'
                    if col.default is not None and getattr(col.default, "arg", None) is not None and not callable(col.default.arg):
                        ddl += f" DEFAULT {col.default.arg!r}"
                    conn.execute(text(ddl))


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
