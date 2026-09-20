from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import cache, chem, ratelimit, suggest
from ..db import NameCache, get_db

router = APIRouter(prefix="/api/molecule", tags=["molecule"])


class MoleculeIn(BaseModel):
    input: str = Field(min_length=1, max_length=200_000)


class HighlightIn(BaseModel):
    smiles: str = Field(min_length=1, max_length=4000)
    atoms: list[int] = Field(max_length=500)
    colour: str = Field(default="#2563eb", pattern=r"^#[0-9a-fA-F]{6}$")


class PngIn(BaseModel):
    smiles: str = Field(min_length=1, max_length=4000)
    width: int = Field(default=1200, ge=200, le=4000)


def _known_from_cache(db: Session) -> list[str]:
    rows = db.scalars(select(NameCache.normalised).where(NameCache.source == "iupac")).all()
    return [r for r in rows if r]


def _error_response(text: str, err: chem.ChemError, db: Session) -> JSONResponse:
    diag = suggest.diagnose(chem.normalise_name(text), err.opsin_error, _known_from_cache(db))
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": diag.reason if err.opsin_error else str(err),
            "input": chem.normalise_name(text),
            "highlight": list(diag.highlight) if diag.highlight else None,
            "suggestions": diag.suggestions,
        },
    )


@router.post("", dependencies=[Depends(ratelimit.check)])
def molecule(body: MoleculeIn, db: Session = Depends(get_db)):
    try:
        data, cached = cache.get_or_build(db, body.input)
    except chem.ChemError as e:
        return _error_response(body.input, e, db)
    data["cached"] = cached
    return data


@router.get("/by-key/{inchikey}")
def molecule_by_key(inchikey: str, db: Session = Depends(get_db)):
    data = cache.get_by_inchikey(db, inchikey.strip().upper())
    if data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No molecule with that key has been built here yet.")
    return data


@router.post("/check")
def check(body: MoleculeIn, db: Session = Depends(get_db)):
    """Parse-only validity check for live feedback while typing."""
    key = cache.normalise(body.input)
    row = db.get(NameCache, key)
    if row is not None:
        return {"ok": True, "warnings": [row.warning] if row.warning else [], "source": row.source}
    try:
        r = chem.resolve_full(body.input)
    except chem.ChemError as e:
        diag = suggest.diagnose(chem.normalise_name(body.input), e.opsin_error, [])
        return {"ok": False, "reason": diag.reason, "highlight": list(diag.highlight) if diag.highlight else None}
    return {"ok": True, "warnings": r.warnings, "source": r.source}


@router.get("/suggest")
def suggest_names(q: str = Query(min_length=1, max_length=200), db: Session = Depends(get_db)):
    return {"names": suggest.autocomplete(q, _known_from_cache(db))}


@router.post("/highlight")
def molecule_highlight(body: HighlightIn):
    try:
        mol = chem.mol_from_smiles(body.smiles)
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return {"svg": chem.render_svg_highlight(mol, body.atoms, body.colour)}


@router.post("/png", dependencies=[Depends(ratelimit.check)])
def molecule_png(body: PngIn):
    try:
        mol = chem.mol_from_smiles(body.smiles)
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    png = chem.render_png(mol, width=body.width, height=int(body.width * 0.75))
    return Response(content=png, media_type="image/png")
