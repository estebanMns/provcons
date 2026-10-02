from app.infrastructure.ai_client import AIClient
from app.core.logging import get_logger

logger = get_logger(__name__)

_SYSTEM_INSTRUCTION = """\
Eres un asistente que extrae información de materiales de construcción desde \
texto de cotizaciones o catálogos de proveedores (español, Colombia).

Devuelve ÚNICAMENTE un JSON con esta forma exacta, sin texto adicional:
{
  "items": [
    {
      "material_name": string,      // nombre normalizado del material, en minúsculas
      "quantity_available": number, // SOLO el número, sin unidad ni texto
      "unit": string,                // unidad separada: "bulto", "kg", "m3", "unidad", etc.
      "unit_price": number,          // precio por unidad, SOLO número, sin símbolo de moneda
      "specs": object                 // cualquier detalle técnico adicional (resistencia, calibre, etc.), o {} si no hay
    }
  ]
}

Si no puedes determinar un valor con certeza, usa null en ese campo — nunca inventes datos.
"""


class DocumentNormalizer:
    """Convierte texto crudo (extraído de un PDF, Excel o imagen) en filas
    estructuradas, listas para guardarse como ProviderInventoryItem."""

    def __init__(self, ai_client: AIClient):
        self.ai_client = ai_client

    async def normalize_inventory_text(self, raw_text: str) -> list[dict]:
        logger.info("Normalizando texto de inventario (%s caracteres)", len(raw_text))

        result = await self.ai_client.generate_json(
            prompt=f"Texto a procesar:\n\n{raw_text}",
            system_instruction=_SYSTEM_INSTRUCTION,
        )

        items = result.get("items", [])
        logger.info("Normalización completa: %s ítems extraídos", len(items))
        return items