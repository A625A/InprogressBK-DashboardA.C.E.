from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.polizas import Poliza, PolizaItem
from app.schemas.polizas import PolizaCreate


def correlativo_exists(session: Session, correlativo: int) -> bool:
    return session.scalar(select(Poliza.id).where(Poliza.correlativo == correlativo)) is not None


def add(session: Session, payload: PolizaCreate) -> Poliza:
    poliza = Poliza(
        **payload.model_dump(exclude={"items"}),
        items=[PolizaItem(**item.model_dump()) for item in payload.items],
    )
    session.add(poliza)
    session.flush()
    return poliza


def detail(session: Session, poliza_id: int) -> Poliza | None:
    return session.scalar(
        select(Poliza).where(Poliza.id == poliza_id).options(selectinload(Poliza.items))
    )
