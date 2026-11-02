"""La pantalla Rendimiento (/api/metrics/summary) es solo del administrador de
la app. El admin de cada empresa no cuenta."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.auth import get_current_user
from app.modules.users.models import User, UserRole


def _as(user: User):
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_overrides():
    yield
    app.dependency_overrides.clear()


def test_el_admin_de_una_empresa_no_ve_el_rendimiento():
    client = _as(User(id=1, role=UserRole.admin, organization_id=1, is_platform_admin=False))
    response = client.get("/api/metrics/summary")
    assert response.status_code == 403


def test_el_administrador_de_la_app_si():
    client = _as(User(id=2, role=UserRole.lector, organization_id=1, is_platform_admin=True))
    response = client.get("/api/metrics/summary")
    assert response.status_code == 200 and "http" in response.json()


def test_los_web_vitals_siguen_abiertos():
    response = TestClient(app).post("/api/metrics/web-vitals", json={"name": "LCP", "value": 1200})
    assert response.status_code == 204
