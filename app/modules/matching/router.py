from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.matching.repository import QuotationRepository, MatchRepository
from app.modules.matching.service import MatchingService
from app.modules.matching.scoring import SimpleScoringStrategy
from app.modules.matching.schemas import QuotationCreate, QuotationOut, MatchOut
from app.dependencies.auth import get_current_user
from app.modules.users.models import User
from app.core.audit import AuditService, AuditRepository
from app.infrastructure.ai_client import AIClient
from pydantic import BaseModel
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/matching", tags=["Matching y recomendación"])


def get_matching_service(db: AsyncSession = Depends(get_db)) -> MatchingService:
    audit = AuditService(AuditRepository(db))
    return MatchingService(
        QuotationRepository(db), MatchRepository(db),
        scoring_strategy=SimpleScoringStrategy(),  # aquí se cambia por MLScoringStrategy en el futuro
        audit=audit,
    )


@router.post("/quotations", response_model=QuotationOut)
async def create_quotation(
    payload: QuotationCreate,
    service: MatchingService = Depends(get_matching_service),
    current_user: User = Depends(get_current_user),
):
    items_data = [item.model_dump() for item in payload.items]
    return await service.create_quotation(
        constructora_org_id=current_user.organization_id,
        title=payload.title, items_data=items_data, actor_user_id=current_user.id,
    )


@router.post("/quotations/{quotation_id}/run", response_model=list[MatchOut])
async def run_matching(
    quotation_id: int,
    service: MatchingService = Depends(get_matching_service),
    current_user: User = Depends(get_current_user),
):
    return await service.run_matching(quotation_id, actor_user_id=current_user.id)


@router.post("/quotations/upload", response_model=dict)
async def upload_quotation_file(
    title: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Endpoint que procesa un archivo de cotización (PDF, Excel o imagen) con IA,
    extrae los materiales, crea una cotización y ejecuta matching automático."""

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

    logger.info("Procesando archivo de cotización: %s (%s bytes, tipo: %s)",
                file.filename, len(file_content), mime_type)

    # Usar IA para extraer materiales del archivo
    ai_client = AIClient()
    system_instruction = """Eres un asistente que extrae información de materiales de cotizaciones.
    Devuelve ÚNICAMENTE un JSON con esta forma exacta:
    {
      "items": [
        {
          "material_name": string,
          "quantity": number,
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

    # Crear cotización
    service = MatchingService(
        QuotationRepository(db), MatchRepository(db),
        scoring_strategy=SimpleScoringStrategy(),
        audit=AuditService(AuditRepository(db)),
    )

    quotation = await service.create_quotation(
        constructora_org_id=current_user.organization_id,
        title=title or file.filename or "Cotización sin título",
        items_data=items_data,
        actor_user_id=current_user.id,
    )

    # Ejecutar matching automático
    matches = await service.run_matching(quotation.id, actor_user_id=current_user.id)

    logger.info("Cotización procesada: id=%s, items=%s, matches=%s",
                quotation.id, len(items_data), len(matches))

    return {
        "quotation_id": quotation.id,
        "title": quotation.title,
        "items_extracted": len(items_data),
        "matches_found": len(matches),
        "top_providers": matches[:5],  # Top 5 proveedores
    }