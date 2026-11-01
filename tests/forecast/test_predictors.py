import pytest

from app.modules.forecast.predictors import (
    PricePoint, ProviderHistory, StatisticalForecastModel,
    confidence, delivery_estimate, price_trend_pct_30d, reliability,
)
from tests.forecast.helpers import BARATO, CONFIABLE, comparison, item, offer, two_providers

model = StatisticalForecastModel()


def _option(result, key):
    return next(o for o in result["options"] if o["key"] == key)


# --- Señales del historial ---------------------------------------------------

def test_sin_historial_se_asume_75_por_ciento_y_confianza_baja():
    assert reliability(ProviderHistory()) == 0.75
    assert confidence(ProviderHistory()) == "baja"


def test_el_cumplimiento_se_acerca_a_la_tasa_real_con_mas_ordenes():
    pocas = ProviderHistory(delivered=1)
    muchas = ProviderHistory(delivered=40, rejected=10)
    assert reliability(pocas) == pytest.approx(0.8)  # 1 entrega no da 100 %
    assert reliability(muchas) == pytest.approx(43 / 54)
    assert confidence(ProviderHistory(delivered=5)) == "media"
    assert confidence(muchas) == "alta"


def test_dias_de_entrega_mediana_y_rango():
    estimate = delivery_estimate(ProviderHistory(lead_times_days=(2, 4, 3, 10, 5)))
    assert estimate == {"median": 4, "p25": 3, "p75": 5}
    assert delivery_estimate(ProviderHistory()) is None


@pytest.mark.parametrize("prices, expected_sign", [
    ([100, 105, 110, 115], 1),
    ([115, 110, 105, 100], -1),
])
def test_tendencia_de_precio(prices, expected_sign):
    points = tuple(PricePoint(day=i * 30, material_key="cemento", unit_price=p) for i, p in enumerate(prices))
    trend = price_trend_pct_30d(points)
    assert trend * expected_sign > 3


def test_tendencia_mezcla_materiales_de_precios_distintos():
    points = (
        PricePoint(0, "cemento", 30000), PricePoint(30, "cemento", 31500),
        PricePoint(0, "puntilla", 10), PricePoint(30, "puntilla", 10.5),
    )
    assert price_trend_pct_30d(points) == pytest.approx(4.9, abs=0.1)


def test_sin_datos_suficientes_no_hay_tendencia():
    assert price_trend_pct_30d((PricePoint(0, "a", 10), PricePoint(30, "a", 12))) is None  # 2 puntos
    assert price_trend_pct_30d(tuple(PricePoint(0, k, 10) for k in "abcd")) is None       # 1 precio por material
    assert price_trend_pct_30d(tuple(PricePoint(d, "a", 10 + d) for d in (0, 1, 2))) is None  # menos de 7 días


# --- Opciones de compra ------------------------------------------------------

def test_sin_historial_el_mas_barato_es_la_mejor_opcion():
    result = model.predict(two_providers(), {})
    assert result["best_option_key"] == f"provider:{BARATO}"
    barato = _option(result, f"provider:{BARATO}")
    assert barato["cost_today"] == 3_600_000
    # 25 % de riesgo de recomprar de urgencia al confiable: 4.4 M − 3.6 M
    assert barato["expected_cost"] == pytest.approx(3_600_000 + 0.25 * 800_000)
    assert barato["confidence"] == "baja"


def test_barato_pero_poco_confiable_sale_mas_caro_a_futuro():
    histories = {
        BARATO: ProviderHistory(delivered=1, rejected=4, lead_times_days=(9, 12, 15)),
        CONFIABLE: ProviderHistory(delivered=10, lead_times_days=(2, 3, 3, 4)),
    }
    result = model.predict(two_providers(), histories)

    barato, confiable = _option(result, f"provider:{BARATO}"), _option(result, f"provider:{CONFIABLE}")
    assert barato["cost_today"] < confiable["cost_today"]
    assert barato["expected_cost"] > confiable["expected_cost"]
    assert result["best_option_key"] == f"provider:{CONFIABLE}"
    assert result["current_recommendation_key"] == f"provider:{BARATO}"  # hoy se recomienda el barato
    assert confiable["success_probability"] > 0.9 > 0.5 > barato["success_probability"]
    assert confiable["delivery_days"]["median"] == 3


