from pydantic import BaseModel


class Totals(BaseModel):
    total_polizas: int
    valor_importado_total: float
