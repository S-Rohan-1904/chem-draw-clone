"""Two-level request cache backed by SQLite.

1. name_cache: normalised input text -> SMILES (avoids the OPSIN JVM start).
2. molecule_cache: canonical SMILES -> serialised MoleculeResult (avoids depiction and
   3D embedding). Different names for the same molecule share this entry.

Failures are never cached, so a bad name is re-checked each time.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import chem
from .db import MoleculeCache, NameCache


def normalise(text: str) -> str:
    return chem.normalise_name(text).lower()


def _serialise(result: chem.MoleculeResult) -> dict:
    data = asdict(result)
    data["stereo"]["unspecified"] = result.stereo.unspecified
    return data


def _from_molecule_cache(db: Session, smiles: str, text: str, resolved: chem.Resolved) -> dict:
    mol_row = db.get(MoleculeCache, smiles)
    if mol_row is not None:
        data = json.loads(mol_row.result_json)
        mol_row.hits += 1
        mol_row.last_used_at = datetime.now(timezone.utc)
    else:
        data = _serialise(chem.build_from_smiles(smiles, input_text=smiles, source=resolved.source))
        db.add(MoleculeCache(smiles=smiles, result_json=json.dumps(data), inchikey=data["inchikey"]))
    db.commit()
    data["input_text"] = smiles if resolved.source == "molfile" else text.strip()
    data["source"] = resolved.source
    data["warnings"] = resolved.warnings
    data["normalised_input"] = resolved.normalised
    return data


def get_or_build(db: Session, text: str) -> tuple[dict, bool]:
    """Return (response dict, cached). Fills both cache levels on a miss."""
    if chem._is_molfile(text):
        # Drawn structures: no name to cache; key only on the molecule.
        resolved = chem.resolve_molfile(text)
        cached = db.get(MoleculeCache, resolved.smiles) is not None
        return _from_molecule_cache(db, resolved.smiles, text, resolved), cached

    key = normalise(text)
    name_row = db.get(NameCache, key)
    if name_row is not None:
        smiles, source = name_row.smiles, name_row.source
        warnings = [name_row.warning] if name_row.warning else []
        normalised = name_row.normalised
    else:
        resolved = chem.resolve_full(text)
        smiles = chem.canonical_smiles(resolved.smiles)
        source, warnings, normalised = resolved.source, resolved.warnings, resolved.normalised

    mol_row = db.get(MoleculeCache, smiles)
    if mol_row is not None:
        data = json.loads(mol_row.result_json)
        mol_row.hits += 1
        mol_row.last_used_at = datetime.now(timezone.utc)
        cached = True
    else:
        data = _serialise(chem.build_from_smiles(smiles, input_text=text.strip(), source=source))
        db.add(MoleculeCache(smiles=smiles, result_json=json.dumps(data), inchikey=data["inchikey"]))
        cached = False

    if name_row is None:
        db.merge(NameCache(key=key, smiles=smiles, source=source, warning=" ".join(warnings), normalised=normalised))
    db.commit()

    # Echo what the user actually typed, not whoever filled the cache first.
    data["input_text"] = text.strip()
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
    row.hits += 1
    row.last_used_at = datetime.now(timezone.utc)
    db.commit()
    data["warnings"] = []
    data["normalised_input"] = ""
    data["cached"] = True
    return data
