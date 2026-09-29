from abc import ABC, abstractmethod
from app.modules.matching.models import QuotationItem
from app.modules.documents_ai.models import ProviderInventoryItem


class ScoringStrategy(ABC):
    """Contrato que cualquier algoritmo de scoring debe cumplir."""

    @abstractmethod
    def calculate(self, item: QuotationItem, inventory: ProviderInventoryItem) -> tuple[float, dict]:
        raise NotImplementedError


class SimpleScoringStrategy(ScoringStrategy):
    """Primera versión: reglas fijas. Se reemplaza por IA real (MLScoringStrategy)
    más adelante, sin tocar MatchingService ni el router."""

    def calculate(self, item: QuotationItem, inventory: ProviderInventoryItem) -> tuple[float, dict]:
        breakdown = {}

        stock_score = 1.0 if inventory.quantity_available >= item.quantity else 0.3
        breakdown["stock_score"] = stock_score

        price_score = 0.8
        breakdown["price_score"] = price_score

        final_score = round((stock_score * 0.6) + (price_score * 0.4), 2)
        breakdown["final_score"] = final_score

        return final_score, breakdown