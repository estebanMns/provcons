from abc import ABC, abstractmethod
from dataclasses import dataclass
from app.modules.matching.models import QuotationItem
from app.modules.matching.text_matching import units_compatible
from app.modules.documents_ai.models import ProviderInventoryItem


@dataclass(frozen=True)
class OfferContext:
    """Lo que el scoring necesita saber además del par (pedido, oferta):
    qué tan parecido es el material y el mejor precio entre TODAS las ofertas
    para ese mismo ítem, para poder comparar un proveedor contra los demás."""
    similarity: float
    best_unit_price: float | None


class ScoringStrategy(ABC):
    """Contrato que cualquier algoritmo de scoring debe cumplir."""

    @abstractmethod
    def calculate(
        self, item: QuotationItem, inventory: ProviderInventoryItem, context: OfferContext,
    ) -> tuple[float, dict]:
        raise NotImplementedError


class ComparativeScoringStrategy(ScoringStrategy):
    """Califica cada oferta de 0 a 1 con criterios medibles y explicables:
    - compatibilidad: qué tan parecido es el material ofrecido al pedido
    - disponibilidad: qué parte de la cantidad pedida tiene en stock
    - precio: qué tan cerca está del precio más bajo ofrecido para ese ítem
    Si la unidad no coincide (m3 vs bulto) la oferta se penaliza, porque los
    precios no son comparables directamente."""

    WEIGHTS = {"compatibilidad": 0.35, "disponibilidad": 0.35, "precio": 0.30}
    UNIT_MISMATCH_PENALTY = 0.6
    UNKNOWN_PRICE_SCORE = 0.5

    def calculate(
        self, item: QuotationItem, inventory: ProviderInventoryItem, context: OfferContext,
    ) -> tuple[float, dict]:
        quantity_available = inventory.quantity_available or 0
        disponibilidad = min(quantity_available / item.quantity, 1.0) if item.quantity else 0.0

        unit_price = inventory.unit_price
        if unit_price and unit_price > 0 and context.best_unit_price:
            precio = context.best_unit_price / unit_price
        else:
            precio = self.UNKNOWN_PRICE_SCORE

        unidad_compatible = units_compatible(item.unit, inventory.unit)

        final_score = (
            self.WEIGHTS["compatibilidad"] * context.similarity
            + self.WEIGHTS["disponibilidad"] * disponibilidad
            + self.WEIGHTS["precio"] * precio
        )
        if not unidad_compatible:
            final_score *= self.UNIT_MISMATCH_PENALTY
        final_score = round(final_score, 3)

        breakdown = {
            "compatibilidad": round(context.similarity, 3),
            "disponibilidad": round(disponibilidad, 3),
            "precio": round(precio, 3),
            "unidad_compatible": unidad_compatible,
            "stock_suficiente": quantity_available >= item.quantity,
            "unit_price": unit_price,
            "subtotal": round(unit_price * item.quantity, 2) if unit_price else None,
            "final_score": final_score,
        }
        if item.unit_price and unit_price:
            # Positivo = más caro que el presupuesto de la constructora
            breakdown["vs_presupuesto"] = round((unit_price - item.unit_price) / item.unit_price, 3)

        return final_score, breakdown
