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

    # Leer archivo
    file_content = await file.read()
    mime_type_map = {
        "pdf": "application/pdf",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xls": "application/vnd.ms-excel",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
    }

    file_ext = file.filename.split(".")[-1].lower() if file.filename else ""
    mime_type = mime_type_map.get(file_ext, "application/octet-stream")

    logger.info("Procesando archivo de inventario: %s (%s bytes, tipo: %s)",
                file.filename, len(file_content), mime_type)

    # Usar IA para extraer productos del archivo
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
    }"""

    try:
        extracted_data = await ai_client.generate_json_from_file(
            file_bytes=file_content,
            mime_type=mime_type,
            system_instruction=system_instruction,
        )
        items_data = extracted_data.get("items", [])
    except Exception as e:
        logger.error("Error procesando archivo con IA: %s", str(e))
        items_data = []

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
            logger.warning("Error guardando item de inventario: %s", str(e))
            continue

    logger.info("Inventario procesado: org=%s, items_extracted=%s, items_saved=%s",
                provider_org_id, len(items_data), len(saved_items))

    return {
        "provider_org_id": provider_org_id,
        "items_extracted": len(items_data),
        "items_saved": len(saved_items),
        "file_name": file.filename,
        "saved_items": saved_items,
    }