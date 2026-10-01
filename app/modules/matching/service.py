from app.modules.matching.repository import QuotationRepository, MatchRepository
from app.modules.matching.models import Quotation, QuotationItem, Match, QuotationStatus
from app.modules.matching.scoring import ScoringStrategy
from app.core.audit import AuditService
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger

logger = get_logger(__name__)


class MatchingService:
    def __init__(
        self, quotation_repo: QuotationRepository, match_repo: MatchRepository,
        scoring_strategy: ScoringStrategy, audit: AuditService,
    ):
        self.quotation_repo = quotation_repo
        self.match_repo = match_repo
        self.scoring_strategy = scoring_strategy
        self.audit = audit

    async def create_quotation(
    self, constructora_org_id: int, title: str, items_data: list[dict], actor_user_id: int,
    ) -> Quotation:
        quotation = Quotation(
            constructora_org_id=constructora_org_id,
            title=title,
            status=QuotationStatus.abierta,
            items=[QuotationItem(**item_data) for item_data in items_data],  # <- ya van incluidos desde el constructor
        )
        saved = await self.quotation_repo.save(quotation)

        logger.info("Cotización creada: id=%s org=%s items=%s", saved.id, constructora_org_id, len(items_data))
        await self.audit.record(
            action="quotation.created", resource_type="Quotation", resource_id=saved.id,
            actor_user_id=actor_user_id, actor_organization_id=constructora_org_id,
            details={"title": title, "items_count": len(items_data)},
        )
        return saved

    async def run_matching(self, quotation_id: int, actor_user_id: int) -> list[Match]:
        quotation = await self.quotation_repo.get_by_id(quotation_id)
        if quotation is None:
            raise NotFoundError("Cotización no encontrada")

        items = await self.quotation_repo.get_items(quotation_id)
        results = []

        for item in items:
            candidates = await self.match_repo.find_candidate_inventory(item.material_name)
            for inventory in candidates:
                score, breakdown = self.scoring_strategy.calculate(item, inventory)
                match = Match(
                    quotation_item_id=item.id,
                    provider_inventory_id=inventory.id,
                    provider_org_id=inventory.provider_org_id,
                    score=score,
                    criteria_breakdown=breakdown,
                )
                saved = await self.match_repo.save(match)
                results.append(saved)

        logger.info("Matching ejecutado: quotation=%s matches_generados=%s", quotation_id, len(results))
        await self.audit.record(
            action="matching.run", resource_type="Quotation", resource_id=quotation_id,
            actor_user_id=actor_user_id, actor_organization_id=quotation.constructora_org_id,
            details={"matches_generated": len(results)},
        )
        return results