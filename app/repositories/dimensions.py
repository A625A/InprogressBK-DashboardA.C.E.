from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dimensions import NamedDimension


def list_dimension(session: Session, model: type[NamedDimension]) -> Sequence[NamedDimension]:
    return session.scalars(select(model).order_by(model.id)).all()


def missing_ids(session: Session, model, identifiers: set[int]) -> set[int]:
    if not identifiers:
        return set()
    existing = set(session.scalars(select(model.id).where(model.id.in_(identifiers))))
    return identifiers - existing
