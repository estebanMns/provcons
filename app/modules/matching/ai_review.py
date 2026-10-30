"""Revisión con IA de los productos del inventario de los proveedores.

La comparación por texto (text_matching) es rápida y explicable, pero no
entiende sinónimos: "acero de refuerzo 3/8" y "varilla corrugada 3/8" no
comparten palabras. Aquí Gemini revisa el catálogo de los proveedores contra
los materiales pedidos y dice, producto por producto, si es el mismo material.

Reglas de diseño:
- una sola llamada a la IA por cotización (no una por producto)
- si la IA falla, el matching sigue funcionando solo con la comparación por texto
- la IA no puede saltarse la regla de medidas (specs_conflict): eso lo decide
  el código, no el modelo
"""

import json
from dataclasses import dataclass

from app.infrastructure.ai_client import AIClient
from app.modules.matching.models import QuotationItem
from app.modules.matching.text_matching import normalize_text
from app.modules.documents_ai.models import ProviderInventoryItem
from app.core.logging import get_logger

logger = get_logger(__name__)

# Con qué confianza mínima se acepta lo que dice la IA
ACCEPT_CONFIDENCE = 0.6
VETO_CONFIDENCE = 0.7
# Tope de productos distintos que se envían en una sola llamada
MAX_CATALOG_PRODUCTS = 400

_SYSTEM_INSTRUCTION = """\
Eres un experto en compras de materiales de construcción en Colombia.
Recibes materiales pedidos por una constructora y el catálogo de productos de \
varios proveedores. Para cada material pedido decide qué productos del catálogo \
son EL MISMO material, es decir, que la constructora podría comprar en su lugar.

Criterios:
- Considera sinónimos y nombres comerciales (ej. "acero de refuerzo" = "varilla corrugada", \
"bloque de concreto" = "bloque de cemento", "arena de río" = "arena lavada de río").
- Si ambos indican una medida (diámetro, dimensiones, calibre, resistencia, peso de \
presentación) y es distinta, NO son equivalentes.
- Un producto más específico que el pedido sí puede ser equivalente si no contradice \
nada de lo pedido (ej. pedido "cemento gris", producto "cemento gris uso general 50 kg").
- Materiales distintos no son equivalentes aunque compartan palabras \
(ej. "cemento blanco" no es "cemento gris", "alambre negro" no es "alambre de púas").

Devuelve ÚNICAMENTE un JSON con esta forma exacta:
{
  "revisiones": [
    {
      "item_id": number,
      "productos": [
        {"ref": string, "equivalente": boolean, "confianza": number, "motivo": string}
      ]
    }
  ]
}

- Para CADA material pedido recorre el catálogo COMPLETO e incluye TODOS sus \
productos equivalentes, aunque el nombre no se parezca (sinónimos).
- "candidatos_por_texto" son solo los productos que un buscador por palabras ya \
encontró: puede estar vacío o incompleto, justamente porque no reconoce sinónimos. \
Nunca te limites a esa lista.
- Incluye además, con "equivalente": false, cada producto de "candidatos_por_texto" \
que NO sea equivalente.
- "confianza" va de 0 a 1. "motivo" es una frase corta en español.
- Usa solo refs que existan en el catálogo; nunca inventes productos.
"""


@dataclass(frozen=True)
class ProductReview:
    equivalente: bool
    confianza: float
    motivo: str


@dataclass
class ReviewResult:
    status: str  # "ok", "failed" o "disabled"
    reviews: dict[tuple[int, int], ProductReview]  # (item_id, inventory_id) -> revisión
    products_reviewed: int = 0
    error: str | None = None


class AIProductReviewer:
    def __init__(self, ai_client: AIClient):
        self.ai_client = ai_client

    async def review(
        self,
        items: list[QuotationItem],
        products: list[ProviderInventoryItem],
        lexical_candidates: dict[int, list[ProviderInventoryItem]],
    ) -> ReviewResult:
        # Los proveedores repiten nombres (o el mismo proveedor importó dos
        # veces): a la IA se le manda cada nombre una sola vez y la respuesta
        # se aplica a todas las filas con ese nombre.
        refs: dict[str, str] = {}             # nombre normalizado -> ref
        rows_by_ref: dict[str, list[ProviderInventoryItem]] = {}
        catalog = []
        for product in products:
            key = normalize_text(product.material_name)
            if key not in refs:
                if len(refs) >= MAX_CATALOG_PRODUCTS:
                    continue
                refs[key] = f"P{len(refs) + 1}"
                catalog.append({"ref": refs[key], "nombre": product.material_name, "unidad": product.unit})
                rows_by_ref[refs[key]] = []
            rows_by_ref[refs[key]].append(product)
        if len(refs) >= MAX_CATALOG_PRODUCTS:
            logger.warning("Catálogo recortado a %s productos para la revisión con IA", MAX_CATALOG_PRODUCTS)

        if not catalog or not items:
            return ReviewResult(status="ok", reviews={}, products_reviewed=0)

        payload = {
            "materiales_pedidos": [
                {
                    "item_id": item.id,
                    "nombre": item.material_name,
                    "cantidad": item.quantity,
                    "unidad": item.unit,
                    "candidatos_por_texto": sorted({
                        refs[normalize_text(p.material_name)]
                        for p in lexical_candidates.get(item.id, [])
                        if normalize_text(p.material_name) in refs
                    }),
                }
                for item in items
            ],
            "catalogo": catalog,
        }

        try:
            result = await self.ai_client.generate_json(
                prompt=json.dumps(payload, ensure_ascii=False),
                system_instruction=_SYSTEM_INSTRUCTION,
                max_retries=2,
            )
        except Exception as e:  # la IA es una mejora, no un requisito
            logger.warning("Revisión con IA no disponible, se usa solo la comparación por texto: %s", e)
            return ReviewResult(status="failed", reviews={}, error=str(e))

        item_ids = {item.id for item in items}
        reviews: dict[tuple[int, int], ProductReview] = {}
        for entry in (result or {}).get("revisiones", []) or []:
            item_id = entry.get("item_id") if isinstance(entry, dict) else None
            if item_id not in item_ids:
                continue
            for verdict in entry.get("productos", []) or []:
                rows = rows_by_ref.get(str(verdict.get("ref")))
                if not rows:
                    continue  # ref inventada o mal escrita: se ignora
                try:
                    confianza = min(max(float(verdict.get("confianza", 0)), 0.0), 1.0)
                except (TypeError, ValueError):
                    continue
                review = ProductReview(
                    equivalente=bool(verdict.get("equivalente")),
                    confianza=round(confianza, 3),
                    motivo=str(verdict.get("motivo") or "")[:200],
                )
                for row in rows:
                    reviews[(item_id, row.id)] = review

        logger.info("Revisión con IA: %s productos de catálogo, %s veredictos", len(catalog), len(reviews))
        return ReviewResult(status="ok", reviews=reviews, products_reviewed=len(catalog))


def decide_similarity(
    lexical: float, conflict: bool, review: ProductReview | None, threshold: float,
) -> tuple[float | None, str]:
    """Combina la comparación por texto con la revisión de la IA.
    Devuelve (similitud, método) o (None, motivo) si no es el mismo material."""
    if conflict:
        return None, "medidas_distintas"
    if review is not None:
        if review.equivalente and review.confianza >= ACCEPT_CONFIDENCE:
            return max(lexical, review.confianza), "ia" if lexical < threshold else "texto+ia"
        if not review.equivalente and review.confianza >= VETO_CONFIDENCE:
            return None, "descartado_por_ia"
    if lexical >= threshold:
        return lexical, "texto"
    return None, "sin_coincidencia"
