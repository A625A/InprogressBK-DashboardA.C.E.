from sqlalchemy.orm import Session

from app.repositories import dashboard
from app.schemas.dashboard import Totals


def totals(session: Session) -> Totals:
    return Totals.model_validate(dashboard.totals(session))
