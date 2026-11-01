"""Explicación en lenguaje natural de la predicción.

Las cifras las calcula predictors.py; aquí solo se cuentan. Gemini recibe los
números ya calculados y redacta qué le pasará a la constructora con cada
opción. La pantalla muestra siempre los números del backend, nunca los que
escriba el modelo, así que una cifra inventada no llega al usuario.

Si no hay API key o la IA falla, TemplateNarrator arma el mismo contenido con
plantillas: la predicción nunca depende de que la IA responda.
"""

import json
from dataclasses import dataclass, field
from typing import Protocol

from app.core.logging import get_logger

logger = get_logger(__name__)

MAX_TEXT = 400
MAX_RISKS = 4

_SYSTEM_INSTRUCTION = """\
Eres un asesor de compras de materiales de construcción en Colombia. Una \
constructora va a elegir a quién comprarle un pedido. Recibes, para cada opción \
de compra, cifras YA CALCULADAS con el historial real de los proveedores:
- costo_hoy: lo que cuesta hoy el pedido completo con esa opción (COP)
- costo_esperado: el costo contando el riesgo de que un proveedor falle y haya \
que recomprarle a otro (COP)
- probabilidad_exito: probabilidad de que todos los proveedores de la opción cumplan
- dias_entrega: mediana y rango de días de entrega, o null si no hay historial
- faltantes: materiales sin stock suficiente
- confianza: "baja", "media" o "alta" según cuánto historial hay
- proveedores: cumplimiento, rechazos, tendencia de precio (% cada 30 días) y \
prima frente al mercado (%)

Explica qué le pasará a la constructora en el futuro si elige cada opción y cuál \
le conviene más. Reglas:
- Usa SOLO las cifras recibidas. No inventes datos, proveedores ni porcentajes.
- Si la confianza es "baja", dilo: hay poco historial y la estimación puede cambiar.
- Si una tendencia de precio es positiva, advierte que sus precios vienen subiendo.
- Escribe en español, frases cortas, en segunda persona ("recibirías", "pagarías").

Devuelve ÚNICAMENTE un JSON con esta forma exacta:
{
  "resumen": string,
  "opciones": [
    {"key": string, "que_pasara": string, "riesgos": [string], "consejo": string}
  ]
}
Incluye una entrada por cada opción recibida, con su mismo "key".
"""


@dataclass
class OptionNarrative:
    que_pasara: str
    riesgos: list[str] = field(default_factory=list)
    consejo: str = ""


@dataclass
class Narrative:
    source: str  # "ia" o "plantilla"
    summary: str
    options: dict[str, OptionNarrative]


class ForecastNarrator(Protocol):
    async def narrate(self, forecast: dict) -> Narrative: ...


def format_cop(value: float) -> str:
    return "$" + f"{value:,.0f}".replace(",", ".")


def _pct(value: float) -> str:
    return f"{value * 100:.0f} %"


def _days(delivery: dict | None) -> str:
    if not delivery:
        return "sin historial de entregas"
    return f"unos {delivery['median']:g} días (entre {delivery['p25']:g} y {delivery['p75']:g})"


class TemplateNarrator:
    """Respaldo determinista: las mismas ideas, armadas con plantillas."""

    async def narrate(self, forecast: dict) -> Narrative:
        return self.build(forecast)

    def build(self, forecast: dict) -> Narrative:
        providers = {p["provider_org_id"]: p for p in forecast["providers"]}
        options = {}
        for option in forecast["options"]:
            risks = []
            if option["confidence"] == "baja":
                risks.append("Poco historial: la estimación puede cambiar con las próximas órdenes.")
            for s in option["shortfalls"][:2]:
                risks.append(
                    f"{s['provider_name']} no tiene stock suficiente de {s['material_name']} "
                    f"(faltan {s['missing_quantity']:g})."
                )
            for pid in option["provider_org_ids"]:
                p = providers.get(pid)
                if p and p["price_trend_pct_30d"] and p["price_trend_pct_30d"] > 0:
                    risks.append(f"Los precios de {p['provider_name']} vienen subiendo {p['price_trend_pct_30d']:g} % cada mes.")
                if p and p["orders_rejected"]:
                    risks.append(f"{p['provider_name']} ha rechazado {p['orders_rejected']} orden(es).")

            extra = option["expected_cost"] - option["cost_today"]
            text = (
                f"Pagarías {format_cop(option['cost_today'])} hoy; contando el riesgo, el costo esperado es "
                f"{format_cop(option['expected_cost'])}. Probabilidad de que todo llegue: "
                f"{_pct(option['success_probability'])}. Entrega: {_days(option['delivery_days'])}."
            )
            if option["complement_items"]:
                text += f" {option['complement_items']} material(es) se compran a otro proveedor."
            advice = (
                "Opción segura: el riesgo casi no cambia el costo." if extra < option["cost_today"] * 0.02
                else "Considera el sobrecosto si el proveedor falla antes de decidir solo por precio."
            )
            options[option["key"]] = OptionNarrative(text, risks[:MAX_RISKS], advice)

        best = next((o for o in forecast["options"] if o["key"] == forecast["best_option_key"]), None)
        if best:
            summary = (
                f"La mejor opción a futuro es {best['label'][0].lower() + best['label'][1:]}: costo esperado "
                f"{format_cop(best['expected_cost'])} y {_pct(best['success_probability'])} de probabilidad de cumplir."
            )
            if forecast["current_recommendation_key"] and forecast["current_recommendation_key"] != best["key"]:
                summary += " Es distinta de la recomendación de hoy porque considera el riesgo y el historial."
        else:
            summary = "No hay ofertas suficientes para predecir el resultado de la compra."
        return Narrative(source="plantilla", summary=summary, options=options)


