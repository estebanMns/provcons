"""Compara proveedores entre sí para una cotización completa.

El scoring califica cada oferta por separado; aquí se responde la pregunta
que le importa a la constructora: ¿a quién le compro?
- ranking de proveedores: cuánto del pedido cubren, a qué costo total y en
  cuántos materiales son los más baratos
- la recomendación (el mejor proveedor único)
- la mejor combinación: comprar cada material al más conveniente, y cuánto
  se ahorraría frente a la recomendación
"""

from collections import defaultdict
from dataclasses import dataclass
from app.modules.matching.models import QuotationItem, Match
from app.modules.documents_ai.models import ProviderInventoryItem


@dataclass(frozen=True)
class ScoredOffer:
    item: QuotationItem
    inventory: ProviderInventoryItem
    match: Match


def format_cop(value: float) -> str:
    return "$" + f"{value:,.0f}".replace(",", ".")


def _offer_out(offer: ScoredOffer, provider_names: dict[int, str], cheapest_id: int | None, best_id: int | None) -> dict:
    breakdown = offer.match.criteria_breakdown
    return {
        "match_id": offer.match.id,
        "provider_org_id": offer.match.provider_org_id,
        "provider_name": provider_names.get(offer.match.provider_org_id, f"Proveedor {offer.match.provider_org_id}"),
        "inventory_id": offer.inventory.id,
        "material_name": offer.inventory.material_name,
        "unit": offer.inventory.unit,
        "unit_price": offer.inventory.unit_price,
        "quantity_available": offer.inventory.quantity_available,
        "subtotal": breakdown.get("subtotal"),
        "score": offer.match.score,
        "criteria": breakdown,
        "is_cheapest": offer.match.id == cheapest_id,
        "is_best": offer.match.id == best_id,
    }


def _cheapest(offers: list[ScoredOffer]) -> ScoredOffer | None:
    priced = [o for o in offers if o.inventory.unit_price and o.match.criteria_breakdown.get("unidad_compatible", True)]
    return min(priced, key=lambda o: o.inventory.unit_price) if priced else None


def _provider_justification(p: dict, items_total: int) -> str:
    parts = [f"Cubre {p['items_covered']} de {items_total} materiales"]
    if p["items_covered"]:
        if p["items_full_stock"] == p["items_covered"]:
            parts[0] += ", todos con stock suficiente"
        else:
            parts[0] += f", {p['items_full_stock']} con stock suficiente"
    if p["cheapest_items"]:
        parts.append(f"es el más económico en {p['cheapest_items']}")
    if p["total_cost"]:
        parts.append(f"costo estimado {format_cop(p['total_cost'])}")
    if p["unit_mismatches"]:
        parts.append(f"revisa la unidad en {p['unit_mismatches']} material(es)")
    return "; ".join(parts) + "."


def build_comparison(
    items: list[QuotationItem], offers: list[ScoredOffer], provider_names: dict[int, str],
) -> dict:
    offers_by_item: dict[int, list[ScoredOffer]] = defaultdict(list)
    for offer in offers:
        offers_by_item[offer.item.id].append(offer)

    items_out = []
    combination = []
    cheapest_count: dict[int, int] = defaultdict(int)

    for item in items:
        item_offers = sorted(offers_by_item.get(item.id, []), key=lambda o: -o.match.score)
        cheapest = _cheapest(item_offers)
        best = item_offers[0] if item_offers else None
        if cheapest:
            cheapest_count[cheapest.match.provider_org_id] += 1

        # Para la mejor combinación se prefiere el más barato que tenga todo el
        # stock; si nadie lo tiene, el más barato a secas.
        with_stock = [o for o in item_offers if o.match.criteria_breakdown.get("stock_suficiente")]
        chosen = _cheapest(with_stock) or cheapest
        if chosen:
            combination.append({
                "item_id": item.id,
                "material_name": item.material_name,
                "provider_org_id": chosen.match.provider_org_id,
                "provider_name": provider_names.get(chosen.match.provider_org_id, f"Proveedor {chosen.match.provider_org_id}"),
                "match_id": chosen.match.id,
                "unit_price": chosen.inventory.unit_price,
                "subtotal": chosen.match.criteria_breakdown.get("subtotal"),
            })

        items_out.append({
            "item_id": item.id,
            "material_name": item.material_name,
            "quantity": item.quantity,
            "unit": item.unit,
            "budget_unit_price": item.unit_price,
            "offers": [
                _offer_out(o, provider_names, cheapest.match.id if cheapest else None, best.match.id if best else None)
                for o in item_offers
            ],
        })

    providers: dict[int, dict] = {}
    for offer in offers:
        org_id = offer.match.provider_org_id
        p = providers.setdefault(org_id, {
            "provider_org_id": org_id,
            "provider_name": provider_names.get(org_id, f"Proveedor {org_id}"),
            "items_covered": 0, "items_full_stock": 0, "unit_mismatches": 0,
            "total_cost": 0.0, "score_sum": 0.0, "match_ids": [], "item_ids": set(),
        })
        breakdown = offer.match.criteria_breakdown
        p["items_covered"] += 1
        p["item_ids"].add(offer.item.id)
        p["items_full_stock"] += 1 if breakdown.get("stock_suficiente") else 0
        p["unit_mismatches"] += 0 if breakdown.get("unidad_compatible", True) else 1
        p["total_cost"] += breakdown.get("subtotal") or 0
        p["score_sum"] += offer.match.score
        p["match_ids"].append(offer.match.id)

    items_total = len(items)
    ranking = []
    for p in providers.values():
        # Promedio sobre TODOS los materiales pedidos: un material que el
        # proveedor no tiene cuenta como 0, así se premia cubrir todo el pedido.
        p["score"] = round(p.pop("score_sum") / items_total, 3) if items_total else 0.0
        p["coverage"] = round(p["items_covered"] / items_total, 3) if items_total else 0.0
        p["cheapest_items"] = cheapest_count.get(p["provider_org_id"], 0)
        p["total_cost"] = round(p["total_cost"], 2)
        p["justificacion"] = _provider_justification(p, items_total)
        ranking.append(p)
    ranking.sort(key=lambda p: (-p["score"], p["total_cost"]))

    recommendation = ranking[0] if ranking else None
    combination_total = round(sum(c["subtotal"] or 0 for c in combination), 2)
    combination_providers = len({c["provider_org_id"] for c in combination})
    # El ahorro solo es comparable si el recomendado cubre los mismos
    # materiales que la combinación (si no, se compararían pedidos distintos).
    savings = None
    if recommendation and {c["item_id"] for c in combination} == recommendation["item_ids"]:
        savings = round(recommendation["total_cost"] - combination_total, 2)
    for p in ranking:
        del p["item_ids"]

    return {
        "items": items_out,
        "providers": ranking,
        "recommendation": recommendation,
        "best_combination": {
            "items": combination,
            "total_cost": combination_total,
            "items_covered": len(combination),
            "providers_count": combination_providers,
            "savings_vs_recommendation": savings,
        },
        "items_total": items_total,
        "items_without_offers": sum(1 for i in items_out if not i["offers"]),
    }
