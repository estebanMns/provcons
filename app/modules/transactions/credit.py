"""¿Le conviene al proveedor darle cuotas a esta constructora?

Funciones puras, sin base de datos ni IA, para poder probarlas con números
fijos. La app no registra pagos, así que "paga bien" se mide por cómo cumple
la constructora con sus órdenes: cuántas recibió y cuántas canceló ella.

- credit_score: probabilidad de que cumpla, con el mismo prior Beta que la
  predicción de proveedores (sin historial arranca en 75 %).
- max_installments: cuántas cuotas como máximo, según el puntaje, la confianza
  y el monto (sin cuotas diminutas).
- installment_plan: valor de cada cuota con amortización francesa.
- verdict: si un número de cuotas es conveniente, con riesgo o no conveniente.
"""

from dataclasses import dataclass

from app.modules.forecast.predictors import PRIOR_FAILURE, PRIOR_SUCCESS, confidence

MAX_INSTALLMENTS = 12
# Una cuota por debajo de esto no compensa el trabajo de cobrarla
MIN_INSTALLMENT_COP = 200_000
# Opciones que se muestran al proveedor
INSTALLMENT_OPTIONS = (1, 2, 3, 4, 6, 9, 12)
# Escalones de cuotas máximas y el puntaje que pide cada uno
LEVELS = (1, 3, 6, 12)
_TIERS = ((0.85, 12), (0.70, 6), (0.55, 3))

CONVENIENTE, CON_RIESGO, NO_CONVENIENTE = "conveniente", "con_riesgo", "no_conveniente"


@dataclass(frozen=True)
class ClientHistory:
    """Historial de la constructora en toda la plataforma (sin contar la orden
    que se está evaluando)."""
    delivered: int = 0              # órdenes que recibió
    cancelled_by_client: int = 0    # órdenes que canceló ella
    open_orders: int = 0            # pendientes, confirmadas o en tránsito
    total_purchased: float = 0.0    # suma de las órdenes recibidas (COP)
    orders_with_provider: int = 0   # órdenes con ESTE proveedor
    delivered_with_provider: int = 0
    months_on_platform: float = 0.0

    @property
    def closed(self) -> int:
        return self.delivered + self.cancelled_by_client


def credit_score(history: ClientHistory) -> float:
    return (history.delivered + PRIOR_SUCCESS) / (history.closed + PRIOR_SUCCESS + PRIOR_FAILURE)


def credit_confidence(history: ClientHistory) -> str:
    # Mismos umbrales que la predicción: solo mira cuántas órdenes cerró
    return confidence(history)  # type: ignore[arg-type]


def _amount_cap(amount: float) -> int:
    return max(1, int(amount // MIN_INSTALLMENT_COP))


def max_installments(score: float, confidence_level: str, amount: float) -> int:
    level = next((n for threshold, n in _TIERS if score >= threshold), 1)
    if confidence_level == "baja":  # poco historial: un escalón más prudente
        level = LEVELS[max(0, LEVELS.index(level) - 1)]
    return max(1, min(level, _amount_cap(amount), MAX_INSTALLMENTS))


def verdict(installments: int, maximum: int) -> str:
    """Hasta el máximo recomendado es conveniente; hasta el escalón siguiente,
    con riesgo; más allá, no conveniente."""
    if installments <= maximum:
        return CONVENIENTE
    next_level = next((n for n in LEVELS if n > maximum), MAX_INSTALLMENTS)
    return CON_RIESGO if installments <= next_level else NO_CONVENIENTE


def installment_plan(amount: float, installments: int, monthly_rate_pct: float) -> dict:
    """Cuota fija (amortización francesa): A = P·r / (1 − (1 + r)^−n).
    Una sola cuota es pago de contado: sin interés."""
    rate = monthly_rate_pct / 100 if installments > 1 else 0.0
    if rate == 0:
        payment = amount / installments
    else:
        payment = amount * rate / (1 - (1 + rate) ** -installments)
    total = payment * installments
    return {
        "installments": installments,
        "monthly_rate_pct": round(rate * 100, 4),
        "installment_amount": round(payment, 2),
        "financed_total": round(total, 2),
        "interest": round(total - amount, 2),
    }


def _pct(value: float) -> str:
    return f"{value * 100:.0f} %"


def _reasons(history: ClientHistory, score: float, amount: float, maximum: int) -> list[str]:
    reasons = []
    if history.closed == 0:
        reasons.append("No tiene órdenes cerradas en ProvCons: la evaluación parte de un supuesto prudente.")
    else:
        reasons.append(
            f"Recibió {history.delivered} de {history.closed} órdenes cerradas ({_pct(score)} de cumplimiento estimado)."
        )
    if history.cancelled_by_client:
        reasons.append(f"Canceló {history.cancelled_by_client} orden(es) por su cuenta.")
    if history.orders_with_provider:
        reasons.append(
            f"Contigo ha hecho {history.orders_with_provider} orden(es) más; {history.delivered_with_provider} entregada(s)."
        )
    if history.months_on_platform < 1:
        reasons.append("Lleva menos de un mes en la plataforma.")
    if _amount_cap(amount) == maximum and maximum < MAX_INSTALLMENTS:
        reasons.append(f"Con este monto, más de {maximum} cuota(s) quedarían por debajo de $200.000 cada una.")
    return reasons


def evaluate(amount: float, history: ClientHistory) -> dict:
    score = credit_score(history)
    level = credit_confidence(history)
    maximum = max_installments(score, level, amount)
    return {
        "score": round(score, 4),
        "confidence": level,
        "max_installments": maximum,
        "reasons": _reasons(history, score, amount, maximum),
        "history": {
            "orders_delivered": history.delivered,
            "orders_cancelled_by_client": history.cancelled_by_client,
            "open_orders": history.open_orders,
            "total_purchased": round(history.total_purchased, 2),
            "orders_with_you": history.orders_with_provider,
            "delivered_with_you": history.delivered_with_provider,
            "months_on_platform": round(history.months_on_platform, 1),
        },
        "options": [
            {"installments": n, "verdict": verdict(n, maximum)}
            for n in INSTALLMENT_OPTIONS
        ],
    }