class AIForecastNarrator:
    """Adaptador sobre AIClient: Gemini redacta, el código valida."""

    def __init__(self, ai_client, fallback: TemplateNarrator | None = None):
        self.ai_client = ai_client
        self.fallback = fallback or TemplateNarrator()

    async def narrate(self, forecast: dict) -> Narrative:
        template = self.fallback.build(forecast)
        if not forecast["options"]:
            return template
        try:
            result = await self.ai_client.generate_json(
                prompt=json.dumps(self._payload(forecast), ensure_ascii=False),
                system_instruction=_SYSTEM_INSTRUCTION,
                max_retries=2,
            )
        except Exception as e:  # la explicación es una mejora; las cifras ya están
            logger.warning("Predicción sin IA, se usan plantillas: %s", e)
            return template

        result = result if isinstance(result, dict) else {}
        options = dict(template.options)  # lo que la IA no cubra queda con plantilla
        produced = 0
        for entry in result.get("opciones") or []:
            if not isinstance(entry, dict) or entry.get("key") not in options:
                continue  # opción inventada: se ignora
            text = str(entry.get("que_pasara") or "").strip()
            if not text:
                continue
            risks = [str(r).strip()[:MAX_TEXT] for r in (entry.get("riesgos") or []) if str(r).strip()]
            options[entry["key"]] = OptionNarrative(
                que_pasara=text[:MAX_TEXT], riesgos=risks[:MAX_RISKS],
                consejo=str(entry.get("consejo") or "").strip()[:MAX_TEXT],
            )
            produced += 1

        summary = str(result.get("resumen") or "").strip()[:MAX_TEXT * 2]
        if not produced and not summary:
            return template
        return Narrative(source="ia", summary=summary or template.summary, options=options)

    @staticmethod
    def _payload(forecast: dict) -> dict:
        names = {p["provider_org_id"]: p["provider_name"] for p in forecast["providers"]}
        return {
            "materiales_del_pedido": forecast["items_total"],
            "materiales_sin_ofertas": forecast["items_unavailable"],
            "mejor_opcion_calculada": forecast["best_option_key"],
            "recomendacion_de_hoy": forecast["current_recommendation_key"],
            "opciones": [
                {
                    "key": o["key"],
                    "nombre": o["label"],
                    "proveedores": [names.get(pid, str(pid)) for pid in o["provider_org_ids"]],
                    "materiales_del_principal": o["items_from_main"],
                    "materiales_de_complemento": o["complement_items"],
                    "costo_hoy": o["cost_today"],
                    "costo_esperado": o["expected_cost"],
                    "probabilidad_exito": o["success_probability"],
                    "dias_entrega": o["delivery_days"],
                    "faltantes": o["shortfalls"],
                    "confianza": o["confidence"],
                    "escenarios": o["scenarios"],
                }
                for o in forecast["options"]
            ],
            "proveedores": [
                {
                    "nombre": p["provider_name"],
                    "ordenes_cerradas": p["orders_closed"],
                    "entregadas": p["orders_delivered"],
                    "rechazadas": p["orders_rejected"],
                    "ordenes_contigo": p["orders_with_you"],
                    "cumplimiento": p["reliability"],
                    "tendencia_precio_pct_30d": p["price_trend_pct_30d"],
                    "prima_vs_mercado_pct": p["market_premium_pct"],
                }
                for p in forecast["providers"]
            ],
        }
