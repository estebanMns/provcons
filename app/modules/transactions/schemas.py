from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.modules.transactions.models import OrderStatus, PaymentTerms


class OrderCreate(BaseModel):
    match_id: int
    constructora_org_id: int
    provider_org_id: int


class OrderConfirmRequest(BaseModel):
    payment_terms: PaymentTerms


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    match_id: int
    constructora_org_id: int
    provider_org_id: int
    status: OrderStatus
    payment_terms: PaymentTerms | None
    logistics_cost: float | None
    predicted_negotiation: dict
    created_at: datetime