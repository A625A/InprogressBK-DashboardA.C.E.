from datetime import date

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.models.dimensions import Pais, Sac
from app.models.polizas import Poliza, PolizaItem


def totals(session: Session):
    statement = (
        select(
            func.count(Poliza.id.distinct()).label("total_polizas"),
            func.coalesce(func.sum(PolizaItem.valor_cif_uds), 0.0).label("valor_importado_total"),
        )
        .select_from(Poliza)
        .outerjoin(PolizaItem, PolizaItem.poliza_id == Poliza.id)
    )
    return session.execute(statement).mappings().one()


def top_countries(session: Session):
    value = func.coalesce(func.sum(PolizaItem.valor_cif_uds), 0.0).label("valor_importado")
    statement = (
        select(Pais.id, Pais.name, value)
        .join(PolizaItem, PolizaItem.pais_id == Pais.id)
        .join(Poliza, PolizaItem.poliza_id == Poliza.id)
        .group_by(Pais.id, Pais.name)
        .order_by(value.desc(), Pais.id)
        .limit(5)
    )
    return session.execute(statement).mappings().all()


def top_products(session: Session):
    value = func.coalesce(func.sum(PolizaItem.valor_cif_uds), 0.0).label("valor_importado")
    statement = (
        select(Sac.id, Sac.fraccion, Sac.descripcion, value)
        .join(PolizaItem, PolizaItem.sac_id == Sac.id)
        .join(Poliza, PolizaItem.poliza_id == Poliza.id)
        .group_by(Sac.id, Sac.fraccion, Sac.descripcion)
        .order_by(value.desc(), Sac.id)
        .limit(5)
    )
    return session.execute(statement).mappings().all()


def monthly_values(session: Session, year: int) -> dict[int, float]:
    month = extract("month", Poliza.fecha_declaracion).label("mes")
    value = func.coalesce(func.sum(PolizaItem.valor_cif_uds), 0.0).label("valor_importado")
    statement = (
        select(month, value)
        .select_from(Poliza)
        .join(PolizaItem, PolizaItem.poliza_id == Poliza.id)
        .where(
            Poliza.fecha_declaracion >= date(year, 1, 1),
            Poliza.fecha_declaracion <= date(year, 12, 31),
        )
        .group_by(month)
        .order_by(month)
    )
    # At most twelve aggregate rows leave the database.
    return {row.mes: row.valor_importado for row in session.execute(statement)}
