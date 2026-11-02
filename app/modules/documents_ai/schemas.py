from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class InventoryItemCreate(BaseModel):
    sku: str | None = Field(default=None, max_length=60)  # sin código, la app genera P-000N
    material_name: str = Field(min_length=2, max_length=200)
    unit: str = Field(min_length=1, max_length=20)
    unit_price: float = Field(gt=0)
    quantity_available: float = Field(ge=0, default=0)
    specs: dict = Field(default_factory=dict)


class InventoryItemUpdate(BaseModel):
    """Solo se cambian los campos que llegan."""
    sku: str | None = Field(default=None, min_length=1, max_length=60)
    material_name: str | None = Field(default=None, min_length=2, max_length=200)
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    unit_price: float | None = Field(default=None, gt=0)
    quantity_available: float | None = Field(default=None, ge=0)


class InventoryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider_org_id: int
    sku: str
    material_name: str
    unit: str
    unit_price: float
    quantity_available: float
    specs: dict
    created_at: datetime
