import asyncio
from itertools import count

import pytest

from app.core.exceptions import ConflictError, ValidationError
from app.modules.documents_ai.models import ProviderInventoryItem
from app.modules.documents_ai.service import InventoryService

ORG = 5
_ids = count(1)


class FakeInventoryRepo:
    def __init__(self, items=()):
        self.items = {i.id: i for i in items}

    async def list_by_provider(self, provider_org_id, include_inactive=False):
        return [i for i in self.items.values()
                if i.provider_org_id == provider_org_id and (include_inactive or i.is_active)]

    async def get_by_id(self, item_id):
        return self.items.get(item_id)

    async def get_by_sku(self, provider_org_id, sku):
        return next((i for i in self.items.values() if i.provider_org_id == provider_org_id and i.sku == sku), None)

    async def save(self, item):
        return (await self.save_all([item]))[0]

    async def save_all(self, items):
        for item in items:
            item.id = item.id or next(_ids)
            self.items[item.id] = item
        return items


class FakeAudit:
    def __init__(self):
        self.actions = []

    async def record(self, action, **kwargs):
        self.actions.append(action)


def _item(sku, name, unit="bulto", qty=100, price=30000, active=True):
    return ProviderInventoryItem(id=next(_ids), provider_org_id=ORG, sku=sku, material_name=name, unit=unit,
                                 unit_price=price, quantity_available=qty, specs={}, is_active=active)


def _service(*items):
    repo, audit = FakeInventoryRepo(items), FakeAudit()
    return InventoryService(repo, audit), repo, audit


def _import(service, rows):
    return asyncio.run(service.bulk_import(ORG, rows, actor_user_id=1))


def test_codigo_existente_suma_y_actualiza_el_precio():
    cemento = _item("CEM-01", "cemento gris", qty=100, price=30000)
    service, repo, audit = _service(cemento)
    result = _import(service, [{"sku": "cem-01 ", "material_name": "Cemento gris 50kg", "unit": "bulto",
                                "quantity_available": 50, "unit_price": 31000}])
    assert result.updated == [cemento] and result.created == []
    assert cemento.quantity_available == 150 and cemento.unit_price == 31000
    assert len(repo.items) == 1
    assert "inventory.stock_added" in audit.actions


def test_codigo_nuevo_crea_el_producto():
    service, repo, _ = _service(_item("CEM-01", "cemento gris"))
    result = _import(service, [{"sku": "VAR-38", "material_name": "varilla 3/8", "unit": "unidad",
                                "quantity_available": 200, "unit_price": 18500}])
    assert [i.sku for i in result.created] == ["VAR-38"]
    assert len(repo.items) == 2


def test_sin_codigo_busca_por_nombre_y_unidad():
    cemento = _item("P-0001", "Cemento Gris", qty=10)
    service, _, _ = _service(cemento)
    result = _import(service, [{"material_name": "cemento  gris", "unit": "Bulto", "quantity_available": 5, "unit_price": None}])
    assert result.updated == [cemento] and cemento.quantity_available == 15
    assert cemento.unit_price == 30000  # sin precio en el archivo se conserva el anterior


def test_un_codigo_real_reemplaza_al_automatico():
    cemento = _item("P-0001", "cemento gris")
    service, _, _ = _service(cemento)
    _import(service, [{"sku": "CEM-01", "material_name": "cemento gris", "unit": "bulto", "quantity_available": 1, "unit_price": 1}])
    assert cemento.sku == "CEM-01"


def test_filas_repetidas_del_mismo_archivo_se_suman():
    service, repo, _ = _service()
    result = _import(service, [
        {"sku": "AR-1", "material_name": "arena", "unit": "m3", "quantity_available": 4, "unit_price": 90000},
        {"sku": "AR-1", "material_name": "arena", "unit": "m3", "quantity_available": 6, "unit_price": 90000},
    ])
    assert len(result.created) == 1 and result.updated == []
    assert result.created[0].quantity_available == 10 and len(repo.items) == 1


def test_genera_el_siguiente_codigo_automatico():
    service, _, _ = _service(_item("P-0007", "cemento gris"), _item("CEM-9", "cal"))
    result = _import(service, [
        {"material_name": "arena", "unit": "m3", "quantity_available": 1, "unit_price": 90000},
        {"material_name": "grava", "unit": "m3", "quantity_available": 1, "unit_price": 95000},
    ])
    assert [i.sku for i in result.created] == ["P-0008", "P-0009"]


def test_un_producto_eliminado_se_reactiva_al_volver_a_subirlo():
    cemento = _item("CEM-01", "cemento gris", qty=0, active=False)
    service, _, _ = _service(cemento)
    _import(service, [{"sku": "CEM-01", "material_name": "cemento gris", "unit": "bulto", "quantity_available": 30, "unit_price": 30000}])
    assert cemento.is_active and cemento.quantity_available == 30


def test_filas_invalidas_se_omiten_y_un_archivo_vacio_da_error():
    service, _, _ = _service()
    result = _import(service, [
        {"material_name": "x", "unit": "kg", "unit_price": 1},                     # nombre muy corto
        {"material_name": "pintura", "unit": "galón", "quantity_available": 3},    # nuevo sin precio
        {"material_name": "estuco", "unit": "bulto", "quantity_available": 3, "unit_price": 25000},
    ])
    assert [i.material_name for i in result.created] == ["estuco"] and result.skipped == 2
    with pytest.raises(ValidationError):
        _import(service, [{"material_name": "x"}])


def test_editar_con_un_codigo_repetido_da_conflicto_y_eliminar_lo_oculta():
    a, b = _item("CEM-01", "cemento gris"), _item("VAR-38", "varilla 3/8", unit="unidad")
    service, repo, _ = _service(a, b)
    with pytest.raises(ConflictError):
        asyncio.run(service.update_item(ORG, b.id, {"sku": "cem-01"}))
    asyncio.run(service.update_item(ORG, b.id, {"quantity_available": 75, "unit_price": 19000}))
    assert b.quantity_available == 75 and b.unit_price == 19000
    asyncio.run(service.delete_item(ORG, a.id))
    assert [i.sku for i in asyncio.run(service.list_inventory(ORG))] == ["VAR-38"]
