import asyncio
import json
from itertools import count

from app.modules.documents_ai.models import ProviderInventoryItem
from app.modules.matching.ai_review import AIProductReviewer, ProductReview, decide_similarity
from app.modules.matching.models import Quotation, QuotationItem
from app.modules.matching.scoring import ComparativeScoringStrategy
from app.modules.matching.service import MatchingService
from app.modules.matching.text_matching import MATCH_THRESHOLD, normalize_text

_ids = count(1)


def _item(name, quantity=10, unit="unidad"):
    return QuotationItem(id=next(_ids), quotation_id=1, material_name=name, quantity=quantity, unit=unit)


def _product(provider, name, price, stock=1000, unit="unidad"):
    return ProviderInventoryItem(
        id=next(_ids), provider_org_id=provider, material_name=name,
        unit=unit, unit_price=price, quantity_available=stock,
    )


class FakeAI:
    """Simula a Gemini: devuelve la respuesta que le pasemos y guarda el prompt."""

    def __init__(self, response=None, error=None):
        self.response, self.error, self.prompts = response, error, []

    async def generate_json(self, prompt, system_instruction, max_retries=3):
        self.prompts.append(json.loads(prompt))
        if self.error:
            raise self.error
        return self.response(self.prompts[-1]) if callable(self.response) else self.response


def _ref(payload, name):
    # Nombres que se normalizan igual se envían una sola vez al catálogo
    return next(p["ref"] for p in payload["catalogo"] if normalize_text(p["nombre"]) == normalize_text(name))


# --- decide_similarity -------------------------------------------------------

def test_la_ia_agrega_un_sinonimo_que_el_texto_no_ve():
    sim, method = decide_similarity(0.0, False, ProductReview(True, 0.9, "sinónimo"), MATCH_THRESHOLD)
    assert sim == 0.9 and method == "ia"


def test_la_ia_confirma_lo_que_ya_encontro_el_texto():
    sim, method = decide_similarity(0.95, False, ProductReview(True, 0.8, "mismo material"), MATCH_THRESHOLD)
    assert sim == 0.95 and method == "texto+ia"


def test_la_ia_descarta_un_falso_positivo_del_texto():
    sim, method = decide_similarity(0.8, False, ProductReview(False, 0.9, "es otro material"), MATCH_THRESHOLD)
    assert sim is None and method == "descartado_por_ia"


def test_la_ia_con_poca_confianza_no_cambia_nada():
    assert decide_similarity(0.8, False, ProductReview(False, 0.4, "no sé"), MATCH_THRESHOLD) == (0.8, "texto")
    assert decide_similarity(0.1, False, ProductReview(True, 0.4, "quizá"), MATCH_THRESHOLD)[0] is None


def test_la_ia_no_puede_saltarse_la_regla_de_medidas():
    sim, method = decide_similarity(0.9, True, ProductReview(True, 1.0, "equivalente"), MATCH_THRESHOLD)
    assert sim is None and method == "medidas_distintas"


# --- AIProductReviewer -------------------------------------------------------

def test_el_catalogo_se_envia_sin_nombres_repetidos_y_el_veredicto_aplica_a_todos():
    item = _item("acero de refuerzo 3/8")
    a = _product(10, 'Varilla corrugada 3/8" x 6m', 18500)
    a_dup = _product(10, 'Varilla corrugada 3/8" x 6m', 18500)  # importado dos veces
    b = _product(20, "Cemento gris 50kg", 23500)

    ai = FakeAI(lambda payload: {"revisiones": [{"item_id": item.id, "productos": [
        {"ref": _ref(payload, a.material_name), "equivalente": True, "confianza": 0.92, "motivo": "acero de refuerzo = varilla corrugada"},
        {"ref": "P999", "equivalente": True, "confianza": 1, "motivo": "ref inventada"},
    ]}]})
    result = asyncio.run(AIProductReviewer(ai).review([item], [a, a_dup, b], {}))

    assert len(ai.prompts[0]["catalogo"]) == 2
    assert result.status == "ok" and result.products_reviewed == 2
    assert result.reviews[(item.id, a.id)] == result.reviews[(item.id, a_dup.id)]
    assert result.reviews[(item.id, a.id)].confianza == 0.92
    assert (item.id, b.id) not in result.reviews


def test_los_candidatos_por_texto_se_envian_para_revision():
    item = _item("cemento gris")
    p = _product(10, "Cemento gris x 50kg", 25000)
    ai = FakeAI({"revisiones": []})
    asyncio.run(AIProductReviewer(ai).review([item], [p], {item.id: [p]}))
    assert ai.prompts[0]["materiales_pedidos"][0]["candidatos_por_texto"] == [ai.prompts[0]["catalogo"][0]["ref"]]


