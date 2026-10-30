from itertools import count

from app.modules.documents_ai.models import ProviderInventoryItem
from app.modules.matching.comparison import ScoredOffer, build_comparison
from app.modules.matching.models import Match, QuotationItem
from app.modules.matching.scoring import ComparativeScoringStrategy, OfferContext
from app.modules.matching.text_matching import material_similarity

_ids = count(1)
NAMES = {10: "Aceros del Valle", 20: "Ferretería Central"}


def _item(name, quantity, unit, budget=None):
    return QuotationItem(id=next(_ids), material_name=name, quantity=quantity, unit=unit, unit_price=budget)


def _inventory(provider, name, unit, price, stock):
    return ProviderInventoryItem(
        id=next(_ids), provider_org_id=provider, material_name=name,
        unit=unit, unit_price=price, quantity_available=stock,
    )


def _offers(item, inventories):
    """Reproduce lo que hace MatchingService para un ítem."""
    best_price = min(inv.unit_price for inv in inventories)
    offers = []
    for inv in inventories:
        context = OfferContext(similarity=material_similarity(item.material_name, inv.material_name), best_unit_price=best_price)
        score, breakdown = ComparativeScoringStrategy().calculate(item, inv, context)
        match = Match(id=next(_ids), quotation_item_id=item.id, provider_inventory_id=inv.id,
                      provider_org_id=inv.provider_org_id, score=score, criteria_breakdown=breakdown)
        offers.append(ScoredOffer(item=item, inventory=inv, match=match))
    return offers


def test_scoring_premia_precio_y_stock():
    item = _item("cemento gris", 100, "bulto")
    barato = _inventory(10, "Cemento gris x 50kg", "bultos", 24000, 150)
    caro = _inventory(20, "Cemento gris 50kg", "bulto", 30000, 150)
    sin_stock = _inventory(20, "Cemento gris 50kg", "bulto", 24000, 40)

    s_barato, b_barato = ComparativeScoringStrategy().calculate(item, barato, OfferContext(1.0, 24000))
    s_caro, b_caro = ComparativeScoringStrategy().calculate(item, caro, OfferContext(1.0, 24000))
    s_sin_stock, b_sin_stock = ComparativeScoringStrategy().calculate(item, sin_stock, OfferContext(1.0, 24000))

    assert s_barato > s_caro
    assert s_barato > s_sin_stock
    assert b_barato["precio"] == 1.0 and b_caro["precio"] == 0.8
    assert b_sin_stock["disponibilidad"] == 0.4 and not b_sin_stock["stock_suficiente"]
    assert b_barato["subtotal"] == 2_400_000


def test_unidad_incompatible_se_penaliza():
    item = _item("arena de rio", 10, "m3")
    misma_unidad = _inventory(10, "Arena de rio", "m3", 45000, 20)
    otra_unidad = _inventory(20, "Arena de rio", "bulto", 45000, 20)
    s1, _ = ComparativeScoringStrategy().calculate(item, misma_unidad, OfferContext(1.0, 45000))
    s2, b2 = ComparativeScoringStrategy().calculate(item, otra_unidad, OfferContext(1.0, 45000))
    assert s2 < s1 and b2["unidad_compatible"] is False


def test_compara_proveedores_y_recomienda_el_que_cubre_mas_barato():
    cemento = _item("cemento gris", 100, "bulto")
    varilla = _item("varilla corrugada 3/8", 50, "unidad")
    arena = _item("arena de rio", 10, "m3")

    offers = (
        _offers(cemento, [
            _inventory(10, "Cemento gris x 50kg", "bultos", 25000, 150),
            _inventory(20, "Cemento gris 50 kg", "bulto", 23500, 500),
        ])
        + _offers(varilla, [
            _inventory(10, 'Varilla corrugada 3/8" x 6m', "unidades", 18500, 300),
            _inventory(20, "Varilla corrugada 3/8 6m", "und", 19900, 100),
        ])
        + _offers(arena, [_inventory(10, "Arena de rio (lavada)", "m3", 45000, 20)])
    )

    result = build_comparison([cemento, varilla, arena], offers, NAMES)

    ranking = result["providers"]
    assert [p["provider_org_id"] for p in ranking] == [10, 20]
    valle, central = ranking
    assert valle["items_covered"] == 3 and central["items_covered"] == 2
    assert valle["total_cost"] == 100 * 25000 + 50 * 18500 + 10 * 45000
    assert valle["cheapest_items"] == 2  # varilla y arena
    assert central["cheapest_items"] == 1  # cemento
    assert result["recommendation"]["provider_name"] == "Aceros del Valle"
    assert "Cubre 3 de 3 materiales" in valle["justificacion"]

    combo = result["best_combination"]
    assert {(c["material_name"], c["provider_org_id"]) for c in combo["items"]} == {
        ("cemento gris", 20), ("varilla corrugada 3/8", 10), ("arena de rio", 10),
    }
    assert combo["providers_count"] == 2
    assert combo["savings_vs_recommendation"] == 100 * (25000 - 23500)

    cemento_out = result["items"][0]
    assert [o["provider_org_id"] for o in cemento_out["offers"] if o["is_cheapest"]] == [20]


def test_ahorro_cuando_ningun_proveedor_cubre_todo():
    cemento = _item("cemento gris", 100, "bulto")
    varilla = _item("varilla corrugada 3/8", 50, "unidad")
    malla = _item("malla electrosoldada", 30, "unidad")  # nadie la tiene

    offers = (
        _offers(cemento, [
            _inventory(10, "Cemento gris", "bulto", 25000, 150),
            _inventory(20, "Cemento gris", "bulto", 23500, 500),
        ])
        + _offers(varilla, [_inventory(10, "Varilla corrugada 3/8", "unidad", 18500, 300)])
    )
    result = build_comparison([cemento, varilla, malla], offers, NAMES)

    assert result["recommendation"]["provider_org_id"] == 10
    assert result["items_without_offers"] == 1
    assert result["best_combination"]["savings_vs_recommendation"] == 100 * (25000 - 23500)
    assert "item_ids" not in result["recommendation"]


def test_material_sin_ofertas():
    clavo = _item("clavo 2 pulgadas", 5, "kg")
    result = build_comparison([clavo], [], NAMES)
    assert result["items_without_offers"] == 1
    assert result["recommendation"] is None
    assert result["providers"] == []
