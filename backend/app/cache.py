"""Two-level request cache backed by SQLite.

1. name_cache: normalised input text -> SMILES (avoids the OPSIN JVM start).
2. molecule_cache: canonical SMILES -> serialised MoleculeResult (avoids depiction and
   3D embedding). Different names for the same molecule share this entry.

Failures are never cached, so a bad name is re-checked each time.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from . import chem, resolver
from .db import LiteratureCache, MoleculeCache, NameCache, NameLookup, SpectraCache


def normalise(text: str) -> str:
    """Name cache key. Case is kept: SMILES are case sensitive (C1CCCCC1 is
    cyclohexane, c1ccccc1 is benzene)."""
    return chem.normalise_name(text)


def encode_warnings(warnings: list[str]) -> str:
    return json.dumps(warnings) if warnings else ""


def decode_warnings(stored: str) -> list[str]:
    """name_cache.warning: a JSON list, or one plain string in older rows."""
    if not stored:
        return []
    if stored.startswith("["):
        try:
            return list(json.loads(stored))
        except ValueError:
            pass
    return [stored]


# Bump when the serialised result gains fields; older cache rows are rebuilt on read.
CACHE_VERSION = 4


def _serialise(result: chem.MoleculeResult) -> dict:
    data = asdict(result)
    data["stereo"]["unspecified"] = result.stereo.unspecified
    data["_v"] = CACHE_VERSION
    return data


def _current(data: dict) -> bool:
    return data.get("_v") == CACHE_VERSION


def is_built(db: Session, smiles: str) -> bool:
    """True if the molecule is already in the cache, so fetching it is cheap."""
    try:
        key = chem.canonical_smiles(smiles)
    except chem.ChemError:
        return False
    row = db.get(MoleculeCache, key)
    return row is not None and _current(json.loads(row.result_json))


def _load_or_build(db: Session, smiles: str, input_text: str, source: str) -> tuple[dict, bool]:
    """Full result for a canonical SMILES from molecule_cache, building and
    storing it on a miss. Returns (data, cached); the caller commits."""
    row = db.get(MoleculeCache, smiles)
    if row is not None:
        data = json.loads(row.result_json)
        if _current(data):
            row.hits += 1
            row.last_used_at = datetime.now(timezone.utc)
            return data, True
    data = _serialise(chem.build_from_smiles(smiles, input_text=input_text, source=source))
    if row is not None:
        row.result_json = json.dumps(data)
        row.inchikey = data["inchikey"]
    else:
        db.add(MoleculeCache(smiles=smiles, result_json=json.dumps(data), inchikey=data["inchikey"]))
    return data, False


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        # Another request built the same molecule or name at the same time and
        # stored it first. Its row holds the same result, so drop ours.
        db.rollback()


def get_or_build(db: Session, text: str) -> tuple[dict, bool]:
    """Return (response dict, cached). Fills both cache levels on a miss."""
    if chem._is_molfile(text):
        # Drawn structures: no name to cache; key only on the molecule.
        resolved = chem.resolve_molfile(text)
        smiles = chem.canonical_smiles(resolved.smiles)
        data, cached = _load_or_build(db, smiles, smiles, resolved.source)
        _commit(db)
        input_text, source, warnings, normalised = smiles, resolved.source, resolved.warnings, resolved.normalised
    else:
        key = normalise(text)
        name_row = db.get(NameCache, key)
        if name_row is not None:
            smiles, source = name_row.smiles, name_row.source
            warnings, normalised = decode_warnings(name_row.warning), name_row.normalised
        else:
            resolved = chem.resolve_full(text)
            smiles = chem.canonical_smiles(resolved.smiles)
            source, warnings, normalised = resolved.source, resolved.warnings, resolved.normalised
        data, cached = _load_or_build(db, smiles, text.strip(), source)
        if name_row is None:
            db.merge(NameCache(key=key, smiles=smiles, source=source, warning=encode_warnings(warnings), normalised=normalised))
        _commit(db)
        # Echo what the user actually typed, not whoever filled the cache first.
        input_text = text.strip()

    data["input_text"] = input_text
    data["source"] = source
    data["warnings"] = warnings
    data["normalised_input"] = normalised
    return data, cached


def get_by_inchikey(db: Session, inchikey: str) -> dict | None:
    """Shared-link lookup. Only molecules built before are known."""
    row = db.scalar(select(MoleculeCache).where(MoleculeCache.inchikey == inchikey))
    if row is None:
        return None
    data = json.loads(row.result_json)
    if not _current(data):
        data = _serialise(chem.build_from_smiles(row.smiles, input_text=data.get("input_text", row.smiles), source=data.get("source", "smiles")))
        row.result_json = json.dumps(data)
    row.hits += 1
    row.last_used_at = datetime.now(timezone.utc)
    db.commit()
    data["warnings"] = []
    data["normalised_input"] = ""
    data["cached"] = True
    return data


# Bump when the spectra payload gains fields, so stale rows are rebuilt.
SPECTRA_VERSION = 3


def get_spectra(db: Session, smiles: str, kind: str, builder) -> dict:
    """Spectra payload for (canonical smiles, kind). `builder(smiles, kind)`
    returns (payload, complete); incomplete results (network trouble) are
    returned but not stored."""
    row = db.get(SpectraCache, (smiles, kind))
    if row is not None:
        data = json.loads(row.result_json)
        if data.get("_sv") == SPECTRA_VERSION:
            data["cached"] = True
            return data
    data, complete = builder(smiles, kind)
    data["_sv"] = SPECTRA_VERSION
    if complete:
        db.merge(SpectraCache(smiles=smiles, kind=kind, result_json=json.dumps(data)))
        try:
            db.commit()
        except (IntegrityError, OperationalError):
            # Two identical requests raced (the UI can fire the same call twice);
            # the other one stored the row, and this payload is just as good.
            db.rollback()
    data["cached"] = False
    return data


def lookup_name(db: Session, inchikey: str, before_fetch: Callable[[], None] | None = None) -> NameLookup:
    """PubChem names for an InChIKey, cached. Misses are retried after a day.
    `before_fetch` runs only when PubChem is actually asked (e.g. to charge a rate limit)."""
    key = inchikey.strip().upper()
    row = db.get(NameLookup, key)
    fresh = row is not None and (row.found or (datetime.now(timezone.utc) - row.created_at.replace(tzinfo=timezone.utc)) < timedelta(days=1))
    if not fresh:
        if before_fetch is not None:
            before_fetch()
        hit = resolver.name_for_inchikey(key)
        if row is None:
            row = NameLookup(inchikey=key)
            db.add(row)
        row.found = hit is not None
        row.iupac = (hit or {}).get("iupac", "")
        row.title = (hit or {}).get("title", "")
        row.cid = (hit or {}).get("cid")
        row.created_at = datetime.now(timezone.utc)
        try:
            db.commit()
        except (IntegrityError, OperationalError):
            db.rollback()
    return row


def get_literature(db: Session, inchikey: str, search) -> dict:
    """ChemRxiv results for a molecule. `search()` returns (payload, complete).
    OpenAlex results with papers are kept 30 days; empty results and the thinner
    Crossref fallback a day, so a better answer replaces them; failures are not kept."""
    row = db.get(LiteratureCache, inchikey)
    if row is not None:
        data = json.loads(row.result_json)
        age = datetime.now(timezone.utc) - row.created_at.replace(tzinfo=timezone.utc)
        keep = timedelta(days=30) if data.get("items") and data.get("source") == "OpenAlex" else timedelta(days=1)
        if age < keep and data.get("_v") == literature_version():
            data["cached"] = True
            return data
    data, complete = search()
    if complete:
        db.merge(LiteratureCache(inchikey=inchikey, result_json=json.dumps(data), created_at=datetime.now(timezone.utc)))
        try:
            db.commit()
        except (IntegrityError, OperationalError):
            db.rollback()
    data["cached"] = False
    return data


def literature_version() -> int:
    from . import literature

    return literature.VERSION
