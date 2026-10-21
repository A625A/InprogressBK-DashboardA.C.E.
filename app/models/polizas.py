from datetime import date

from sqlalchemy import BigInteger, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Poliza(Base):
    __tablename__ = "polizas"

    id: Mapped[int] = mapped_column(primary_key=True)
    correlativo: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    fecha_declaracion: Mapped[date | None]
    tipo_cambio_dolar: Mapped[float | None]
    aduana_id: Mapped[int | None] = mapped_column(ForeignKey("aduanas.id"))
    tipo_regimen_id: Mapped[int | None] = mapped_column(ForeignKey("tipo_regimen.id"))
    items: Mapped[list["PolizaItem"]] = relationship(
        back_populates="poliza",
        cascade="all, delete-orphan",
        lazy="raise",
        order_by="PolizaItem.id",
    )


class PolizaItem(Base):
    __tablename__ = "poliza_items"
    __table_args__ = (
        Index("idx_poliza_items_poliza_id", "poliza_id"),
        Index("idx_poliza_items_sac_id", "sac_id"),
        Index("idx_poliza_items_pais_id", "pais_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    poliza_id: Mapped[int | None] = mapped_column(ForeignKey("polizas.id", ondelete="CASCADE"))
    sac_id: Mapped[int | None] = mapped_column(ForeignKey("sac.id"))
    pais_id: Mapped[int | None] = mapped_column(ForeignKey("pais.id"))
    tipo_unidad_medida_id: Mapped[int | None] = mapped_column(ForeignKey("tipo_unidad_medida.id"))
    cantidad_fraccion: Mapped[float | None]
    tasa_dai: Mapped[float | None]
    valor_dai: Mapped[float | None]
    valor_cif_uds: Mapped[float | None]
    tasa_cif_cantidad_fraccion: Mapped[float | None]
    poliza: Mapped[Poliza | None] = relationship(back_populates="items")
