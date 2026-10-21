from collections.abc import Mapping

from sqlalchemy.orm import Session

from app.repositories import dashboard
from app.schemas.dashboard import MonthlyValues, MonthValue, TopFive, Totals


def totals(session: Session) -> Totals:
    return Totals.model_validate(dashboard.totals(session))


def top_five(session: Session) -> TopFive:
    return TopFive(
        paises=dashboard.top_countries(session), productos=dashboard.top_products(session)
    )


def complete_months(year: int, values: Mapping[int, float]) -> MonthlyValues:
    return MonthlyValues(
        year=year,
        meses=[
            MonthValue(mes=month, valor_importado=values.get(month, 0.0)) for month in range(1, 13)
        ],
    )


def monthly_values(session: Session, year: int) -> MonthlyValues:
    return complete_months(year, dashboard.monthly_values(session, year))
