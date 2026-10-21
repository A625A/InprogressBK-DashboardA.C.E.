from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import current_user
from app.db.session import get_session
from app.models.dimensions import Aduana, Pais, TipoRegimen
from app.repositories.dimensions import list_dimension
from app.schemas.dimensions import DimensionRead

router = APIRouter(prefix="/dimensions", tags=["Dimensiones"], dependencies=[Depends(current_user)])
DB = Annotated[Session, Depends(get_session)]


@router.get("/paises", response_model=list[DimensionRead])
def paises(session: DB):
    return list_dimension(session, Pais)


@router.get("/aduanas", response_model=list[DimensionRead])
def aduanas(session: DB):
    return list_dimension(session, Aduana)


@router.get("/tipos-regimen", response_model=list[DimensionRead])
def tipos_regimen(session: DB):
    return list_dimension(session, TipoRegimen)
