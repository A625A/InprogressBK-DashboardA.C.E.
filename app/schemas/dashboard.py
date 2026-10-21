from pydantic import BaseModel


class Totals(BaseModel):
    total_polizas: int
    valor_importado_total: float


class CountryValue(BaseModel):
    id: int
    name: str | None
    valor_importado: float


class ProductValue(BaseModel):
    id: int
    fraccion: int | None
    descripcion: str | None
    valor_importado: float


class TopFive(BaseModel):
    paises: list[CountryValue]
    productos: list[ProductValue]


class MonthValue(BaseModel):
    mes: int
    valor_importado: float


class MonthlyValues(BaseModel):
    year: int
    meses: list[MonthValue]
