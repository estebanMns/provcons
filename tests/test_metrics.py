import asyncio
import time

from fastapi.testclient import TestClient

from app.core.metrics import MetricsRegistry, RollingWindow, metrics, monitor_event_loop_lag, percentile
from app.main import app


def test_percentiles_por_rango_mas_cercano():
    values = [i / 100 for i in range(1, 101)]  # 0.01 .. 1.00
    assert percentile(values, 50) == 0.5
    assert percentile(values, 95) == 0.95
    assert percentile([], 95) is None


def test_ventana_guarda_solo_las_ultimas_mediciones():
    window = RollingWindow(size=3)
    for v in (10, 20, 30, 1000):
        window.add(v / 1000)
    stats = window.stats()
    assert stats["count"] == 4          # total histórico
    assert stats["p99"] == 1000.0       # ms; el 10 ya salió de la ventana
    assert stats["p50"] == 30.0


def test_resumen_agrupa_por_ruta_y_cuenta_errores():
    registry = MetricsRegistry()
    registry.observe_http("GET", "/api/orders", 200, 0.05)
    registry.observe_http("GET", "/api/orders", 500, 0.20)
    registry.observe_grpc("ComputeSimilarities", 0.01, ok=True)
    registry.engine_fallback()
    summary = registry.summary()
    orders = next(r for r in summary["http"] if r["route"] == "/api/orders")
    assert orders["count"] == 2 and orders["errors"] == 1
    assert summary["grpc"][0]["method"] == "ComputeSimilarities"
    assert summary["engine_fallbacks"] == 1


def test_el_monitor_detecta_un_event_loop_bloqueado():
    registry_before = metrics.loop_lag.total

    async def scenario():
        monitor = asyncio.create_task(monitor_event_loop_lag(interval=0.05))
        await asyncio.sleep(0.12)   # mediciones normales
        time.sleep(0.3)             # código síncrono que bloquea el loop
        await asyncio.sleep(0.12)
        monitor.cancel()

    asyncio.run(scenario())
    stats = metrics.loop_lag.stats()
    assert metrics.loop_lag.total > registry_before
    assert stats["p99"] >= 200      # el bloqueo de 300 ms se ve como retraso


def test_endpoints_de_metricas():
    with TestClient(app) as client:
        client.get("/health")
        prom = client.get("/metrics")
        assert prom.status_code == 200
        assert "http_request_duration_seconds" in prom.text
        assert 'route="/health"' in prom.text  # plantilla de ruta, no la URL

        assert client.post("/api/metrics/web-vitals", json={"name": "LCP", "value": 1234}).status_code == 204
        assert client.post("/api/metrics/web-vitals", json={"name": "OTRA", "value": 1}).status_code == 422
        assert client.get("/api/metrics/summary").status_code in (401, 403)  # requiere sesión
    assert metrics.web_vitals["LCP"].total >= 1
