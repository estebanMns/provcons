from fastapi import APIRouter, Depends, UploadFile, File, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.documents_ai.repository import ProviderInventoryRepository
from app.modules.documents_ai.service import ImportResult, InventoryService
from app.modules.documents_ai.schemas import InventoryItemCreate, InventoryItemOut, InventoryItemUpdate
from app.dependencies.auth import get_current_user, require_same_organization
from app.modules.users.models import User
from app.core.audit import AuditService, AuditRepository
from pydantic import BaseModel
from app.modules.documents_ai.normalizer import DocumentNormalizer
from app.infrastructure.ai_client import AIClient
from app.infrastructure.documents import extract_json_from_upload
from app.core.exceptions import ValidationError
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["Documentos e IA"])


class ImportTextRequest(BaseModel):
    raw_text: str


def get_inventory_service(db: AsyncSession = Depends(get_db)) -> InventoryService:
    audit = AuditService(AuditRepository(db))
    normalizer = DocumentNormalizer(AIClient())
    return InventoryService(ProviderInventoryRepository(db), audit, normalizer)


def _import_out(result: ImportResult, extracted: int, file_name: str | None = None) -> dict:
    return {
        "items_extracted": extracted,
        "created": len(result.created),
        "updated": len(result.updated),
        "skipped": result.skipped,
        "file_name": file_name,
        "saved_items": [InventoryItemOut.model_validate(i).model_dump(mode="json") for i in result.items],
    }


@router.post("/inventory/{provider_org_id}/import-text", response_model=dict)
async def import_inventory_from_text(
    provider_org_id: int,
    payload: ImportTextRequest,
    service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(get_current_user),
):
    """Recibe texto crudo, la IA lo estructura y se guarda sumando por código."""
    require_same_organization(provider_org_id, current_user)
    result = await service.import_from_text(provider_org_id, payload.raw_text, current_user.id)
    return _import_out(result, len(result.items) + result.skipped)


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
        provider_org_id=provider_org_id, sku=payload.sku,
        material_name=payload.material_name, unit=payload.unit,
        unit_price=payload.unit_price, quantity_available=payload.quantity_available,
        specs=payload.specs, actor_user_id=current_user.id,
    )


@router.patch("/inventory/{provider_org_id}/{item_id}", response_model=InventoryItemOut)
async def update_inventory_item(
    provider_org_id: int,
    item_id: int,
    payload: InventoryItemUpdate,
    service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(get_current_user),
):
    """Corrige código, nombre, unidad, precio o cantidad de un producto."""
    require_same_organization(provider_org_id, current_user)
    return await service.update_item(provider_org_id, item_id, payload.model_dump(exclude_unset=True), current_user.id)


@router.delete("/inventory/{provider_org_id}/{item_id}", status_code=204)
async def delete_inventory_item(
    provider_org_id: int,
    item_id: int,
    service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(get_current_user),
):
    """Deja de mostrar el producto en el inventario y en las comparaciones."""
    require_same_organization(provider_org_id, current_user)
    await service.delete_item(provider_org_id, item_id, current_user.id)
    return Response(status_code=204)


_UPLOAD_INSTRUCTION = """Eres un asistente que extrae información de catálogos de inventario.
Devuelve ÚNICAMENTE un JSON con esta forma exacta:
{
  "items": [
    {
      "sku": string,
      "material_name": string,
      "quantity_available": number,
      "unit": string,
      "unit_price": number,
      "specs": object
    }
  ]
}
"sku" es el código o referencia del producto si el catálogo lo trae (columnas
tipo "Código", "Ref", "SKU", "Item"). Si una fila no trae código, usa null:
nunca inventes un código.
Si no puedes determinar un valor con certeza, usa null en ese campo — nunca inventes datos."""


@router.post("/inventory/{provider_org_id}/upload", response_model=dict)
async def upload_inventory_file(
    provider_org_id: int,
    file: UploadFile = File(...),
    service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(get_current_user),
):
    """Procesa un archivo de inventario (PDF, Excel o imagen) con IA. Las filas
    con un código que ya existe suman a ese producto; las demás se agregan."""
    require_same_organization(provider_org_id, current_user)

    file_content = await file.read()
    logger.info("Procesando archivo de inventario: %s (%s bytes)", file.filename, len(file_content))

    # Si la IA falla, el error llega al usuario en vez de responder "0 productos"
    extracted_data = await extract_json_from_upload(AIClient(), file.filename, file_content, _UPLOAD_INSTRUCTION)
    items_data = [i for i in extracted_data.get("items", []) or [] if isinstance(i, dict) and i.get("material_name")]
    if not items_data:
        raise ValidationError("No se encontraron productos en el archivo")

    result = await service.bulk_import(provider_org_id, items_data, current_user.id)
    return {"provider_org_id": provider_org_id, **_import_out(result, len(items_data), file.filename)}
