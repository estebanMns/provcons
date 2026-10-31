import asyncio

import pytest

from app.core.exceptions import ForbiddenError
from app.modules.matching.models import Match, Quotation
from app.modules.matching.scoring import ComparativeScoringStrategy
from app.modules.matching.service import MatchingService
from tests.matching.test_ai_review import FakeAudit, FakeMatchRepo, FakeQuotationRepo, _item, _product


class HistoryMatchRepo(FakeMatchRepo):
    def __init__(self, products, names, stored):
        super().__init__(products, names)
        self.stored = stored

    async def get_offers_for_items(self, item_ids):
        return [(m, inv) for m, inv in self.stored if m.quotation_item_id in item_ids]


def _match(match_id, item, inventory, price_score):
    return Match(id=match_id, quotation_item_id=item.id, provider_inventory_id=inventory.id,
                 provider_org_id=inventory.provider_org_id, score=price_score,
                 criteria_breakdown={"subtotal": inventory.unit_price * item.quantity, "stock_suficiente": True,
                                     "unidad_compatible": True, "metodo": "texto"})


def test_reabrir_la_comparacion_usa_el_ultimo_match_por_proveedor():
    cemento = _item("cemento gris", quantity=10, unit="bulto")
    valle_viejo = _product(10, "Cemento gris", 26000, unit="bulto")
    valle_nuevo = _product(10, "Cemento gris", 25000, unit="bulto")
    argos = _product(20, "Cemento gris 50kg", 23500, unit="bulto")
    stored = [
        (_match(1, cemento, valle_viejo, 0.8), valle_viejo),  # con orden, sobrevivió al recálculo
        (_match(5, cemento, valle_nuevo, 0.9), valle_nuevo),
        (_match(6, cemento, argos, 0.95), argos),
    ]
    quotation = Quotation(id=1, constructora_org_id=99, title="Obra")
    service = MatchingService(
        FakeQuotationRepo(quotation, [cemento]), HistoryMatchRepo([], {10: "Aceros del Valle", 20: "Argos"}, stored),
        scoring_strategy=ComparativeScoringStrategy(), audit=FakeAudit(),
    )

    result = asyncio.run(service.get_comparison(1, actor_org_id=99))

    offers = result["items"][0]["offers"]
    assert sorted(o["match_id"] for o in offers) == [5, 6]
    assert result["ai_review"]["status"] == "stored"
    assert result["recommendation"]["provider_name"] == "Argos"

    with pytest.raises(ForbiddenError):
        asyncio.run(service.get_comparison(1, actor_org_id=7))
