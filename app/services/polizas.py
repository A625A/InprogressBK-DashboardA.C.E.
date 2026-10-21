from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.dimensions import Aduana, Pais, Sac, TipoRegimen, TipoUnidadMedida
from app.repositories import polizas
from app.repositories.dimensions import missing_ids
from app.schemas.polizas import PolizaCreate, PolizaDetail, PolizaFilters, PolizaPage


def create(session: Session, payload: PolizaCreate) -> PolizaDetail:
    try:
        with session.begin():
            if polizas.correlativo_exists(session, payload.correlativo):
                raise HTTPException(409, "El correlativo ya existe")
            references = [
                (Aduana, {payload.aduana_id}),
                (TipoRegimen, {payload.tipo_regimen_id}),
                (Sac, {item.sac_id for item in payload.items}),
                (Pais, {item.pais_id for item in payload.items}),
                (TipoUnidadMedida, {item.tipo_unidad_medida_id for item in payload.items}),
            ]
            for model, identifiers in references:
                if missing_ids(session, model, identifiers):
                    raise HTTPException(422, f"Referencia inexistente en {model.__tablename__}")
            result = PolizaDetail.model_validate(polizas.add(session, payload))
        return result
    except IntegrityError:
        # Includes uniqueness/FK races; the transaction context already rolled back.
        raise HTTPException(409, "Conflicto de integridad al guardar la póliza") from None


def detail(session: Session, poliza_id: int) -> PolizaDetail:
    poliza = polizas.detail(session, poliza_id)
    if poliza is None:
        raise HTTPException(404, "Póliza no encontrada")
    return PolizaDetail.model_validate(poliza)


def list_page(session: Session, filters: PolizaFilters) -> PolizaPage:
    rows, total = polizas.list_page(session, filters)
    return PolizaPage(items=rows, total=total, page=filters.page, page_size=filters.page_size)
