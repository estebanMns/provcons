from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.modules.transactions.models import OrderStatus, PaymentTerms


class OrderCreate(BaseModel):
    """La constructora elige ofertas de una comparación (matches). Se crea una
    orden por cada proveedor involucrado. La organización compradora sale de la
    sesión, nunca del cuerpo de la petición."""
    quotation_id: int
    match_ids: list[int] = Field(min_length=1)
    payment_terms: PaymentTerms = PaymentTerms.contado


class OrderConfirmRequest(BaseModel):
    payment_terms: PaymentTerms | None = None


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    requested_material: str
    material_name: str
    quantity: float
    unit: str
    unit_price: float | None
    subtotal: float | None


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    quotation_id: int | None
    quotation_title: str | None = None
    constructora_org_id: int
    constructora_name: str | None = None
    provider_org_id: int
    provider_name: str | None = None
    status: OrderStatus
    payment_terms: PaymentTerms | None
    total_amount: float | None
    items: list[OrderItemOut]
    created_at: datetime
    updated_at: datetime
