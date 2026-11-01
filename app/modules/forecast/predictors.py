"""Predicción del resultado futuro de cada opción de compra.

La comparación responde "¿quién es más barato hoy?". Aquí se responde "¿qué
me va a pasar si le compro a este proveedor?": si va a cumplir, cuándo llega
el pedido y cuánto terminará costando de verdad, contando el riesgo de que
falle y haya que recomprarle a otro.

Todo es estadística sobre el historial real de órdenes, sin I/O y
determinista: las mismas entradas dan siempre las mismas cifras. La IA
(narrator.py) solo explica estas cifras; nunca las calcula.

Una "opción" es un plan para comprar el pedido completo:
- elegir un proveedor: lo que él tiene se le compra a él, y lo que le falta
  al más barato de los demás (el complemento), porque la obra necesita todo
- la mejor combinación: cada material al más conveniente
Así los costos de todas las opciones son comparables entre sí.
"""

from dataclasses import dataclass, field
from statistics import median
from typing import Protocol

# Prior de la distribución Beta: un proveedor sin historial arranca en 3/4 =
# 75 % de cumplimiento, y cada orden cerrada lo mueve hacia su tasa real.
PRIOR_SUCCESS = 3
PRIOR_FAILURE = 1
# Días que se suman en el peor caso: buscar otro proveedor y volver a pedir
REBUY_DELAY_DAYS = 3
# Recomprar de urgencia sale más caro que el precio de lista del alternativo:
# flete exprés, precio sin negociar y días de obra detenida. Sin este recargo
# un proveedor barato que nunca cumple saldría siempre "mejor".
REBUY_OVERHEAD = 0.10
# Mínimo de precios históricos para estimar una tendencia
MIN_PRICE_POINTS = 3
MIN_PRICE_SPAN_DAYS = 7


@dataclass(frozen=True)
class PricePoint:
    day: float           # días desde una fecha de referencia
    material_key: str    # nombre normalizado del material
    unit_price: float


@dataclass(frozen=True)
class ProviderHistory:
    delivered: int = 0
    rejected: int = 0                 # órdenes que el proveedor rechazó
    open_orders: int = 0              # pendientes, confirmadas o en tránsito
    orders_with_client: int = 0       # órdenes de ESTA constructora con él
    lead_times_days: tuple[float, ...] = ()
    price_points: tuple[PricePoint, ...] = ()

    @property
    def closed(self) -> int:
        return self.delivered + self.rejected


def reliability(history: ProviderHistory) -> float:
    """Probabilidad de que entregue, suavizada con un prior Beta para que
    pocas órdenes no den 0 % ni 100 %."""
    return (history.delivered + PRIOR_SUCCESS) / (history.closed + PRIOR_SUCCESS + PRIOR_FAILURE)


def confidence(history: ProviderHistory) -> str:
    if history.closed < 3:
        return "baja"
    return "media" if history.closed < 10 else "alta"


