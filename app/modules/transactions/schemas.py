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


class OrderTermsRequest(BaseModel):
    """Condiciones con las que el proveedor acepta la orden. El valor de la
    cuota lo calcula el backend, nunca se toma del navegador."""
    delivery_days: int = Field(ge=1, le=180)
    installments: int = Field(default=1, ge=1, le=12)
    monthly_rate_pct: float = Field(default=0, ge=0, le=10)
    note: str | None = Field(default=None, max_length=300)


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    requested_material: str
    material_name: str
    quantity: float
    unit: str
    unit_price: float | None
    subtotal: float | None


class ProposalOut(BaseModel):
    installments: int
    monthly_rate_pct: float
    installment_amount: float
    financed_total: float
    delivery_days: int
    note: str | None = None
    proposed_at: datetime


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
    installments: int | None = None
    monthly_rate_pct: float | None = None
    installment_amount: float | None = None
    financed_total: float | None = None
    delivery_days: int | None = None
    promised_delivery_at: datetime | None = None
    delivered_at: datetime | None = None
    delay_days: int | None = None
    proposal: ProposalOut | None = None
    created_at: datetime
    updated_at: datetime


class InstallmentOptionOut(BaseModel):
    installments: int
    verdict: str  # conveniente | con_riesgo | no_conveniente


class ClientHistoryOut(BaseModel):
    orders_delivered: int
    orders_cancelled_by_client: int
    open_orders: int
    total_purchased: float
    orders_with_you: int
    delivered_with_you: int
    months_on_platform: float


class CreditNarrativeOut(BaseModel):
    source: str  # ia | plantilla
    summary: str
    advice: str


class OrderEvaluationOut(BaseModel):
    """Lo que ve el proveedor antes de aceptar: cómo cumple la constructora y
    cuántas cuotas le conviene dar."""
    order_id: int
    constructora_name: str | None
    amount: float
    requested_payment_terms: PaymentTerms | None
    score: float
    confidence: str
    max_installments: int
    reasons: list[str]
    history: ClientHistoryOut
    options: list[InstallmentOptionOut]
    narrative: CreditNarrativeOut
