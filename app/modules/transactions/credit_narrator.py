"""Explicación de la evaluación de crédito para el proveedor.

Las cifras y los veredictos los calcula credit.py. Gemini solo redacta por qué
conviene o no dar cuotas; la pantalla muestra siempre los números del backend.
Si no hay API key o la IA falla, se usa la plantilla.
"""

import json
from dataclasses import dataclass
from typing import Protocol

from app.core.logging import get_logger
from app.modules.forecast.narrator import format_cop

logger = get_logger(__name__)

MAX_TEXT = 400

_SYSTEM_INSTRUCTION = """\
Eres un asesor de crédito comercial para proveedores de materiales de \
construcción en Colombia. Un proveedor va a aceptar un pedido de una \
constructora y debe decidir si le da cuotas y cuántas. Recibes cifras YA \
CALCULADAS con el historial real de la constructora en la plataforma:
- monto: valor del pedido (COP)
- cumplimiento: probabilidad estimada de que la constructora cumpla (0 a 1)
- confianza: "baja", "media" o "alta" según cuántas órdenes ha cerrado
- maximo_cuotas_recomendado: tope calculado de cuotas
- historial: órdenes recibidas, canceladas por ella, abiertas, total comprado, \
órdenes con este proveedor y meses en la plataforma
- razones: hechos ya calculados

La plataforma NO registra pagos: el cumplimiento se mide por órdenes recibidas \
y canceladas. No digas que la constructora "paga a tiempo" ni lo contrario.

Explica al proveedor si le conviene dar cuotas y por qué. Reglas:
- Usa SOLO las cifras recibidas. No inventes datos ni porcentajes.
- No recomiendes más cuotas que maximo_cuotas_recomendado.
- Si la confianza es "baja", dilo: hay poco historial.
- Español, frases cortas, en segunda persona ("te conviene", "podrías").

Devuelve ÚNICAMENTE un JSON con esta forma exacta:
{"resumen": string, "consejo": string}
"""


@dataclass
class CreditNarrative:
    source: str  # "ia" o "plantilla"
    summary: str
    advice: str


class CreditNarrator(Protocol):
    async def narrate(self, evaluation: dict) -> CreditNarrative: ...


class TemplateCreditNarrator:
    async def narrate(self, evaluation: dict) -> CreditNarrative:
        return self.build(evaluation)

    @staticmethod
    def build(evaluation: dict) -> CreditNarrative:
        name = evaluation.get("constructora_name") or "La constructora"
        maximum = evaluation["max_installments"]
        summary = (
            f"{name} tiene un cumplimiento estimado de {evaluation['score'] * 100:.0f} % "
            f"(confianza {evaluation['confidence']}). Para un pedido de {format_cop(evaluation['amount'])}, "
            f"te recomendamos hasta {maximum} cuota{'s' if maximum != 1 else ''}."
        )
        if maximum == 1:
            advice = "Te conviene pedir pago de contado o un anticipo antes de despachar."
        elif evaluation["confidence"] == "baja":
            advice = f"Hay poco historial: si das cuotas, no pases de {maximum} y pide la primera antes de despachar."
        else:
            advice = f"Dar hasta {maximum} cuotas es razonable; más allá, el riesgo de no cobrar aumenta."
        return CreditNarrative(source="plantilla", summary=summary, advice=advice)


class AICreditNarrator:
    """Adaptador sobre AIClient: Gemini redacta, el código valida."""

    def __init__(self, ai_client, fallback: TemplateCreditNarrator | None = None):
        self.ai_client = ai_client
        self.fallback = fallback or TemplateCreditNarrator()

    async def narrate(self, evaluation: dict) -> CreditNarrative:
        template = self.fallback.build(evaluation)
        try:
            result = await self.ai_client.generate_json(
                prompt=json.dumps(self._payload(evaluation), ensure_ascii=False),
                system_instruction=_SYSTEM_INSTRUCTION,
                max_retries=2,
            )
        except Exception as e:  # la explicación es una mejora; las cifras ya están
            logger.warning("Evaluación de crédito sin IA, se usa la plantilla: %s", e)
            return template

        result = result if isinstance(result, dict) else {}
        summary = str(result.get("resumen") or "").strip()[:MAX_TEXT]
        advice = str(result.get("consejo") or "").strip()[:MAX_TEXT]
        if not summary and not advice:
            return template
        return CreditNarrative(source="ia", summary=summary or template.summary, advice=advice or template.advice)

    @staticmethod
    def _payload(evaluation: dict) -> dict:
        return {
            "constructora": evaluation.get("constructora_name"),
            "monto": evaluation["amount"],
            "cumplimiento": evaluation["score"],
            "confianza": evaluation["confidence"],
            "maximo_cuotas_recomendado": evaluation["max_installments"],
            "historial": evaluation["history"],
            "razones": evaluation["reasons"],
        }
