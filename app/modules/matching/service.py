from app.modules.matching.repository import QuotationRepository, MatchRepository
from app.modules.matching.models import Quotation, QuotationItem, Match, QuotationStatus
from app.modules.matching.scoring import ScoringStrategy, OfferContext
from app.modules.matching.comparison import ScoredOffer, build_comparison
from app.modules.matching.text_matching import MATCH_THRESHOLD, material_similarity, specs_conflict, units_compatible
from app.modules.matching.ai_review import AIProductReviewer, ProductReview, ReviewResult, decide_similarity
from app.modules.documents_ai.models import ProviderInventoryItem
from app.core.audit import AuditService
from app.core.exceptions import NotFoundError, ForbiddenError
from app.core.logging import get_logger

logger = get_logger(__name__)


class MatchingService:
    def __init__(
        self, quotation_repo: QuotationRepository, match_repo: MatchRepository,
        scoring_strategy: ScoringStrategy, audit: AuditService,
        reviewer: AIProductReviewer | None = None,
    ):
        self.quotation_repo = quotation_repo
        self.match_repo = match_repo
        self.scoring_strategy = scoring_strategy
        self.audit = audit
        self.reviewer = reviewer  # None = solo comparación por texto

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

    async def list_quotations(self, org_id: int) -> list[dict]:
        return await self.quotation_repo.list_by_organization(org_id)

    async def get_comparison(self, quotation_id: int, actor_org_id: int) -> dict:
        """Rearma la comparación con los matches ya guardados, sin volver a
        llamar a la IA (para reabrir una cotización desde el historial)."""
        quotation = await self._get_owned_quotation(quotation_id, actor_org_id)
        items = await self.quotation_repo.get_items(quotation_id)
        items_by_id = {item.id: item for item in items}

        # Si se recalculó la comparación, los matches que tienen orden se
        # conservan junto a los nuevos: por material y proveedor vale el último.
        latest: dict[tuple[int, int], tuple] = {}
        for match, inventory in await self.match_repo.get_offers_for_items(list(items_by_id)):
            latest[(match.quotation_item_id, match.provider_org_id)] = (match, inventory)
        offers = [
            ScoredOffer(item=items_by_id[match.quotation_item_id], inventory=inventory, match=match)
            for match, inventory in latest.values()
        ]

        provider_names = await self.match_repo.get_organization_names({o.match.provider_org_id for o in offers})
        return {
            "quotation_id": quotation.id,
            "title": quotation.title,
            "matches_found": len(offers),
            "ai_review": {
                # "stored": la revisión ya se hizo al comparar; cada oferta
                # conserva su veredicto en criteria.revision_ia
                "status": "stored",
                "products_reviewed": 0,
                "matches_added": sum(1 for o in offers if o.match.criteria_breakdown.get("metodo") == "ia"),
                "matches_rejected": 0,
            },
            **build_comparison(items, offers, provider_names),
        }

    async def _get_owned_quotation(self, quotation_id: int, actor_org_id: int) -> Quotation:
        quotation = await self.quotation_repo.get_by_id(quotation_id)
        if quotation is None:
            raise NotFoundError("Cotización no encontrada")
        if quotation.constructora_org_id != actor_org_id:
            raise ForbiddenError("No tienes acceso a esta cotización")
        return quotation

    @staticmethod
    def _lexical_candidates(
        items: list[QuotationItem], products: list[ProviderInventoryItem],
    ) -> tuple[dict[tuple[int, int], float], dict[int, list[ProviderInventoryItem]]]:
        """Similitud por texto de cada par (pedido, producto) y, por ítem, los
        productos que el texto considera candidatos (para que la IA los confirme
        o los descarte)."""
        similarity: dict[tuple[int, int], float] = {}
        candidates: dict[int, list[ProviderInventoryItem]] = {}
        for item in items:
            for product in products:
                score = material_similarity(item.material_name, product.material_name)
                similarity[(item.id, product.id)] = score
                if score >= MATCH_THRESHOLD:
                    candidates.setdefault(item.id, []).append(product)
        return similarity, candidates

    @staticmethod
    def _best_offer_per_provider(
        accepted: list[tuple[ProviderInventoryItem, float, str, ProductReview | None]],
    ) -> list[tuple[ProviderInventoryItem, float, str, ProductReview | None]]:
        """Una sola oferta por proveedor: si tiene el material repetido, cuenta
        la más parecida y, a igual parecido, la más barata."""
        best: dict[int, tuple] = {}
        for offer in accepted:
            inventory, similarity = offer[0], offer[1]
            current = best.get(inventory.provider_org_id)
            key = (similarity, -(inventory.unit_price or float("inf")))
            if current is None or key > (current[1], -(current[0].unit_price or float("inf"))):
                best[inventory.provider_org_id] = offer
        return list(best.values())

    async def run_matching(self, quotation_id: int, actor_user_id: int, actor_org_id: int) -> dict:
        quotation = await self._get_owned_quotation(quotation_id, actor_org_id)

        items = await self.quotation_repo.get_items(quotation_id)
        await self.match_repo.delete_unordered_for_items([item.id for item in items])

        products = await self.match_repo.list_inventory()
        lexical, lexical_candidates = self._lexical_candidates(items, products)
        if self.reviewer is not None:
            review = await self.reviewer.review(items, products, lexical_candidates)
        else:
            review = ReviewResult(status="disabled", reviews={})

        # Contados por (material, proveedor) para no inflarlos con productos repetidos
        added_by_ai: set[tuple[int, int]] = set()
        rejected_by_ai: set[tuple[int, int]] = set()
        pending: list[tuple[QuotationItem, ProviderInventoryItem, Match]] = []
        for item in items:
            accepted = []
            for product in products:
                product_review = review.reviews.get((item.id, product.id))
                lexical_score = lexical[(item.id, product.id)]
                similarity, method = decide_similarity(
                    lexical_score, specs_conflict(item.material_name, product.material_name),
                    product_review, MATCH_THRESHOLD,
                )
                if method == "descartado_por_ia" and lexical_score >= MATCH_THRESHOLD:
                    rejected_by_ai.add((item.id, product.provider_org_id))
                if similarity is not None:
                    accepted.append((product, similarity, method, product_review))

            offers = self._best_offer_per_provider(accepted)
            added_by_ai.update((item.id, inv.provider_org_id) for inv, _, method, _ in offers if method == "ia")
            comparable_prices = [
                inv.unit_price for inv, *_ in offers
                if inv.unit_price and units_compatible(item.unit, inv.unit)
            ]
            best_unit_price = min(comparable_prices) if comparable_prices else None

            for inventory, similarity, method, product_review in offers:
                score, breakdown = self.scoring_strategy.calculate(
                    item, inventory, OfferContext(similarity=similarity, best_unit_price=best_unit_price),
                )
                breakdown["metodo"] = method
                if product_review is not None:
                    breakdown["revision_ia"] = {
                        "equivalente": product_review.equivalente,
                        "confianza": product_review.confianza,
                        "motivo": product_review.motivo,
                    }
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
                "ai_review_status": review.status,
            },
        )
        return {
            "quotation_id": quotation.id,
            "title": quotation.title,
            "matches_found": len(offers),
            "ai_review": {
                "status": review.status,
                "products_reviewed": review.products_reviewed,
                "matches_added": len(added_by_ai),
                "matches_rejected": len(rejected_by_ai),
            },
            **comparison,
        }
