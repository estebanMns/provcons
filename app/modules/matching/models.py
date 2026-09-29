import enum
from sqlalchemy import String, Float, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base
from app.db.mixins import TimestampMixin


class QuotationStatus(str, enum.Enum):
    abierta = "abierta"
    en_negociacion = "en_negociacion"
    cerrada = "cerrada"
    cancelada = "cancelada"


class Quotation(Base, TimestampMixin):
    __tablename__ = "quotations"

    id: Mapped[int] = mapped_column(primary_key=True)
    constructora_org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[QuotationStatus] = mapped_column(Enum(QuotationStatus), default=QuotationStatus.abierta)

    items: Mapped[list["QuotationItem"]] = relationship(back_populates="quotation")

    def close(self) -> None:
        if self.status != QuotationStatus.en_negociacion:
            raise ValueError("Solo se puede cerrar una cotización en negociación")
        self.status = QuotationStatus.cerrada


class QuotationItem(Base, TimestampMixin):
    __tablename__ = "quotation_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    quotation_id: Mapped[int] = mapped_column(ForeignKey("quotations.id"))
    material_name: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20))
    specs: Mapped[dict] = mapped_column(JSONB, default=dict)

    quotation: Mapped["Quotation"] = relationship(back_populates="items")


class Match(Base, TimestampMixin):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    quotation_item_id: Mapped[int] = mapped_column(ForeignKey("quotation_items.id"))
    provider_inventory_id: Mapped[int] = mapped_column(ForeignKey("provider_inventory.id"))
    provider_org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    score: Mapped[float] = mapped_column(Float)
    criteria_breakdown: Mapped[dict] = mapped_column(JSONB, default=dict)

    def is_strong_match(self, threshold: float = 0.7) -> bool:
        return self.score >= threshold