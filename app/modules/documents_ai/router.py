from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.documents_ai.repository import ProviderInventoryRepository
from app.modules.documents_ai.service import InventoryService
from app.modules.documents_ai.schemas import InventoryItemCreate, InventoryItemOut
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


@router.post("/inventory/{provider_org_id}/import-text", response_model=list[InventoryItemOut])
async def import_inventory_from_text(
    provider_org_id: int,
    payload: ImportTextRequest,
    service: InventoryService = Depends(get_inventory_service),
    current_user: User = Depends(get_current_user),
):
    """Primer endpoint real de IA: recibe texto (temporalmente pegado a mano;
    cuando tengamos ocr_pipeline.py, este texto vendrá de un PDF/imagen
    subido), lo normaliza y lo guarda como inventario real."""
    require_same_organization(provider_org_id, current_user)
    return await service.import_from_text(provider_org_id, payload.raw_text, current_user.id)


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


@router.post("/inventory/{provider_org_id}/upload", response_model=dict)
async def upload_inventory_file(
    provider_org_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Endpoint que procesa un archivo de inventario (PDF, Excel o imagen) con IA,
    extrae los productos y los guarda en el inventario del proveedor."""

    require_same_organization(provider_org_id, current_user)

    file_content = await file.read()
    logger.info("Procesando archivo de inventario: %s (%s bytes)", file.filename, len(file_content))

    # Usar IA para extraer productos del archivo (PDF, imagen o Excel). Si la IA
    # falla, el error llega al usuario en vez de responder "0 productos".
    ai_client = AIClient()
    system_instruction = """Eres un asistente que extrae información de catálogos de inventario.
    Devuelve ÚNICAMENTE un JSON con esta forma exacta:
    {
      "items": [
        {
          "material_name": string,
          "quantity_available": number,
          "unit": string,
          "unit_price": number,
          "specs": object
        }
      ]
    }
    Si no puedes determinar un valor con certeza, usa null en ese campo — nunca inventes datos."""

    extracted_data = await extract_json_from_upload(ai_client, file.filename, file_content, system_instruction)
    items_data = [i for i in extracted_data.get("items", []) or [] if isinstance(i, dict) and i.get("material_name")]
    if not items_data:
        raise ValidationError("No se encontraron productos en el archivo")

    # Guardar items en inventario
    service = InventoryService(
        ProviderInventoryRepository(db),
        AuditService(AuditRepository(db)),
        DocumentNormalizer(AIClient()),
    )

    saved_items = []
    for item_data in items_data:
        try:
            saved_item = await service.add_item(
                provider_org_id=provider_org_id,
                material_name=item_data.get("material_name", ""),
                unit=item_data.get("unit", ""),
                unit_price=item_data.get("unit_price"),
                quantity_available=item_data.get("quantity_available", 0),
                specs=item_data.get("specs", {}),
                actor_user_id=current_user.id,
            )
            saved_items.append(saved_item)
        except Exception as e:
            # Un ítem inválido (ej. sin precio) no debe tumbar el resto: se
            # deshace la transacción fallida y se sigue con el siguiente.
            logger.warning("Error guardando item de inventario: %s", str(e))
            await db.rollback()
            continue

    logger.info("Inventario procesado: org=%s, items_extracted=%s, items_saved=%s",
                provider_org_id, len(items_data), len(saved_items))

    return {
        "provider_org_id": provider_org_id,
        "items_extracted": len(items_data),
        "items_saved": len(saved_items),
        "file_name": file.filename,
        "saved_items": [InventoryItemOut.model_validate(item).model_dump(mode="json") for item in saved_items],
    }