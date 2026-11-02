import re

from sqlalchemy import Boolean, String, Float, ForeignKey, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base
from app.db.mixins import TimestampMixin

# Códigos que genera la app cuando el archivo no trae uno: P-0001, P-0002...
AUTO_SKU = re.compile(r"^P-(\d+)$")


def clean_sku(value) -> str | None:
    """Código tal como se compara: sin espacios sobrantes y en mayúsculas."""
    text = re.sub(r"\s+", " ", str(value or "")).strip().upper()
    return text[:60] or None


class ProviderInventoryItem(Base, TimestampMixin):
    __tablename__ = "provider_inventory"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))

    # Código del producto, único por proveedor. Si el archivo trae uno se usa
    # ese; si no, la app genera P-000N. Al volver a subir un archivo, las filas
    # con un código que ya existe suman a ese producto en vez de duplicarlo.
    sku: Mapped[str] = mapped_column(String(60))
    material_name: Mapped[str] = mapped_column(String(200))
    unit: Mapped[str] = mapped_column(String(20))
    unit_price: Mapped[float] = mapped_column(Float)
    quantity_available: Mapped[float] = mapped_column(Float, default=0)
    # Eliminar un producto lo apaga: las comparaciones y órdenes viejas lo
    # siguen referenciando, pero ya no aparece en el inventario ni en ofertas
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    specs: Mapped[dict] = mapped_column(JSONB, default=dict)
    source_document_url: Mapped[str] = mapped_column(String(500), nullable=True)

    def is_in_stock(self) -> bool:
        return self.quantity_available > 0

    def update_price(self, new_price: float) -> None:
        if new_price <= 0:
            raise ValueError("El precio debe ser mayor a cero")
        self.unit_price = new_price

    def add_stock(self, quantity: float) -> None:
        """Entrada de mercancía (por ejemplo, al volver a subir el archivo)."""
        if quantity < 0:
            raise ValueError("La cantidad a sumar no puede ser negativa")
        self.quantity_available = (self.quantity_available or 0) + quantity

    def take_stock(self, quantity: float) -> None:
        """Salida por una venta confirmada. No deja el stock en negativo."""
        if quantity > (self.quantity_available or 0):
            raise ValueError(f"Stock insuficiente de {self.material_name}")
        self.quantity_available = (self.quantity_available or 0) - quantity

    def return_stock(self, quantity: float) -> None:
        """Devuelve lo de una venta que se canceló o se rechazó."""
        self.quantity_available = (self.quantity_available or 0) + quantity
