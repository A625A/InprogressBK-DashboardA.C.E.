from sqlalchemy import BigInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class NamedDimension(Base):
    __abstract__ = True
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(Text, unique=True)


class Pais(NamedDimension):
    __tablename__ = "pais"


class Aduana(NamedDimension):
    __tablename__ = "aduanas"


class TipoRegimen(NamedDimension):
    __tablename__ = "tipo_regimen"


class TipoUnidadMedida(NamedDimension):
    __tablename__ = "tipo_unidad_medida"


class Sac(Base):
    __tablename__ = "sac"
    id: Mapped[int] = mapped_column(primary_key=True)
    fraccion: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    descripcion: Mapped[str | None] = mapped_column(Text)
