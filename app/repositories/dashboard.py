from sqlalchemy import func, select
from sqlalchemy.orm import Session

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
