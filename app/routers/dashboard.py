from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.cache import DashboardCache, get_dashboard_cache
from app.core.security import current_user
from app.db.session import get_session
from app.schemas.dashboard import MonthlyValues, TopFive, Totals
from app.services import dashboard

router = APIRouter(
    prefix="/dashboard/kpis", tags=["Dashboard"], dependencies=[Depends(current_user)]
)
DB = Annotated[Session, Depends(get_session)]
Cache = Annotated[DashboardCache, Depends(get_dashboard_cache)]


@router.get("/totals", response_model=Totals)
def totals(session: DB, cache: Cache):
    return cache.get_or_load("totals", lambda: dashboard.totals(session))


@router.get("/top-5", response_model=TopFive)
def top_five(session: DB, cache: Cache):
    return cache.get_or_load("top-5", lambda: dashboard.top_five(session))


@router.get("/valor-por-mes", response_model=MonthlyValues)
def monthly_values(year: Annotated[int, Query(ge=1, le=9999)], session: DB, cache: Cache):
    return cache.get_or_load(
        "valor-por-mes", lambda: dashboard.monthly_values(session, year), year=year
    )
