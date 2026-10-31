"""Cómo se calcula la similitud entre materiales pedidos y productos.

MatchingService depende de la abstracción MaterialMatcher, no de cómo se
calcula (inversión de dependencias): puede ser en el mismo proceso
(LocalMaterialMatcher) o en el microservicio gRPC (GrpcMaterialMatcher, en
app/infrastructure/matching_engine_client.py). Las dos implementaciones son
intercambiables y dan el mismo resultado.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Protocol

from app.core.logging import get_logger
from app.modules.matching.text_matching import material_similarity, specs_conflict

logger = get_logger(__name__)


@dataclass(frozen=True)
class PairScore:
    similarity: float
    specs_conflict: bool


NO_MATCH = PairScore(similarity=0.0, specs_conflict=False)

# (id, nombre) de un material pedido o de un producto
NamedItem = tuple[int, str]
Similarities = dict[tuple[int, int], PairScore]


class MaterialMatcher(Protocol):
    async def compute(self, items: list[NamedItem], products: list[NamedItem]) -> Similarities:
        """Similitud de cada par (item_id, product_id). Los pares ausentes valen NO_MATCH."""
        ...


def compute_similarities(items: list[NamedItem], products: list[NamedItem]) -> Similarities:
    """Cálculo puro y síncrono (CPU). Lo usan el matcher local y el servidor gRPC."""
    result: Similarities = {}
    for item_id, item_name in items:
        for product_id, product_name in products:
            similarity = material_similarity(item_name, product_name)
            conflict = specs_conflict(item_name, product_name)
            if similarity > 0 or conflict:
                result[(item_id, product_id)] = PairScore(similarity, conflict)
    return result


class LocalMaterialMatcher:
    """Calcula en el mismo proceso, pero en un hilo aparte: es trabajo de CPU
    y no debe bloquear el event loop que atiende las demás peticiones."""

    async def compute(self, items: list[NamedItem], products: list[NamedItem]) -> Similarities:
        return await asyncio.to_thread(compute_similarities, items, products)


class ResilientMatcher:
    """Usa el matcher principal (gRPC) y, si falla o no responde, cae al
    local: la comparación sigue funcionando aunque el motor esté caído."""

    def __init__(self, primary: MaterialMatcher, fallback: MaterialMatcher, on_fallback=None):
        self.primary = primary
        self.fallback = fallback
        self.on_fallback = on_fallback

    async def compute(self, items: list[NamedItem], products: list[NamedItem]) -> Similarities:
        try:
            return await self.primary.compute(items, products)
        except Exception as e:  # cualquier fallo del motor remoto
            logger.warning("Motor de comparación no disponible, se calcula localmente: %s", e)
            if self.on_fallback:
                self.on_fallback()
            started = time.perf_counter()
            result = await self.fallback.compute(items, products)
            logger.info("Comparación local de respaldo en %.0f ms", (time.perf_counter() - started) * 1000)
            return result
