from sqlalchemy.orm import Session

from app.repositories import dashboard
from app.schemas.dashboard import TopFive, Totals


def totals(session: Session) -> Totals:
    return Totals.model_validate(dashboard.totals(session))


def top_five(session: Session) -> TopFive:
    return TopFive(
        paises=dashboard.top_countries(session), productos=dashboard.top_products(session)
    )