def test_si_la_ia_falla_no_se_rompe_el_matching():
    result = asyncio.run(AIProductReviewer(FakeAI(error=RuntimeError("timeout"))).review(
        [_item("cemento")], [_product(10, "Cemento gris", 25000)], {},
    ))
    assert result.status == "failed" and result.reviews == {}


# --- MatchingService con revisión de IA --------------------------------------

class FakeQuotationRepo:
    def __init__(self, quotation, items):
        self.quotation, self.items = quotation, items

    async def get_by_id(self, quotation_id):
        return self.quotation

    async def get_items(self, quotation_id):
        return self.items


class FakeMatchRepo:
    def __init__(self, products, names):
        self.products, self.names, self.saved = products, names, []

    async def delete_unordered_for_items(self, item_ids):
        pass

    async def list_inventory(self):
        return self.products

    async def save_all(self, matches):
        for match in matches:
            match.id = next(_ids)
        self.saved = matches
        return matches

    async def get_organization_names(self, org_ids):
        return {i: self.names[i] for i in org_ids}


class FakeAudit:
    async def record(self, **kwargs):
        pass


def _run(items, products, ai):
    quotation = Quotation(id=1, constructora_org_id=99, title="Obra")
    service = MatchingService(
        FakeQuotationRepo(quotation, items), FakeMatchRepo(products, {10: "Aceros del Valle", 20: "Argos"}),
        scoring_strategy=ComparativeScoringStrategy(), audit=FakeAudit(),
        reviewer=AIProductReviewer(ai) if ai else None,
    )
    return asyncio.run(service.run_matching(1, actor_user_id=1, actor_org_id=99))


def test_servicio_usa_la_ia_para_sinonimos_y_para_descartar():
    acero = _item("acero de refuerzo 3/8", quantity=100)
    arena = _item("arena de rio", quantity=5, unit="m3")
    varilla_valle = _product(10, 'Varilla corrugada 3/8" x 6m', 18500)
    varilla_argos = _product(20, "Varilla corrugada 3/8 x 6 m", 19900)
    arena_valle = _product(10, "Arena de rio (lavada)", 45000, unit="m3")
    arena_argos = _product(20, "Arena de rio para filtro piscina", 52000, unit="m3")  # otro uso

    def respond(payload):
        return {"revisiones": [
            {"item_id": acero.id, "productos": [
                {"ref": _ref(payload, varilla_valle.material_name), "equivalente": True, "confianza": 0.9, "motivo": "sinónimo"},
                {"ref": _ref(payload, varilla_argos.material_name), "equivalente": True, "confianza": 0.85, "motivo": "sinónimo"},
            ]},
            {"item_id": arena.id, "productos": [
                {"ref": _ref(payload, arena_valle.material_name), "equivalente": True, "confianza": 0.95, "motivo": "misma arena"},
                {"ref": _ref(payload, arena_argos.material_name), "equivalente": False, "confianza": 0.85, "motivo": "arena para piscina, no de construcción"},
            ]},
        ]}

    products = [varilla_valle, varilla_argos, arena_valle, arena_argos]
    result = _run([acero, arena], products, FakeAI(respond))

    acero_offers = result["items"][0]["offers"]
    assert {o["provider_name"] for o in acero_offers} == {"Aceros del Valle", "Argos"}
    assert all(o["criteria"]["metodo"] == "ia" for o in acero_offers)
    assert acero_offers[0]["criteria"]["revision_ia"]["motivo"] == "sinónimo"

    arena_offers = result["items"][1]["offers"]
    assert [o["provider_name"] for o in arena_offers] == ["Aceros del Valle"]
    assert arena_offers[0]["criteria"]["metodo"] == "texto+ia"

    # 3 y no 4: las dos varillas se escriben distinto pero se normalizan igual
    assert result["ai_review"] == {"status": "ok", "products_reviewed": 3, "matches_added": 2, "matches_rejected": 1}


def test_servicio_sin_ia_sigue_funcionando_por_texto():
    cemento = _item("cemento gris", unit="bulto")
    acero = _item("acero de refuerzo 3/8")
    products = [_product(10, "Cemento gris x 50kg", 25000, unit="bulto"), _product(10, 'Varilla corrugada 3/8" x 6m', 18500)]

    for ai in (None, FakeAI(error=RuntimeError("caída"))):
        result = _run([cemento, acero], products, ai)
        assert result["ai_review"]["status"] == ("disabled" if ai is None else "failed")
        assert len(result["items"][0]["offers"]) == 1  # el cemento lo encuentra el texto
        assert result["items"][1]["offers"] == []      # el sinónimo solo lo vería la IA