def _quantile(sorted_values: list[float], q: float) -> float:
    """Interpolación lineal entre los dos valores más cercanos."""
    position = (len(sorted_values) - 1) * q
    low = int(position)
    high = min(low + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (position - low)


def delivery_estimate(history: ProviderHistory) -> dict | None:
    """Mediana de días de entrega y rango intercuartil (p25–p75)."""
    if not history.lead_times_days:
        return None
    values = sorted(history.lead_times_days)
    return {
        "median": round(median(values), 1),
        "p25": round(_quantile(values, 0.25), 1),
        "p75": round(_quantile(values, 0.75), 1),
    }


def price_trend_pct_30d(points: tuple[PricePoint, ...]) -> float | None:
    """Cuánto cambia el precio cada 30 días, en %.

    Cada precio se divide por el promedio de su material, para que materiales
    de precios muy distintos (cemento y puntillas) se puedan mezclar en una
    sola recta de mínimos cuadrados. Solo cuentan materiales con 2 o más
    precios, porque un precio suelto no dice nada de su evolución."""
    by_material: dict[str, list[PricePoint]] = {}
    for p in points:
        if p.unit_price > 0:
            by_material.setdefault(p.material_key, []).append(p)

    xs: list[float] = []
    ys: list[float] = []
    for series in by_material.values():
        if len(series) < 2:
            continue
        mean_price = sum(p.unit_price for p in series) / len(series)
        for p in series:
            xs.append(p.day)
            ys.append(p.unit_price / mean_price)

    if len(xs) < MIN_PRICE_POINTS or max(xs) - min(xs) < MIN_PRICE_SPAN_DAYS:
        return None
    mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
    variance = sum((x - mean_x) ** 2 for x in xs)
    if variance == 0:
        return None
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / variance
    return round(slope * 30 * 100, 1)


# --- Ofertas y planes de compra ----------------------------------------------

@dataclass(frozen=True)
class Offer:
    item_id: int
    provider_org_id: int
    unit_price: float
    quantity_available: float
    subtotal: float


@dataclass
class Assignment:
    """Un material del pedido y a quién se le compra en un plan."""
    item_id: int
    material_name: str
    quantity: float
    offer: Offer


@dataclass
class PlanResult:
    key: str
    label: str
    kind: str                         # "proveedor" o "combinacion"
    provider_org_ids: list[int]
    main_provider_id: int | None
    items_from_main: int
    complement_items: int
    cost_today: float
    expected_cost: float
    success_probability: float
    confidence: str
    delivery_days: dict | None
    shortfalls: list[dict] = field(default_factory=list)
    scenarios: dict = field(default_factory=dict)


def _usable_offers(item: dict) -> list[Offer]:
    """Ofertas con precio y unidad compatible: solo esas tienen un costo
    comparable con las demás."""
    offers = []
    for o in item["offers"]:
        criteria = o.get("criteria") or {}
        if not o.get("unit_price") or not criteria.get("unidad_compatible", True):
            continue
        offers.append(Offer(
            item_id=item["item_id"], provider_org_id=o["provider_org_id"],
            unit_price=float(o["unit_price"]), quantity_available=float(o.get("quantity_available") or 0),
            subtotal=float(o.get("subtotal") or o["unit_price"] * item["quantity"]),
        ))
    return offers


def _cheapest(offers: list[Offer], exclude_provider: int | None = None) -> Offer | None:
    candidates = [o for o in offers if o.provider_org_id != exclude_provider]
    if not candidates:
        return None
    # Primero los que tienen todo el stock, luego por precio
    return min(candidates, key=lambda o: (o.quantity_available <= 0, o.unit_price))


class ForecastModel(Protocol):
    """Contrato del modelo de predicción. Hoy es estadístico; si algún día hay
    datos suficientes para entrenar un modelo, se cambia sin tocar el servicio."""

    def predict(self, comparison: dict, histories: dict[int, ProviderHistory]) -> dict: ...


class StatisticalForecastModel:
    def predict(self, comparison: dict, histories: dict[int, ProviderHistory]) -> dict:
        names = {p["provider_org_id"]: p["provider_name"] for p in comparison["providers"]}
        offers_by_item = {item["item_id"]: _usable_offers(item) for item in comparison["items"]}
        items = {item["item_id"]: item for item in comparison["items"]}
        unavailable = [items[i]["material_name"] for i, offers in offers_by_item.items() if not offers]

        def history(provider_id: int) -> ProviderHistory:
            return histories.get(provider_id, ProviderHistory())

        providers = [self._provider_profile(p, history(p["provider_org_id"]), comparison) for p in comparison["providers"]]

        plans: list[PlanResult] = []
        for provider_id, name in names.items():
            assignments, from_main = [], 0
            for item_id, offers in offers_by_item.items():
                own = next((o for o in offers if o.provider_org_id == provider_id), None)
                chosen = own or _cheapest(offers)
                if chosen is None:
                    continue
                from_main += 1 if own else 0
                assignments.append(self._assignment(items[item_id], chosen))
            if from_main == 0:
                continue  # solo ofrece con unidad incompatible o sin precio
            plans.append(self._evaluate(
                f"provider:{provider_id}", f"Comprarle a {name}", "proveedor",
                assignments, offers_by_item, history, names, main_provider_id=provider_id, items_from_main=from_main,
            ))

        combo = comparison["best_combination"]
        if combo["providers_count"] > 1:
            assignments = []
            for c in combo["items"]:
                offer = next((o for o in offers_by_item.get(c["item_id"], []) if o.provider_org_id == c["provider_org_id"]), None)
                if offer:
                    assignments.append(self._assignment(items[c["item_id"]], offer))
            if assignments:
                plans.append(self._evaluate(
                    "combination", f"Combinar {combo['providers_count']} proveedores", "combinacion",
                    assignments, offers_by_item, history, names, main_provider_id=None, items_from_main=len(assignments),
                ))

        # La mejor opción a futuro: la de menor costo esperado; a igual costo,
        # la más probable de salir bien. Se premia cubrir más materiales.
        best = min(plans, key=lambda p: (-(p.items_from_main + p.complement_items), p.expected_cost, -p.success_probability), default=None)
        recommendation = comparison.get("recommendation")
        return {
            "quotation_id": comparison["quotation_id"],
            "items_total": comparison["items_total"],
            "items_unavailable": unavailable,
            "providers": providers,
            "options": [self._plan_out(p) for p in sorted(plans, key=lambda p: p.expected_cost)],
            "best_option_key": best.key if best else None,
            "current_recommendation_key": f"provider:{recommendation['provider_org_id']}" if recommendation else None,
        }

    @staticmethod
    def _assignment(item: dict, offer: Offer) -> Assignment:
        return Assignment(item_id=item["item_id"], material_name=item["material_name"], quantity=float(item["quantity"]), offer=offer)

    @staticmethod
    def _provider_profile(provider: dict, history: ProviderHistory, comparison: dict) -> dict:
        # Prima frente al mercado: su costo contra la mediana de las ofertas de
        # los mismos materiales. Positivo = más caro que el resto.
        own, market = 0.0, 0.0
        for item in comparison["items"]:
            offers = _usable_offers(item)
            mine = next((o for o in offers if o.provider_org_id == provider["provider_org_id"]), None)
            if mine and len(offers) > 1:
                own += mine.subtotal
                market += median(o.subtotal for o in offers)
        return {
            "provider_org_id": provider["provider_org_id"],
            "provider_name": provider["provider_name"],
            "orders_closed": history.closed,
            "orders_delivered": history.delivered,
            "orders_rejected": history.rejected,
            "orders_open": history.open_orders,
            "orders_with_you": history.orders_with_client,
            "reliability": round(reliability(history), 3),
            "confidence": confidence(history),
            "delivery_days": delivery_estimate(history),
            "price_trend_pct_30d": price_trend_pct_30d(history.price_points),
            "market_premium_pct": round((own - market) / market * 100, 1) if market else None,
            "unit_mismatches": provider.get("unit_mismatches", 0),
        }

    def _evaluate(
        self, key: str, label: str, kind: str, assignments: list[Assignment],
        offers_by_item: dict[int, list[Offer]], history, names: dict[int, str],
        main_provider_id: int | None, items_from_main: int,
    ) -> PlanResult:
        provider_ids = sorted({a.offer.provider_org_id for a in assignments})
        cost_today = sum(a.offer.subtotal for a in assignments)

        # Faltantes: lo que el proveedor no tiene en stock se compra al más
        # barato de los demás, y se paga la diferencia de precio.
        shortfall_extra, shortfalls = 0.0, []
        for a in assignments:
            missing = a.quantity - a.offer.quantity_available
            if missing <= 0:
                continue
            alt = _cheapest(offers_by_item[a.item_id], exclude_provider=a.offer.provider_org_id)
            extra = max(0.0, missing * (alt.unit_price - a.offer.unit_price)) if alt else 0.0
            shortfall_extra += extra
            shortfalls.append({
                "material_name": a.material_name,
                "provider_name": names.get(a.offer.provider_org_id, ""),
                "missing_quantity": round(missing, 2),
                "alternative_provider": names.get(alt.provider_org_id) if alt else None,
                "extra_cost": round(extra, 2),
            })

        # Si un proveedor falla, sus materiales se recompran de urgencia al
        # siguiente más barato: el sobrecosto pesa según la probabilidad de
        # que falle. Sin alternativa, queda al menos el recargo de urgencia.
        success, failure_extra, worst_extra = 1.0, 0.0, 0.0
        for provider_id in provider_ids:
            p = reliability(history(provider_id))
            success *= p
            rebuy = 0.0
            for a in assignments:
                if a.offer.provider_org_id != provider_id:
                    continue
                alt = _cheapest(offers_by_item[a.item_id], exclude_provider=provider_id)
                replacement = alt.subtotal if alt else a.offer.subtotal
                rebuy += max(0.0, replacement * (1 + REBUY_OVERHEAD) - a.offer.subtotal)
            failure_extra += (1 - p) * rebuy
            worst_extra += rebuy

        estimates = [delivery_estimate(history(pid)) for pid in provider_ids]
        known = [e for e in estimates if e]
        # El pedido está completo cuando llega el último proveedor
        delivery = {
            "median": max(e["median"] for e in known),
            "p25": max(e["p25"] for e in known),
            "p75": max(e["p75"] for e in known),
        } if known else None

        base = cost_today + shortfall_extra
        expected = base + failure_extra
        levels = [confidence(history(pid)) for pid in provider_ids]
        plan_confidence = "baja" if "baja" in levels else ("media" if "media" in levels else "alta")

        return PlanResult(
            key=key, label=label, kind=kind, provider_org_ids=provider_ids, main_provider_id=main_provider_id,
            items_from_main=items_from_main, complement_items=len(assignments) - items_from_main,
            cost_today=round(cost_today, 2), expected_cost=round(expected, 2),
            success_probability=round(success, 3), confidence=plan_confidence,
            delivery_days=delivery, shortfalls=shortfalls,
            scenarios={
                "optimista": {"cost": round(base, 2), "days": delivery["p25"] if delivery else None},
                "probable": {"cost": round(expected, 2), "days": delivery["median"] if delivery else None},
                "pesimista": {
                    "cost": round(base + worst_extra, 2),
                    "days": round(delivery["p75"] + REBUY_DELAY_DAYS, 1) if delivery else None,
                },
            },
        )

    @staticmethod
    def _plan_out(plan: PlanResult) -> dict:
        return {
            "key": plan.key,
            "label": plan.label,
            "kind": plan.kind,
            "provider_org_ids": plan.provider_org_ids,
            "main_provider_id": plan.main_provider_id,
            "items_from_main": plan.items_from_main,
            "complement_items": plan.complement_items,
            "cost_today": plan.cost_today,
            "expected_cost": plan.expected_cost,
            "success_probability": plan.success_probability,
            "confidence": plan.confidence,
            "delivery_days": plan.delivery_days,
            "shortfalls": plan.shortfalls,
            "scenarios": plan.scenarios,
        }
