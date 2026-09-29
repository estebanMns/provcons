from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.documents_ai.repository import ProviderInventoryRepository
from app.modules.documents_ai.service import InventoryService
from app.modules.documents_ai.schemas import InventoryItemCreate, InventoryItemOut
from app.dependencies.auth import get_current_user, require_same_organization
from app.modules.users.models import User
from app.core.audit import AuditService, AuditRepository

router = APIRouter(prefix="/documents", tags=["Documentos e IA"])


def get_inventory_service(db: AsyncSession = Depends(get_db)) -> InventoryService:
    audit = AuditService(AuditRepository(db))
    return InventoryService(ProviderInventoryRepository(db), audit)


@router.get("/inventory/{provider_org_id}", response_model=list[InventoryItemOut])
async def list_inventory(
    provider_org_id: int,
    service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(get_current_user),
):
    require_same_organization(provider_org_id, current_user)
    return await service.list_inventory(provider_org_id)


@router.post("/inventory/{provider_org_id}", response_model=InventoryItemOut)
async def add_inventory_item(
    provider_org_id: int,
    payload: InventoryItemCreate,
    service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(get_current_user),
):
    require_same_organization(provider_org_id, current_user)
    return await service.add_item(
        provider_org_id=provider_org_id,
        material_name=payload.material_name, unit=payload.unit,
        unit_price=payload.unit_price, quantity_available=payload.quantity_available,
        specs=payload.specs, actor_user_id=current_user.id,
    )