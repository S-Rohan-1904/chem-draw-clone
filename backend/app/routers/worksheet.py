from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from .. import ratelimit, worksheet
from ..chem import ChemError

router = APIRouter(prefix="/api/worksheet", tags=["worksheet"])


class Item(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    smiles: str = Field(min_length=1, max_length=4000)


class WorksheetIn(BaseModel):
    title: str = Field(default="Worksheet", max_length=120)
    items: list[Item] = Field(min_length=1, max_length=64)
    show_names: bool = False
    answer_key: bool = True


@router.post("", dependencies=[Depends(ratelimit.check)])
def make_worksheet(body: WorksheetIn):
    try:
        pdf = worksheet.build_pdf(body.title, [i.model_dump() for i in body.items], body.show_names, body.answer_key)
    except ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="worksheet.pdf"'})
