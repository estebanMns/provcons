"""La cotización guarda dirección de entrega, descripción y forma de pago."""

import asyncio

from fastapi.testclient import TestClient

from app.main import app
from app.modules.matching.router import get_matching_service
from app.modules.matching.service import MatchingService
from app.modules.users.auth import get_current_user
from app.modules.users.models import User, UserRole


class FakeQuotationRepo:
    async def save(self, quotation):
        quotation.id = 1
        return quotation


class FakeAudit:
    def __init__(self):
        self.details = None

    async def record(self, action, **kwargs):
        self.details = kwargs.get("details")


def test_crear_cotizacion_guarda_entrega_descripcion_y_cuotas():
    audit = FakeAudit()
    service = MatchingService(FakeQuotationRepo(), None, scoring_strategy=None, audit=audit)
    q = asyncio.run(service.create_quotation(
        constructora_org_id=1, title="Torre B", actor_user_id=1,
        items_data=[{"material_name": "cemento gris", "quantity": 100, "unit": "bulto", "unit_price": None, "specs": {}}],
        delivery_address="  Cra 7 # 45-10, Bogotá ", description="  ", payment_installments=6,
    ))
    assert q.delivery_address == "Cra 7 # 45-10, Bogotá"
    assert q.description is None  # solo espacios: se guarda vacío
    assert q.payment_installments == 6
    assert audit.details["payment_installments"] == 6


def test_subir_sin_direccion_de_entrega_se_rechaza_antes_de_la_ia():
    app.dependency_overrides[get_current_user] = lambda: User(id=1, role=UserRole.admin, organization_id=1)
    app.dependency_overrides[get_matching_service] = lambda: None
    try:
        client = TestClient(app)
        files = {"file": ("lista.pdf", b"%PDF-1.4", "application/pdf")}
        r = client.post("/api/matching/quotations/upload", data={"title": "Obra", "delivery_address": "  "}, files=files)
        assert r.status_code == 422 and "dirección" in r.json()["detail"]
        r = client.post("/api/matching/quotations/upload",
                        data={"delivery_address": "Cra 7 # 45-10", "payment_installments": "13"}, files=files)
        assert r.status_code == 422
    finally:
        app.dependency_overrides.clear()
