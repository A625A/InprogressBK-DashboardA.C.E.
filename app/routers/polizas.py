from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.cache import DashboardCache, get_dashboard_cache
from app.core.security import current_user
from app.db.session import get_session
from app.schemas.polizas import Identifier, PolizaCreate, PolizaDetail, PolizaFilters, PolizaPage
from app.services import polizas

router = APIRouter(prefix="/polizas", tags=["Pólizas"], dependencies=[Depends(current_user)])
DB = Annotated[Session, Depends(get_session)]


@router.post("", response_model=PolizaDetail, status_code=201)
def create(
    payload: PolizaCreate,
    session: DB,
    cache: Annotated[DashboardCache, Depends(get_dashboard_cache)],
):
    return polizas.create(session, payload, cache)


@router.get("/{poliza_id}", response_model=PolizaDetail)
def detail(poliza_id: Identifier, session: DB):
    return polizas.detail(session, poliza_id)


@router.get("", response_model=PolizaPage)
def list_page(filters: Annotated[PolizaFilters, Query()], session: DB):
    return polizas.list_page(session, filters)
