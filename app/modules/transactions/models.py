import enum
from sqlalchemy import Float, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base
from app.db.mixins import TimestampMixin


class PaymentTerms(str, enum.Enum):
    contado = "contado"
    cuotas = "cuotas"


class OrderStatus(str, enum.Enum):
    pendiente = "pendiente"
    confirmada = "confirmada"
    en_transito = "en_transito"
    entregada = "entregada"
    cancelada = "cancelada"


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    constructora_org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    provider_org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))

    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.pendiente)
    payment_terms: Mapped[PaymentTerms] = mapped_column(Enum(PaymentTerms), nullable=True)
    logistics_cost: Mapped[float] = mapped_column(Float, nullable=True)
    predicted_negotiation: Mapped[dict] = mapped_column(JSONB, default=dict)

    def can_be_cancelled(self) -> bool:
        return self.status in (OrderStatus.pendiente, OrderStatus.confirmada)

    def confirm(self, payment_terms: PaymentTerms) -> None:
        if self.status != OrderStatus.pendiente:
            raise ValueError(f"No se puede confirmar una orden en estado {self.status}")
        self.status = OrderStatus.confirmada
        self.payment_terms = payment_terms

    def total_cost_estimate(self) -> float:
        base = self.predicted_negotiation.get("estimated_price", 0)
        return base + (self.logistics_cost or 0)