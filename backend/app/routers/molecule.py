from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import align as _align, cache, chem, nameparse, projections, ratelimit, reaction, resolver, resonance, stereo_explain, suggest
from ..db import NameCache, NameLookup, get_db

router = APIRouter(prefix="/api/molecule", tags=["molecule"])


class MoleculeIn(BaseModel):
    input: str = Field(min_length=1, max_length=200_000)


class HighlightIn(BaseModel):
    smiles: str = Field(min_length=1, max_length=4000)
    atoms: list[int] = Field(max_length=500)
    colour: str = Field(default="#2563eb", pattern=r"^#[0-9a-fA-F]{6}$")


class StereoIn(BaseModel):
    smiles: str = Field(min_length=1, max_length=4000)
    atom_idx: int | None = None
    bond_idx: int | None = None


class VariantIn(BaseModel):
    smiles: str = Field(min_length=1, max_length=4000)
    op: str = Field(pattern=r"^(mirror|invert)$")
    atom_idx: int | None = None


class BatchIn(BaseModel):
    inputs: list[str] = Field(min_length=1, max_length=200)


class ProjectionIn(BaseModel):
    smiles: str = Field(min_length=1, max_length=4000)
    front: int | None = None
    back: int | None = None
    rotate: float = 0.0
    ring: list[int] | None = None
    flipped: bool = False


class PngIn(BaseModel):
    smiles: str = Field(min_length=1, max_length=4000)
    width: int = Field(default=1200, ge=200, le=4000)


def _known_from_cache(db: Session) -> list[str]:
    rows = db.scalars(select(NameCache.normalised).where(NameCache.source.in_(("iupac", *resolver.SOURCES)))).all()
    return [r for r in rows if r]


def _error_response(text: str, err: chem.ChemError, db: Session) -> JSONResponse:
    if "took too long" in str(err):
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(err), "input": text, "highlight": None, "suggestions": []})
    diag = suggest.diagnose(chem.normalise_name(text), err.opsin_error, _known_from_cache(db))
    detail = diag.reason if err.opsin_error else str(err)
    if err.opsin_error and resolver.enabled():
        detail += " It is not in PubChem or NCI CACTUS either; paste a SMILES or draw it."
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": detail,
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


@router.get("/name/{inchikey}")
def name_lookup(inchikey: str, db: Session = Depends(get_db)):
    """Names for a structure, from PubChem, cached. Misses are retried after a day."""
    from datetime import datetime, timedelta, timezone

    key = inchikey.strip().upper()
    row = db.get(NameLookup, key)
    fresh = row is not None and (row.found or (datetime.now(timezone.utc) - row.created_at.replace(tzinfo=timezone.utc)) < timedelta(days=1))
    if not fresh:
        hit = resolver.name_for_inchikey(key)
        if row is None:
            row = NameLookup(inchikey=key)
            db.add(row)
        row.found = hit is not None
        row.iupac = (hit or {}).get("iupac", "")
        row.title = (hit or {}).get("title", "")
        row.cid = (hit or {}).get("cid")
        row.created_at = datetime.now(timezone.utc)
        db.commit()
    if not row.found:
        return {"found": False}
    return {"found": True, "iupac": row.iupac, "title": row.title, "cid": row.cid, "source": "PubChem"}


class SmilesIn(BaseModel):
    smiles: str = Field(min_length=1, max_length=4000)


@router.post("/charges")
def molecule_charges(body: SmilesIn, db: Session = Depends(get_db)):
    """Gasteiger partial charges per atom, in the 3D mol block's atom order (H included)."""
    from rdkit import Chem
    from rdkit.Chem import AllChem

    try:
        mb = _molblock(db, body.smiles)
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    mol = Chem.MolFromMolBlock(mb, removeHs=False)
    AllChem.ComputeGasteigerCharges(mol)
    charges = []
    for a in mol.GetAtoms():
        try:
            q = float(a.GetProp("_GasteigerCharge"))
        except KeyError:
            q = 0.0
        charges.append(0.0 if q != q else round(q, 4))  # NaN guard
    return {"charges": charges, "min": min(charges), "max": max(charges)}


