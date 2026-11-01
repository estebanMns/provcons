import asyncio
import json

from app.modules.forecast.narrator import AIForecastNarrator, TemplateNarrator
from app.modules.forecast.predictors import ProviderHistory, StatisticalForecastModel
from app.modules.forecast.service import ForecastCache, ForecastService
from tests.forecast.helpers import BARATO, CONFIABLE, two_providers

KEYS = (f"provider:{BARATO}", f"provider:{CONFIABLE}")


def _forecast(histories=None):
    return StatisticalForecastModel().predict(two_providers(), histories or {})


class FakeAI:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.prompts = response, error, []

    async def generate_json(self, prompt, system_instruction, max_retries=3):
        self.prompts.append(json.loads(prompt))
        if self.error:
            raise self.error
        return self.response


def test_plantilla_explica_cada_opcion_y_avisa_poca_confianza():
    narrative = TemplateNarrator().build(_forecast())
    assert narrative.source == "plantilla"
    assert set(narrative.options) == set(KEYS)
    assert "Poco historial" in narrative.options[KEYS[0]].riesgos[0]
    assert "comprarle a Ferretería Barata" in narrative.summary


def test_plantilla_explica_por_que_cambia_la_recomendacion():
    histories = {BARATO: ProviderHistory(delivered=1, rejected=4), CONFIABLE: ProviderHistory(delivered=10)}
    narrative = TemplateNarrator().build(_forecast(histories))
    assert "distinta de la recomendación de hoy" in narrative.summary
    assert any("rechazado 4" in r for r in narrative.options[KEYS[0]].riesgos)


def test_la_ia_redacta_y_se_ignoran_opciones_inventadas():
    ai = FakeAI({
        "resumen": "Te conviene el depósito.",
        "opciones": [
            {"key": KEYS[1], "que_pasara": "Recibirías todo en 3 días." + "x" * 1000, "riesgos": ["ninguno"], "consejo": "Cómprale."},
            {"key": "provider:999", "que_pasara": "Proveedor inventado"},
        ],
    })
    narrative = asyncio.run(AIForecastNarrator(ai).narrate(_forecast()))

    assert narrative.source == "ia"
    assert narrative.summary == "Te conviene el depósito."
    assert "provider:999" not in narrative.options
    assert len(narrative.options[KEYS[1]].que_pasara) == 400
    # La opción que la IA no explicó queda con la plantilla
    assert narrative.options[KEYS[0]].que_pasara.startswith("Pagarías")
    # A la IA se le envían las cifras ya calculadas
    sent = ai.prompts[0]["opciones"][0]
    assert {"costo_hoy", "costo_esperado", "probabilidad_exito", "confianza"} <= set(sent)


def test_si_la_ia_falla_se_usa_la_plantilla():
    narrative = asyncio.run(AIForecastNarrator(FakeAI(error=RuntimeError("cuota agotada"))).narrate(_forecast()))
    assert narrative.source == "plantilla"
    assert set(narrative.options) == set(KEYS)


def test_respuesta_vacia_de_la_ia_usa_la_plantilla():
    narrative = asyncio.run(AIForecastNarrator(FakeAI({"opciones": "no es una lista"})).narrate(_forecast()))
    assert narrative.source == "plantilla"


class FakeMatching:
    def __init__(self):
        self.calls = 0

    async def get_comparison(self, quotation_id, actor_org_id):
        self.calls += 1
        return two_providers() | {"quotation_id": quotation_id}


class FakeHistory:
    async def provider_history(self, provider_ids, constructora_org_id):
        return {CONFIABLE: ProviderHistory(delivered=10, lead_times_days=(3,))}


def test_servicio_arma_la_prediccion_y_la_cache_evita_otra_llamada_a_la_ia():
    ai = FakeAI({"resumen": "Resumen IA", "opciones": []})
    service = ForecastService(
        FakeMatching(), FakeHistory(), StatisticalForecastModel(), AIForecastNarrator(ai), ForecastCache(),
    )

    first = asyncio.run(service.forecast(7, actor_org_id=1))
    second = asyncio.run(service.forecast(7, actor_org_id=1))

    assert first["quotation_id"] == 7 and first["cached"] is False
    assert first["summary"] == "Resumen IA" and first["narrative_source"] == "ia"
    assert all(o["narrative"]["que_pasara"] for o in first["options"])
    assert second["cached"] is True
    assert len(ai.prompts) == 1


def test_cache_vence_y_respeta_su_tamano():
    cache = ForecastCache(ttl_seconds=-1, max_entries=2)
    cache.set(("a",), {"x": 1})
    assert cache.get(("a",)) is None  # vencida
    cache = ForecastCache(max_entries=2)
    for k in "abc":
        cache.set((k,), {})
    assert cache.get(("a",)) is None and cache.get(("c",)) == {}