def test_escenarios_ordenados_de_mejor_a_peor():
    histories = {BARATO: ProviderHistory(delivered=3, rejected=1, lead_times_days=(2, 4, 6))}
    barato = _option(model.predict(two_providers(), histories), f"provider:{BARATO}")
    s = barato["scenarios"]
    assert s["optimista"]["cost"] <= s["probable"]["cost"] <= s["pesimista"]["cost"]
    assert s["optimista"]["days"] == 3 and s["probable"]["days"] == 4 and s["pesimista"]["days"] == 8


def test_faltante_de_stock_se_compra_al_otro_y_se_paga_la_diferencia():
    barato = _option(model.predict(two_providers(cheap_stock=60), {}), f"provider:{BARATO}")
    [shortfall] = barato["shortfalls"]
    assert shortfall["missing_quantity"] == 40
    assert shortfall["alternative_provider"] == "Depósito Confiable"
    assert shortfall["extra_cost"] == 40 * 3000
    assert barato["scenarios"]["optimista"]["cost"] == 3_600_000 + 120_000


def test_lo_que_el_proveedor_no_tiene_se_completa_con_otro():
    data = comparison(
        [
            item(1, "Cemento", 100, [offer(BARATO, 27000, 100), offer(CONFIABLE, 30000, 100)]),
            item(2, "Varilla 3/8", 50, [offer(CONFIABLE, 20000, 50)]),
            item(3, "Teja de barro", 10, []),
        ],
        providers=[BARATO, CONFIABLE],
    )
    result = model.predict(data, {})
    barato = _option(result, f"provider:{BARATO}")
    assert (barato["items_from_main"], barato["complement_items"]) == (1, 1)
    assert barato["provider_org_ids"] == [BARATO, CONFIABLE]
    assert barato["success_probability"] == pytest.approx(0.75 * 0.75, abs=1e-3)  # deben cumplir los dos
    assert result["items_unavailable"] == ["Teja de barro"]


def test_unidad_incompatible_no_cuenta_como_oferta():
    data = comparison(
        [item(1, "Arena", 10, [offer(BARATO, 1000, 10, compatible=False), offer(CONFIABLE, 90000, 10)])],
        providers=[BARATO, CONFIABLE],
    )
    result = model.predict(data, {})
    assert [o["key"] for o in result["options"]] == [f"provider:{CONFIABLE}"]


def test_la_combinacion_se_evalua_como_una_opcion_mas():
    data = comparison(
        [
            item(1, "Cemento", 100, [offer(BARATO, 27000, 100), offer(CONFIABLE, 30000, 100)]),
            item(2, "Arena", 10, [offer(BARATO, 110000, 10), offer(CONFIABLE, 100000, 10)]),
        ],
        providers=[BARATO, CONFIABLE], combination=[(1, BARATO), (2, CONFIABLE)],
    )
    histories = {BARATO: ProviderHistory(delivered=10), CONFIABLE: ProviderHistory(delivered=10)}
    result = model.predict(data, histories)
    combo = _option(result, "combination")
    assert combo["cost_today"] == 2_700_000 + 1_000_000
    assert combo["success_probability"] == pytest.approx((13 / 14) ** 2, abs=1e-3)
    assert result["best_option_key"] == "combination"


def test_prima_frente_al_mercado():
    result = model.predict(two_providers(), {})
    profiles = {p["provider_org_id"]: p for p in result["providers"]}
    assert profiles[BARATO]["market_premium_pct"] < 0 < profiles[CONFIABLE]["market_premium_pct"]
