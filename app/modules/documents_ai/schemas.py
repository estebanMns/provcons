from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class InventoryItemCreate(BaseModel):
    material_name: str = Field(min_length=2, max_length=200)
    unit: str = Field(min_length=1, max_length=20)
    unit_price: float = Field(gt=0)
    quantity_available: float = Field(ge=0, default=0)
    specs: dict = Field(default_factory=dict)


class InventoryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider_org_id: int
    material_name: str
    unit: str
    unit_price: float
    quantity_available: float
    specs: dict
    created_at: datetime