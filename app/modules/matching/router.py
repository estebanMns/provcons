from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.matching.repository import QuotationRepository, MatchRepository
from app.modules.matching.service import MatchingService
from app.modules.matching.scoring import ComparativeScoringStrategy
from app.modules.matching.ai_review import AIProductReviewer
from app.modules.matching.matchers import LocalMaterialMatcher, MaterialMatcher, ResilientMatcher
from app.infrastructure.matching_engine_client import GrpcMaterialMatcher
from app.core.config import settings
from app.modules.matching.schemas import (
    QuotationCreate, QuotationOut, QuotationComparisonOut, QuotationUploadOut, QuotationSummaryOut,
)
from app.dependencies.auth import get_current_user
from app.modules.users.models import User
from app.core.audit import AuditService, AuditRepository
from app.core.exceptions import ValidationError
from app.infrastructure.ai_client import AIClient
from app.infrastructure.documents import extract_json_from_upload
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/matching", tags=["Matching y recomendación"])


# Uno por proceso: así el canal gRPC se reutiliza entre peticiones
_engine = GrpcMaterialMatcher(settings.matching_engine_addr, settings.matching_engine_timeout)
_matcher: MaterialMatcher = (
    LocalMaterialMatcher() if settings.matching_engine_mode == "local"
    else ResilientMatcher(primary=_engine, fallback=LocalMaterialMatcher())
)


async def matching_engine_status() -> str:
    """Para /health: "local" o el estado del health check gRPC del motor."""
    return "local" if settings.matching_engine_mode == "local" else await _engine.health()


def get_matching_service(db: AsyncSession = Depends(get_db)) -> MatchingService:
    """Factory: arma el servicio con sus dependencias concretas."""
    audit = AuditService(AuditRepository(db))
    reviewer = AIProductReviewer(AIClient()) if settings.matching_ai_review and settings.gemini_api_key else None
    return MatchingService(
        QuotationRepository(db), MatchRepository(db),
        scoring_strategy=ComparativeScoringStrategy(),
        audit=audit,
        reviewer=reviewer,
        matcher=_matcher,
    )


def _clean_extracted_items(raw_items: list) -> list[dict]:
    """La IA puede devolver filas incompletas (sin cantidad, con null). Solo se
    aceptan las que tienen nombre y una cantidad positiva; no se inventan datos."""
    cleaned = []
    for raw in raw_items or []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("material_name") or "").strip()
        try:
            quantity = float(raw.get("quantity") or 0)
        except (TypeError, ValueError):
            quantity = 0
        if len(name) < 2 or quantity <= 0:
            continue
        try:
            unit_price = float(raw["unit_price"]) if raw.get("unit_price") is not None else None
        except (TypeError, ValueError):
            unit_price = None
        cleaned.append({
            "material_name": name[:200],
            "quantity": quantity,
            "unit": str(raw.get("unit") or "")[:20],
            "unit_price": unit_price,
            "specs": raw.get("specs") if isinstance(raw.get("specs"), dict) else {},
        })
    return cleaned


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


@router.get("/quotations", response_model=list[QuotationSummaryOut])
async def list_quotations(
    service: MatchingService = Depends(get_matching_service),
    current_user: User = Depends(get_current_user),
):
    """Historial de cotizaciones de la organización."""
    return await service.list_quotations(current_user.organization_id)


@router.get("/quotations/{quotation_id}/comparison", response_model=QuotationComparisonOut)
async def get_comparison(
    quotation_id: int,
    service: MatchingService = Depends(get_matching_service),
    current_user: User = Depends(get_current_user),
):
    """Comparación guardada de una cotización (no vuelve a llamar a la IA)."""
    return await service.get_comparison(quotation_id, current_user.organization_id)


@router.post("/quotations/{quotation_id}/run", response_model=QuotationComparisonOut)
async def run_matching(
    quotation_id: int,
    service: MatchingService = Depends(get_matching_service),
    current_user: User = Depends(get_current_user),
):
    """Busca proveedores para cada material de la cotización y los compara
    entre sí (cobertura, stock, precio). Se puede ejecutar de nuevo cuando
    cambie el inventario de los proveedores."""
    return await service.run_matching(
        quotation_id, actor_user_id=current_user.id, actor_org_id=current_user.organization_id,
    )


@router.post("/quotations/upload", response_model=QuotationUploadOut)
async def upload_quotation_file(
    title: str = Form(""),
    file: UploadFile = File(...),
    service: MatchingService = Depends(get_matching_service),
    current_user: User = Depends(get_current_user),
):
    """Endpoint que procesa un archivo de cotización (PDF, Excel o imagen) con IA,
    extrae los materiales, crea una cotización y ejecuta matching automático."""

    file_content = await file.read()
    logger.info("Procesando archivo de cotización: %s (%s bytes)", file.filename, len(file_content))

    # Usar IA para extraer materiales del archivo (PDF, imagen o Excel). Si la
    # IA falla, el AIServiceError llega al usuario en vez de crear una
    # cotización vacía.
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
    }
    Si no puedes determinar un valor con certeza, usa null en ese campo — nunca inventes datos."""

    extracted_data = await extract_json_from_upload(ai_client, file.filename, file_content, system_instruction)
    items_data = _clean_extracted_items(extracted_data.get("items", []))
    if not items_data:
        raise ValidationError("No se encontraron materiales con cantidad en el archivo")

    quotation = await service.create_quotation(
        constructora_org_id=current_user.organization_id,
        title=title or file.filename or "Cotización sin título",
        items_data=items_data,
        actor_user_id=current_user.id,
    )

    # Ejecutar matching automático
    comparison = await service.run_matching(
        quotation.id, actor_user_id=current_user.id, actor_org_id=current_user.organization_id,
    )

    logger.info("Cotización procesada: id=%s, items=%s, matches=%s",
                quotation.id, len(items_data), comparison["matches_found"])

    return {**comparison, "items_extracted": len(items_data)}
