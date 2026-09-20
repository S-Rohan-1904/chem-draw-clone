from fastapi import APIRouter, Depends, HTTPException, Query, status

from .. import isomers, ratelimit
from ..chem import ChemError

router = APIRouter(prefix="/api/isomers", tags=["isomers"])


@router.get("", dependencies=[Depends(ratelimit.check)])
def list_isomers(formula: str = Query(min_length=1, max_length=30)):
    try:
        return isomers.enumerate_isomers(formula)
    except ChemError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