class BreakdownIn(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    smiles: str = Field(min_length=1, max_length=4000)


@router.post("/breakdown")
def molecule_breakdown(body: BreakdownIn):
    return nameparse.breakdown(chem.normalise_name(body.name), body.smiles)


class ReactionIn(BaseModel):
    text: str = Field(min_length=3, max_length=4000)


@router.post("/reaction", dependencies=[Depends(ratelimit.check)])
def molecule_reaction(body: ReactionIn):
    try:
        return reaction.parse_reaction(body.text)
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


class AlignIn(BaseModel):
    smiles_a: str = Field(min_length=1, max_length=4000)
    smiles_b: str = Field(min_length=1, max_length=4000)


@router.post("/align", dependencies=[Depends(ratelimit.check)])
def molecule_align(body: AlignIn, db: Session = Depends(get_db)):
    try:
        return _align.align(_molblock(db, body.smiles_a), _molblock(db, body.smiles_b))
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/resonance")
def molecule_resonance(body: SmilesIn):
    try:
        return {"forms": resonance.resonance_svgs(body.smiles)}
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/check")
def check(body: MoleculeIn, db: Session = Depends(get_db)):
    """Parse-only validity check for live feedback while typing. No database
    lookup here: that only runs on build, so typing never hits the network."""
    key = cache.normalise(body.input)
    row = db.get(NameCache, key)
    if row is not None:
        # The "taken from PubChem" note is informational; it is shown on build, not as a typing warning.
        warnings = [row.warning] if row.warning and row.source not in resolver.SOURCES else []
        return {"ok": True, "warnings": warnings, "source": row.source}
    try:
        r = chem.resolve_full(body.input, lookup=False)
    except chem.ChemError as e:
        diag = suggest.diagnose(chem.normalise_name(body.input), e.opsin_error, [])
        return {"ok": False, "reason": diag.reason, "highlight": list(diag.highlight) if diag.highlight else None, "lookup": resolver.enabled()}
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


@router.post("/stereo")
def molecule_stereo(body: StereoIn):
    try:
        if body.atom_idx is not None:
            return stereo_explain.explain_centre(body.smiles, body.atom_idx)
        if body.bond_idx is not None:
            return stereo_explain.explain_double_bond(body.smiles, body.bond_idx)
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    raise HTTPException(status.HTTP_400_BAD_REQUEST, "Give atom_idx or bond_idx.")


@router.post("/variant", dependencies=[Depends(ratelimit.check)])
def molecule_variant(body: VariantIn, db: Session = Depends(get_db)):
    """Build the mirror image or a single-centre inversion of a molecule."""
    try:
        smiles = chem.variant_smiles(body.smiles, body.op, body.atom_idx)
        data, cached = cache.get_or_build(db, smiles)
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    data["cached"] = cached
    data["source"] = "smiles"
    return data


@router.post("/batch", dependencies=[Depends(ratelimit.check)])
def molecule_batch(body: BatchIn):
    """Parse-only table for many names: no depiction or 3D, so it stays quick."""
    from rdkit import Chem
    from rdkit.Chem import Descriptors, rdMolDescriptors

    rows = []
    for raw in body.inputs:
        text = raw.strip()
        if not text:
            continue
        try:
            resolved = chem.resolve_full(text)
            smiles = chem.canonical_smiles(resolved.smiles)
            mol = chem.mol_from_smiles(smiles)
            stereo = chem._stereo_report(mol)
            rows.append({
                "input": text,
                "ok": True,
                "smiles": smiles,
                "formula": rdMolDescriptors.CalcMolFormula(mol),
                "mw": round(Descriptors.MolWt(mol), 2),
                "inchikey": Chem.MolToInchiKey(mol),
                "stereo": " ".join([f"{c.symbol}{c.atom_idx + 1}:{c.label}" for c in stereo.centers] + [f"C=C:{b.label}" for b in stereo.double_bonds]),
                "unspecified": stereo.unspecified,
                "warning": " ".join(resolved.warnings),
                "error": "",
            })
        except chem.ChemError as e:
            diag = suggest.diagnose(chem.normalise_name(text), e.opsin_error, [])
            rows.append({"input": text, "ok": False, "error": diag.reason, "suggestions": diag.suggestions})
    return {"rows": rows}


def _molblock(db: Session, smiles: str) -> str:
    data, _ = cache.get_or_build(db, smiles)
    return data["molblock"]


@router.post("/projections")
def projections_available(body: ProjectionIn, db: Session = Depends(get_db)):
    """Which Newman bonds and chair rings a molecule offers."""
    try:
        mb = _molblock(db, body.smiles)
        return {"newman_bonds": projections.newman_bonds(mb), "chair_rings": projections.chair_rings(mb)}
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/newman")
def newman(body: ProjectionIn, db: Session = Depends(get_db)):
    if body.front is None or body.back is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "front and back atoms required")
    try:
        return projections.newman_svg(_molblock(db, body.smiles), body.front, body.back, body.rotate)
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/chair")
def chair(body: ProjectionIn, db: Session = Depends(get_db)):
    if not body.ring:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ring required")
    try:
        analysis = projections.chair_analysis(_molblock(db, body.smiles), body.ring)
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    out = {k: v for k, v in analysis.items() if not k.startswith("_")}
    out["svg"] = projections.chair_svg(analysis, flipped=False)
    out["svg_flipped"] = projections.chair_svg(analysis, flipped=True)
    return out


@router.post("/png", dependencies=[Depends(ratelimit.check)])
def molecule_png(body: PngIn):
    try:
        mol = chem.mol_from_smiles(body.smiles)
    except chem.ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    png = chem.render_png(mol, width=body.width, height=int(body.width * 0.75))
    return Response(content=png, media_type="image/png")
