from app.modules.matching.repository import QuotationRepository, MatchRepository
from app.modules.matching.models import Quotation, QuotationItem, Match, QuotationStatus
from app.modules.matching.scoring import ScoringStrategy, OfferContext
from app.modules.matching.comparison import ScoredOffer, build_comparison
from app.modules.matching.text_matching import MATCH_THRESHOLD, material_similarity, search_terms, units_compatible
from app.modules.documents_ai.models import ProviderInventoryItem
from app.core.audit import AuditService
from app.core.exceptions import NotFoundError, ForbiddenError
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

    async def _best_offer_per_provider(self, item: QuotationItem) -> list[tuple[ProviderInventoryItem, float]]:
        """Candidatos del inventario que SÍ son el material pedido, dejando una
        sola oferta por proveedor (si un proveedor tiene el material repetido,
        cuenta la más parecida y, a igual parecido, la más barata)."""
        candidates = await self.match_repo.find_candidate_inventory(search_terms(item.material_name))

        best: dict[int, tuple[ProviderInventoryItem, float]] = {}
        for inventory in candidates:
            similarity = material_similarity(item.material_name, inventory.material_name)
            if similarity < MATCH_THRESHOLD:
                continue
            current = best.get(inventory.provider_org_id)
            key = (similarity, -(inventory.unit_price or float("inf")))
            if current is None or key > (current[1], -(current[0].unit_price or float("inf"))):
                best[inventory.provider_org_id] = (inventory, similarity)
        return list(best.values())

    async def run_matching(self, quotation_id: int, actor_user_id: int, actor_org_id: int) -> dict:
        quotation = await self.quotation_repo.get_by_id(quotation_id)
        if quotation is None:
            raise NotFoundError("Cotización no encontrada")
        if quotation.constructora_org_id != actor_org_id:
            raise ForbiddenError("No tienes acceso a esta cotización")

        items = await self.quotation_repo.get_items(quotation_id)
        await self.match_repo.delete_unordered_for_items([item.id for item in items])

        pending: list[tuple[QuotationItem, ProviderInventoryItem, Match]] = []
        for item in items:
            offers = await self._best_offer_per_provider(item)
            comparable_prices = [
                inv.unit_price for inv, _ in offers
                if inv.unit_price and units_compatible(item.unit, inv.unit)
            ]
            best_unit_price = min(comparable_prices) if comparable_prices else None

            for inventory, similarity in offers:
                score, breakdown = self.scoring_strategy.calculate(
                    item, inventory, OfferContext(similarity=similarity, best_unit_price=best_unit_price),
                )
                match = Match(
                    quotation_item_id=item.id,
                    provider_inventory_id=inventory.id,
                    provider_org_id=inventory.provider_org_id,
                    score=score,
                    criteria_breakdown=breakdown,
                )
                pending.append((item, inventory, match))

        await self.match_repo.save_all([match for _, _, match in pending])
        offers = [ScoredOffer(item=item, inventory=inventory, match=match) for item, inventory, match in pending]

        provider_names = await self.match_repo.get_organization_names({o.match.provider_org_id for o in offers})
        comparison = build_comparison(items, offers, provider_names)
        recommendation = comparison["recommendation"]

        logger.info(
            "Matching ejecutado: quotation=%s matches_generados=%s proveedores=%s",
            quotation_id, len(offers), len(comparison["providers"]),
        )
        await self.audit.record(
            action="matching.run", resource_type="Quotation", resource_id=quotation_id,
            actor_user_id=actor_user_id, actor_organization_id=quotation.constructora_org_id,
            details={
                "matches_generated": len(offers),
                "providers_compared": len(comparison["providers"]),
                "recommended_provider_org_id": recommendation["provider_org_id"] if recommendation else None,
            },
        )
        return {
            "quotation_id": quotation.id,
            "title": quotation.title,
            "matches_found": len(offers),
            **comparison,
        }
