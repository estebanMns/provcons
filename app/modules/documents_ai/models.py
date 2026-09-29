from sqlalchemy import String, Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base
from app.db.mixins import TimestampMixin


class ProviderInventoryItem(Base, TimestampMixin):
    __tablename__ = "provider_inventory"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))

    material_name: Mapped[str] = mapped_column(String(200))
    unit: Mapped[str] = mapped_column(String(20))
    unit_price: Mapped[float] = mapped_column(Float)
    quantity_available: Mapped[float] = mapped_column(Float, default=0)

    specs: Mapped[dict] = mapped_column(JSONB, default=dict)
    source_document_url: Mapped[str] = mapped_column(String(500), nullable=True)

    def is_in_stock(self) -> bool:
        return self.quantity_available > 0

    def update_price(self, new_price: float) -> None:
        if new_price <= 0:
            raise ValueError("El precio debe ser mayor a cero")
        self.unit_price = new_price