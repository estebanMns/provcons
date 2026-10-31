import enum
from sqlalchemy import Float, String, Enum, ForeignKey
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

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderItem.id",
    )

    def can_be_cancelled(self) -> bool:
        return self.status in (OrderStatus.pendiente, OrderStatus.confirmada)

    def confirm(self, payment_terms: PaymentTerms | None = None) -> None:
        if self.status != OrderStatus.pendiente:
            raise ValueError(f"No se puede confirmar una orden en estado {self.status.value}")
        self.status = OrderStatus.confirmada
        if payment_terms is not None:
            self.payment_terms = payment_terms

    def advance(self) -> None:
        """Confirmada -> en tránsito -> entregada (lo hace el proveedor)."""
        next_status = _PROVIDER_NEXT_STATUS.get(self.status)
        if next_status is None:
            raise ValueError(f"Una orden en estado {self.status.value} no puede avanzar")
        self.status = next_status

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
