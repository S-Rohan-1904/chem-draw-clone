"""SQLite persistence: users, saved molecules and the request cache."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, create_engine
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    user: Mapped[User] = relationship(back_populates="molecules")


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
    hits: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
