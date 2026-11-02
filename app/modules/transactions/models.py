import enum
import math
from datetime import datetime, timedelta, timezone
from sqlalchemy import DateTime, Float, Integer, String, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
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


# Transiciones que puede hacer el proveedor después de confirmar
_PROVIDER_NEXT_STATUS = {
    OrderStatus.confirmada: OrderStatus.en_transito,
    OrderStatus.en_transito: OrderStatus.entregada,
}


class Order(Base, TimestampMixin):
    """Pedido de una constructora a UN proveedor. Puede tener varios
    materiales (OrderItem); si la constructora compra a varios proveedores se
    crea una orden por cada uno."""
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Solo las órdenes antiguas (de un único material) usan match_id; las
    # nuevas guardan sus materiales en items.
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"), nullable=True)
    quotation_id: Mapped[int | None] = mapped_column(ForeignKey("quotations.id"), nullable=True)
    constructora_org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    provider_org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))

    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.pendiente)
    payment_terms: Mapped[PaymentTerms] = mapped_column(Enum(PaymentTerms), nullable=True)
    total_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    logistics_cost: Mapped[float] = mapped_column(Float, nullable=True)
    predicted_negotiation: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Condiciones acordadas al confirmar (null en órdenes anteriores)
    installments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_rate_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    installment_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    financed_total: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivery_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    promised_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Condiciones que el proveedor propuso y la constructora aún no responde.
    # La orden sigue pendiente mientras tanto.
    proposal: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderItem.id",
    )

    def can_be_cancelled(self) -> bool:
        return self.status in (OrderStatus.pendiente, OrderStatus.confirmada)

    def _require_open_for_provider(self) -> None:
        if self.status != OrderStatus.pendiente:
            raise ValueError(f"No se puede aceptar una orden en estado {self.status.value}")
        if self.proposal:
            raise ValueError("Ya enviaste una propuesta: espera la respuesta de la constructora")

    def requires_client_approval(self, installments: int) -> bool:
        """Confirmar de una vez solo si el proveedor deja el pago como lo pidió
        la constructora (de contado). Cualquier cuota es una condición nueva."""
        return installments > 1 or self.payment_terms == PaymentTerms.cuotas

    def apply_terms(self, terms: dict, now: datetime) -> None:
        """Deja la orden confirmada con estas condiciones."""
        if self.status != OrderStatus.pendiente:
            raise ValueError(f"No se puede confirmar una orden en estado {self.status.value}")
        self.installments = terms["installments"]
        self.monthly_rate_pct = terms["monthly_rate_pct"]
        self.installment_amount = terms["installment_amount"]
        self.financed_total = terms["financed_total"]
        self.delivery_days = terms["delivery_days"]
        self.payment_terms = PaymentTerms.contado if self.installments == 1 else PaymentTerms.cuotas
        self.promised_delivery_at = now + timedelta(days=self.delivery_days)
        self.proposal = None
        self.status = OrderStatus.confirmada

    def confirm_directly(self, terms: dict, now: datetime) -> None:
        self._require_open_for_provider()
        self.apply_terms(terms, now)

    def propose(self, terms: dict, now: datetime) -> None:
        self._require_open_for_provider()
        self.proposal = {**terms, "proposed_at": now.isoformat()}

    def accept_proposal(self, now: datetime) -> None:
        if not self.proposal:
            raise ValueError("Esta orden no tiene una propuesta por responder")
        self.apply_terms(self.proposal, now)

    def reject_proposal(self) -> None:
        if not self.proposal:
            raise ValueError("Esta orden no tiene una propuesta por responder")
        self.proposal = None

    def advance(self, now: datetime | None = None) -> None:
        """Confirmada -> en tránsito -> entregada (lo hace el proveedor)."""
        next_status = _PROVIDER_NEXT_STATUS.get(self.status)
        if next_status is None:
            raise ValueError(f"Una orden en estado {self.status.value} no puede avanzar")
        self.status = next_status
        if next_status == OrderStatus.entregada:
            self.delivered_at = now or datetime.now(timezone.utc)

    def delay_days(self, now: datetime) -> int | None:
        """Días completos de atraso frente a la fecha prometida (0 = a tiempo).
        Si ya se entregó, cuenta hasta la entrega."""
        if self.promised_delivery_at is None or self.status == OrderStatus.cancelada:
            return None
        end = self.delivered_at or now
        return max(0, math.floor((end - self.promised_delivery_at).total_seconds() / 86400))

    def total_cost_estimate(self) -> float:
        base = self.total_amount or self.predicted_negotiation.get("estimated_price", 0)
        return base + (self.logistics_cost or 0)


class OrderItem(Base, TimestampMixin):
    """Un material de la orden. Guarda una copia del nombre y del precio al
    momento de comprar: si el proveedor cambia su inventario después, la orden
    no cambia."""
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"), nullable=True)
    quotation_item_id: Mapped[int | None] = mapped_column(ForeignKey("quotation_items.id"), nullable=True)

    requested_material: Mapped[str] = mapped_column(String(200))  # lo que pidió la constructora
    material_name: Mapped[str] = mapped_column(String(200))       # lo que vende el proveedor
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20))
    unit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    subtotal: Mapped[float | None] = mapped_column(Float, nullable=True)

    order: Mapped["Order"] = relationship(back_populates="items")
