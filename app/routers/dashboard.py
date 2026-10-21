from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import current_user
from app.db.session import get_session
from app.schemas.dashboard import TopFive, Totals
from app.services import dashboard

router = APIRouter(
    prefix="/dashboard/kpis", tags=["Dashboard"], dependencies=[Depends(current_user)]
)
DB = Annotated[Session, Depends(get_session)]


@router.get("/totals", response_model=Totals)
def totals(session: DB):
    return dashboard.totals(session)


@router.get("/top-5", response_model=TopFive)
def top_five(session: DB):
    return dashboard.top_five(session)
