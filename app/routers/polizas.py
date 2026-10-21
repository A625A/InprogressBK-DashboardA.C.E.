from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import current_user
from app.db.session import get_session
from app.schemas.polizas import Identifier, PolizaCreate, PolizaDetail
from app.services import polizas

router = APIRouter(prefix="/polizas", tags=["Pólizas"], dependencies=[Depends(current_user)])
DB = Annotated[Session, Depends(get_session)]


@router.post("", response_model=PolizaDetail, status_code=201)
def create(payload: PolizaCreate, session: DB):
    return polizas.create(session, payload)


@router.get("/{poliza_id}", response_model=PolizaDetail)
def detail(poliza_id: Identifier, session: DB):
    return polizas.detail(session, poliza_id)
