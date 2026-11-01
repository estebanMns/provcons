from datetime import datetime
from pydantic import BaseModel


class DeliveryDaysOut(BaseModel):
    median: float
    p25: float
    p75: float


class ProviderProfileOut(BaseModel):
    provider_org_id: int
    provider_name: str
    orders_closed: int
    orders_delivered: int
    orders_rejected: int
    orders_open: int
    orders_with_you: int
    reliability: float              # probabilidad de que entregue (0 a 1)
    confidence: str                 # "baja", "media" o "alta"
    delivery_days: DeliveryDaysOut | None
    price_trend_pct_30d: float | None
    market_premium_pct: float | None
    unit_mismatches: int


class ShortfallOut(BaseModel):
    material_name: str
    provider_name: str
    missing_quantity: float
    alternative_provider: str | None
    extra_cost: float


class ScenarioOut(BaseModel):
    cost: float
    days: float | None


class OptionNarrativeOut(BaseModel):
    que_pasara: str
    riesgos: list[str]
    consejo: str


class ForecastOptionOut(BaseModel):
    key: str
    label: str
    kind: str                       # "proveedor" o "combinacion"
    provider_org_ids: list[int]
    main_provider_id: int | None
    items_from_main: int
    complement_items: int
    cost_today: float
    expected_cost: float
    success_probability: float
    confidence: str
    delivery_days: DeliveryDaysOut | None
    shortfalls: list[ShortfallOut]
    scenarios: dict[str, ScenarioOut]
    narrative: OptionNarrativeOut


class QuotationForecastOut(BaseModel):
    quotation_id: int
    items_total: int
    items_unavailable: list[str]
    providers: list[ProviderProfileOut]
    options: list[ForecastOptionOut]
    best_option_key: str | None
    current_recommendation_key: str | None
    summary: str
    narrative_source: str           # "ia" o "plantilla"
    generated_at: datetime
    cached: bool
