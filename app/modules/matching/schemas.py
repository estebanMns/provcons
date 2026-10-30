from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.modules.matching.models import QuotationStatus


class QuotationItemCreate(BaseModel):
    material_name: str = Field(min_length=2, max_length=200)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=20)
    unit_price: float | None = Field(default=None, ge=0)
    specs: dict = Field(default_factory=dict)


class QuotationCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    items: list[QuotationItemCreate] = Field(min_length=1)


class QuotationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    constructora_org_id: int
    title: str
    status: QuotationStatus
    created_at: datetime


class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    provider_org_id: int
    score: float
    criteria_breakdown: dict


class OfferOut(BaseModel):
    match_id: int
    provider_org_id: int
    provider_name: str
    inventory_id: int
    material_name: str
    unit: str
    unit_price: float | None
    quantity_available: float
    subtotal: float | None
    score: float
    criteria: dict
    is_cheapest: bool
    is_best: bool


class ItemComparisonOut(BaseModel):
    item_id: int
    material_name: str
    quantity: float
    unit: str
    budget_unit_price: float | None
    offers: list[OfferOut]


class ProviderRankingOut(BaseModel):
    provider_org_id: int
    provider_name: str
    score: float
    coverage: float
    items_covered: int
    items_full_stock: int
    cheapest_items: int
    unit_mismatches: int
    total_cost: float
    justificacion: str
    match_ids: list[int]


class CombinationItemOut(BaseModel):
    item_id: int
    material_name: str
    provider_org_id: int
    provider_name: str
    match_id: int
    unit_price: float | None
    subtotal: float | None


class BestCombinationOut(BaseModel):
    items: list[CombinationItemOut]
    total_cost: float
    items_covered: int
    providers_count: int
    savings_vs_recommendation: float | None


class QuotationComparisonOut(BaseModel):
    quotation_id: int
    title: str
    matches_found: int
    items_total: int
    items_without_offers: int
    items: list[ItemComparisonOut]
    providers: list[ProviderRankingOut]
    recommendation: ProviderRankingOut | None
    best_combination: BestCombinationOut


class QuotationUploadOut(QuotationComparisonOut):
    items_extracted: int