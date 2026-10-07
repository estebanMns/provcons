from abc import ABC, abstractmethod
import asyncio
from app.modules.matching.models import QuotationItem
from app.modules.documents_ai.models import ProviderInventoryItem
from app.infrastructure.ai_client import AIClient
from app.core.logging import get_logger

logger = get_logger(__name__)


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


class AIScoreStrategy(ScoringStrategy):
    """Estrategia de scoring usando IA de Gemini para análisis inteligente
    de disponibilidad, precio, logística e historial."""

    def __init__(self, ai_client: AIClient = None):
        self.ai_client = ai_client or AIClient()

    def calculate(self, item: QuotationItem, inventory: ProviderInventoryItem) -> tuple[float, dict]:
        """Calcula score de forma síncrona (wrapper para la versión async)."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        score, breakdown = loop.run_until_complete(
            self._calculate_async(item, inventory)
        )
        return score, breakdown

    async def _calculate_async(self, item: QuotationItem, inventory: ProviderInventoryItem) -> tuple[float, dict]:
        """Calcula score usando IA."""
        system_instruction = """Eres un experto en logística y compras. Analiza este par de:
        - Cotización (material solicitado)
        - Inventario disponible de proveedor

        Devuelve un JSON con scores de 0-100 para:
        - disponibilidad: ¿el proveedor tiene suficiente cantidad? (0-100)
        - precio: ¿el precio es competitivo? (0-100)
        - logística: ¿puede entregar rápido? (0-100)
        - confiabilidad: historial del proveedor (0-100, estima si es desconocido)
        - compatibilidad: ¿cumple especificaciones? (0-100)

        Formato JSON exacto:
        {
          "disponibilidad": number,
          "precio": number,
          "logistica": number,
          "confiabilidad": number,
          "compatibilidad": number,
          "justificacion": string
        }"""

        prompt = f"""
        Cotización solicitada:
        - Material: {item.material_name}
        - Cantidad: {item.quantity}
        - Presupuesto por unidad: ${item.unit_price}

        Proveedor disponible:
        - Material: {inventory.material_name}
        - Cantidad: {inventory.quantity_available}
        - Precio por unidad: ${inventory.unit_price}
        - Especificaciones: {inventory.specs or "N/A"}
        """

        try:
            result = await self.ai_client.generate_json(
                prompt=prompt,
                system_instruction=system_instruction,
            )

            scores = {
                "disponibilidad": result.get("disponibilidad", 50) / 100,
                "precio": result.get("precio", 50) / 100,
                "logistica": result.get("logistica", 50) / 100,
                "confiabilidad": result.get("confiabilidad", 50) / 100,
                "compatibilidad": result.get("compatibilidad", 50) / 100,
            }

            # Promedio ponderado
            final_score = round(
                (scores["disponibilidad"] * 0.25) +
                (scores["precio"] * 0.25) +
                (scores["logistica"] * 0.20) +
                (scores["confiabilidad"] * 0.20) +
                (scores["compatibilidad"] * 0.10),
                2
            )

            breakdown = {
                **scores,
                "justificacion": result.get("justificacion", ""),
                "final_score": final_score,
            }

            return final_score, breakdown

        except Exception as e:
            logger.warning("Error en scoring con IA, usando fallback: %s", str(e))
            # Fallback a scoring simple
            simple_strategy = SimpleScoringStrategy()
            return simple_strategy.calculate(item, inventory)