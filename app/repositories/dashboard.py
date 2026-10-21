from sqlalchemy import func, select
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
