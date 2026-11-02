import asyncio

import pytest

from app.modules.transactions.credit import (
    CON_RIESGO, CONVENIENTE, NO_CONVENIENTE, ClientHistory,
    credit_confidence, credit_score, evaluate, installment_plan, max_installments, verdict,
)
from app.modules.transactions.credit_narrator import AICreditNarrator, TemplateCreditNarrator

BIG = 50_000_000  # monto sin tope por cuotas mínimas


def test_puntaje_sin_historial_parte_del_prior():
    history = ClientHistory()
    assert credit_score(history) == pytest.approx(0.75)
    assert credit_confidence(history) == "baja"


def test_cancelar_baja_el_puntaje():
    good = ClientHistory(delivered=10)
    bad = ClientHistory(delivered=4, cancelled_by_client=6)
    assert credit_score(good) == pytest.approx(13 / 14)
    assert credit_score(bad) < 0.55
    assert credit_confidence(good) == "alta"


def test_escalones_de_cuotas_y_baja_por_confianza():
    assert max_installments(0.93, "alta", BIG) == 12
    assert max_installments(0.75, "media", BIG) == 6
    assert max_installments(0.60, "media", BIG) == 3
    assert max_installments(0.40, "alta", BIG) == 1
    assert max_installments(0.75, "baja", BIG) == 3  # sin historial: un escalón menos


def test_tope_por_monto_evita_cuotas_diminutas():
    assert max_installments(0.95, "alta", 900_000) == 4    # 900.000 / 200.000
    assert max_installments(0.95, "alta", 150_000) == 1


def test_veredictos():
    assert verdict(3, 3) == CONVENIENTE
    assert verdict(6, 3) == CON_RIESGO      # siguiente escalón
    assert verdict(9, 3) == NO_CONVENIENTE
    assert verdict(4, 4) == CONVENIENTE
    assert verdict(6, 4) == CON_RIESGO      # el tope por monto no es un escalón: el siguiente es 6
    assert verdict(12, 12) == CONVENIENTE


def test_amortizacion_francesa():
    plan = installment_plan(1_200_000, 12, 0)
    assert plan["installment_amount"] == 100_000 and plan["interest"] == 0

    plan = installment_plan(1_000_000, 6, 2)
    assert plan["installment_amount"] == pytest.approx(178_525.81, abs=0.01)
    assert plan["financed_total"] == pytest.approx(plan["installment_amount"] * 6, abs=0.05)
    assert plan["interest"] > 0

    contado = installment_plan(1_000_000, 1, 3)
    assert contado["installment_amount"] == 1_000_000 and contado["monthly_rate_pct"] == 0


def test_evaluar_arma_opciones_y_razones():
    result = evaluate(900_000, ClientHistory(delivered=2, cancelled_by_client=2, orders_with_provider=1, months_on_platform=0.5))
    assert result["max_installments"] == 3
    assert [o["installments"] for o in result["options"]] == [1, 2, 3, 4, 6, 9, 12]
    by_n = {o["installments"]: o["verdict"] for o in result["options"]}
    assert by_n[3] == CONVENIENTE and by_n[6] == CON_RIESGO and by_n[12] == NO_CONVENIENTE
    text = " ".join(result["reasons"])
    assert "Canceló 2" in text and "menos de un mes" in text


def _evaluation():
    return {"constructora_name": "Constructora Andina", "amount": 2_000_000,
            **evaluate(2_000_000, ClientHistory(delivered=12, months_on_platform=10))}


class FakeAI:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.prompts = response, error, []

    async def generate_json(self, prompt, system_instruction, max_retries):
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return self.response


def test_plantilla_recomienda_el_maximo():
    narrative = TemplateCreditNarrator.build(_evaluation())
    assert narrative.source == "plantilla"
    assert "Constructora Andina" in narrative.summary and "10 cuotas" in narrative.summary


def test_ia_redacta_y_se_recorta():
    ai = FakeAI({"resumen": "Te conviene. " * 100, "consejo": "Da hasta 10 cuotas."})
    narrative = asyncio.run(AICreditNarrator(ai).narrate(_evaluation()))
    assert narrative.source == "ia" and len(narrative.summary) <= 400
    assert "maximo_cuotas_recomendado" in ai.prompts[0]


@pytest.mark.parametrize("ai", [FakeAI(error=RuntimeError("cuota agotada")), FakeAI({"otra": 1}), FakeAI("texto")])
def test_si_la_ia_falla_se_usa_la_plantilla(ai):
    assert asyncio.run(AICreditNarrator(ai).narrate(_evaluation())).source == "plantilla"
