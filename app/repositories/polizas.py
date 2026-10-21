from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.polizas import Poliza, PolizaItem
from app.schemas.polizas import PolizaCreate, PolizaFilters


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


def list_page(session: Session, filters: PolizaFilters):
    conditions = []
    for name in ("correlativo", "aduana_id", "tipo_regimen_id"):
        value = getattr(filters, name)
        if value is not None:
            conditions.append(getattr(Poliza, name) == value)
    if filters.fecha_desde is not None:
        conditions.append(Poliza.fecha_declaracion >= filters.fecha_desde)
    if filters.fecha_hasta is not None:
        conditions.append(Poliza.fecha_declaracion <= filters.fecha_hasta)
    item_conditions = []
    for name in ("pais_id", "sac_id"):
        value = getattr(filters, name)
        if value is not None:
            item_conditions.append(getattr(PolizaItem, name) == value)
    if item_conditions:
        conditions.append(
            select(PolizaItem.id)
            .where(PolizaItem.poliza_id == Poliza.id, *item_conditions)
            .exists()
        )
    total = session.scalar(select(func.count()).select_from(Poliza).where(*conditions))
    rows = session.scalars(
        select(Poliza)
        .where(*conditions)
        .order_by(Poliza.id)
        .limit(filters.page_size)
        .offset((filters.page - 1) * filters.page_size)
    ).all()
    return rows, total
