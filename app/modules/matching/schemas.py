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