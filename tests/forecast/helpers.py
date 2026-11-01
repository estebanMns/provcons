"""Comparaciones de ejemplo con la misma forma que devuelve build_comparison."""

BARATO, CONFIABLE = 2, 3


def offer(provider, price, quantity, stock=1000, compatible=True, match_id=None):
    return {
        "match_id": match_id or provider * 100 + int(price),
        "provider_org_id": provider,
        "unit_price": price,
        "quantity_available": stock,
        "subtotal": round(price * quantity, 2),
        "criteria": {"unidad_compatible": compatible, "stock_suficiente": stock >= quantity},
    }


def item(item_id, name, quantity, offers):
    return {"item_id": item_id, "material_name": name, "quantity": quantity, "unit": "unidad", "offers": offers}


def comparison(items, providers, recommendation_id=None, combination=None):
    names = {BARATO: "Ferretería Barata", CONFIABLE: "Depósito Confiable"}
    ranking = [{"provider_org_id": p, "provider_name": names.get(p, f"Proveedor {p}"), "unit_mismatches": 0} for p in providers]
    combination = combination or []
    return {
        "quotation_id": 1,
        "items_total": len(items),
        "items": items,
        "providers": ranking,
        "recommendation": next((r for r in ranking if r["provider_org_id"] == recommendation_id), None),
        "best_combination": {
            "items": [{"item_id": i, "provider_org_id": p} for i, p in combination],
            "providers_count": len({p for _, p in combination}),
        },
    }


def two_providers(cheap_stock=1000):
    """Dos materiales; el barato cobra 10 % menos que el confiable."""
    return comparison(
        [
            item(1, "Cemento gris 50 kg", 100, [offer(BARATO, 27000, 100, cheap_stock), offer(CONFIABLE, 30000, 100)]),
            item(2, "Arena de río", 10, [offer(BARATO, 90000, 10), offer(CONFIABLE, 100000, 10)]),
        ],
        providers=[BARATO, CONFIABLE], recommendation_id=BARATO,
    )
