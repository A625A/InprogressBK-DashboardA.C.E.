from pydantic import BaseModel, ConfigDict


class DimensionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str | None
