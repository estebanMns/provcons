from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.matching.repository import QuotationRepository, MatchRepository
from app.modules.matching.service import MatchingService
from app.modules.matching.scoring import SimpleScoringStrategy
from app.modules.matching.schemas import QuotationCreate, QuotationOut, MatchOut
from app.dependencies.auth import get_current_user
from app.modules.users.models import User
from app.core.audit import AuditService, AuditRepository

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