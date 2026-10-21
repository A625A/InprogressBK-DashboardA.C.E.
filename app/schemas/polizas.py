from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

Identifier = Annotated[int, Field(gt=0, le=2**63 - 1)]
Correlativo = Annotated[int, Field(ge=-(2**63), le=2**63 - 1)]


class ItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sac_id: Identifier
    pais_id: Identifier
    tipo_unidad_medida_id: Identifier
    cantidad_fraccion: FiniteFloat
    tasa_dai: FiniteFloat
    valor_dai: FiniteFloat
    valor_cif_uds: FiniteFloat
    tasa_cif_cantidad_fraccion: FiniteFloat


class PolizaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correlativo: Correlativo
    fecha_declaracion: date
    tipo_cambio_dolar: FiniteFloat
    aduana_id: Identifier
    tipo_regimen_id: Identifier
    items: list[ItemCreate] = Field(min_length=1)


class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    poliza_id: int | None
    sac_id: int | None
    pais_id: int | None
    tipo_unidad_medida_id: int | None
    cantidad_fraccion: float | None
    tasa_dai: float | None
    valor_dai: float | None
    valor_cif_uds: float | None
    tasa_cif_cantidad_fraccion: float | None


class PolizaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    correlativo: int | None
    fecha_declaracion: date | None
    tipo_cambio_dolar: float | None
    aduana_id: int | None
    tipo_regimen_id: int | None


class PolizaDetail(PolizaRead):
    items: list[ItemRead]


class PolizaFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1, le=2**63 - 1)
    page_size: int = Field(default=20, ge=1, le=100)
    correlativo: Correlativo | None = None
    fecha_desde: date | None = None
    fecha_hasta: date | None = None
    aduana_id: Identifier | None = None
    tipo_regimen_id: Identifier | None = None
    pais_id: Identifier | None = None
    sac_id: Identifier | None = None

    @model_validator(mode="after")
    def validate_ranges(self):
        if self.fecha_desde and self.fecha_hasta and self.fecha_desde > self.fecha_hasta:
            raise ValueError("fecha_desde debe ser anterior o igual a fecha_hasta")
        if (self.page - 1) * self.page_size > 2**63 - 1:
            raise ValueError("El desplazamiento de página excede el rango admitido")
        return self


class PolizaPage(BaseModel):
    items: list[PolizaRead]
    total: int
    page: int
    page_size: int
