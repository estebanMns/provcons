import asyncio
from datetime import datetime, timezone
from itertools import count

import pytest

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.modules.documents_ai.models import ProviderInventoryItem
from app.modules.matching.models import Match, Quotation, QuotationItem, QuotationStatus
from app.modules.transactions.models import Order, OrderStatus, PaymentTerms
from app.modules.transactions.service import OrderService

_ids = count(100)
CONSTRUCTORA, VALLE, ARGOS, OTRA = 1, 2, 3, 9


class FakeOrderRepo:
    def __init__(self, quotation, offers):
        self.quotation, self.offers, self.orders = quotation, offers, {}

    async def get_quotation(self, quotation_id):
        return self.quotation if quotation_id == self.quotation.id else None

    async def save_quotation(self, quotation):
        pass

    async def get_offers(self, match_ids):
        return [o for o in self.offers if o[0].id in match_ids]

    async def ordered_quotation_items(self, item_ids):
        return {
            i.quotation_item_id for o in self.orders.values() if o.status != OrderStatus.cancelada
            for i in o.items if i.quotation_item_id in item_ids
        }

    async def save_all(self, orders):
        now = datetime.now(timezone.utc)
        for o in orders:
            o.id = o.id or next(_ids)
            o.status = o.status or OrderStatus.pendiente
            o.created_at = o.updated_at = now
            for i in o.items:
                i.id = i.id or next(_ids)
            self.orders[o.id] = o
        return orders

    async def save(self, order):
        return (await self.save_all([order]))[0]

    async def get_by_id(self, order_id):
        return self.orders.get(order_id)

    async def list_by_organization(self, org_id):
        return [o for o in self.orders.values() if org_id in (o.constructora_org_id, o.provider_org_id)]

    async def get_organization_names(self, org_ids):
        return {i: f"Org {i}" for i in org_ids}

    async def get_quotation_titles(self, ids):
        return {i: "Obra" for i in ids}


class FakeAudit:
    def __init__(self):
        self.actions = []

    async def record(self, action, **kwargs):
        self.actions.append(action)


def _offer(quotation_item, provider, price):
    inventory = ProviderInventoryItem(id=next(_ids), provider_org_id=provider, material_name=quotation_item.material_name.title(),
                                      unit=quotation_item.unit, unit_price=price, quantity_available=1000)
    match = Match(id=next(_ids), quotation_item_id=quotation_item.id, provider_inventory_id=inventory.id,
                  provider_org_id=provider, score=0.9, criteria_breakdown={})
    return match, quotation_item, inventory


@pytest.fixture
def setup():
    quotation = Quotation(id=1, constructora_org_id=CONSTRUCTORA, title="Obra", status=QuotationStatus.abierta)
    cemento = QuotationItem(id=11, quotation_id=1, material_name="cemento gris", quantity=100, unit="bulto")
    varilla = QuotationItem(id=12, quotation_id=1, material_name="varilla 3/8", quantity=50, unit="unidad")
    offers = {
        "cemento_valle": _offer(cemento, VALLE, 25000),
        "cemento_argos": _offer(cemento, ARGOS, 23500),
        "varilla_valle": _offer(varilla, VALLE, 18500),
    }
    repo, audit = FakeOrderRepo(quotation, list(offers.values())), FakeAudit()
    ids = {k: v[0].id for k, v in offers.items()}
    return OrderService(repo, audit), repo, audit, quotation, ids


def _create(service, match_ids, org=CONSTRUCTORA):
    return asyncio.run(service.create_orders(1, match_ids, PaymentTerms.contado, actor_user_id=1, actor_org_id=org))


def test_una_orden_por_proveedor_con_precios_congelados(setup):
    service, repo, audit, quotation, ids = setup
    orders = _create(service, [ids["cemento_argos"], ids["varilla_valle"]])

    by_provider = {o["provider_org_id"]: o for o in orders}
    assert set(by_provider) == {ARGOS, VALLE}
    assert by_provider[ARGOS]["total_amount"] == 100 * 23500
    assert by_provider[VALLE]["items"][0].subtotal == 50 * 18500
    assert all(o["status"] == OrderStatus.pendiente for o in orders)
    assert quotation.status == QuotationStatus.en_negociacion
    assert audit.actions.count("order.created") == 2


def test_no_se_puede_pedir_dos_veces_el_mismo_material(setup):
    service, *_, ids = setup
    _create(service, [ids["cemento_argos"]])
    with pytest.raises(ConflictError):
        _create(service, [ids["cemento_valle"]])


def test_dos_ofertas_del_mismo_material_en_una_orden(setup):
    service, *_, ids = setup
    with pytest.raises(ValidationError):
        _create(service, [ids["cemento_argos"], ids["cemento_valle"]])


def test_solo_la_constructora_duena_crea_ordenes(setup):
    service, *_, ids = setup
    with pytest.raises(ForbiddenError):
        _create(service, [ids["cemento_argos"]], org=OTRA)


def test_oferta_inexistente(setup):
    service, *_ = setup
    with pytest.raises(NotFoundError):
        _create(service, [123456])


def test_flujo_del_proveedor_y_permisos(setup):
    service, *_, ids = setup
    order_id = _create(service, [ids["varilla_valle"]])[0]["id"]
    run = asyncio.run

    with pytest.raises(ForbiddenError):
        run(service.confirm_order(order_id, 1, CONSTRUCTORA))  # confirma el proveedor, no la constructora
    with pytest.raises(ForbiddenError):
        run(service.get_order(order_id, ARGOS))  # otro proveedor no la ve
    with pytest.raises(ConflictError):
        run(service.advance_order(order_id, 2, VALLE))  # no puede enviarse sin confirmar

    assert run(service.confirm_order(order_id, 2, VALLE))["status"] == OrderStatus.confirmada
    assert run(service.advance_order(order_id, 2, VALLE))["status"] == OrderStatus.en_transito
    assert run(service.advance_order(order_id, 2, VALLE))["status"] == OrderStatus.entregada
    with pytest.raises(ConflictError):
        run(service.cancel_order(order_id, 1, CONSTRUCTORA))  # ya entregada


def test_si_el_proveedor_rechaza_el_material_queda_libre(setup):
    service, repo, audit, _, ids = setup
    order_id = _create(service, [ids["cemento_argos"]])[0]["id"]
    assert asyncio.run(service.cancel_order(order_id, 3, ARGOS))["status"] == OrderStatus.cancelada
    assert "order.rejected" in audit.actions
    assert _create(service, [ids["cemento_valle"]])[0]["provider_org_id"] == VALLE


def test_transiciones_del_modelo():
    order = Order(status=OrderStatus.pendiente, predicted_negotiation={})
    with pytest.raises(ValueError):
        order.advance()
    order.confirm()
    assert order.status == OrderStatus.confirmada and order.can_be_cancelled()
    order.advance()
    order.advance()
    assert order.status == OrderStatus.entregada and not order.can_be_cancelled()
    with pytest.raises(ValueError):
        order.advance()
