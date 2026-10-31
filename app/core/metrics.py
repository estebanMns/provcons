"""Métricas de rendimiento.

Cada medición se registra en dos lugares:
- prometheus_client: formato estándar, expuesto en GET /metrics para que
  cualquier herramienta (Prometheus, Grafana) lo pueda leer
- una ventana en memoria con las últimas N mediciones por serie, de donde
  salen los percentiles p50/p95/p99 que muestra la pantalla "Rendimiento"

El registro es un Singleton por proceso (`metrics`). En el plan gratuito de
Render corre una sola instancia, así que la vista en memoria es la completa.
"""

import asyncio
import math
import time
from collections import defaultdict, deque
from threading import Lock

from prometheus_client import Counter, Gauge, Histogram

from app.core.logging import get_logger

logger = get_logger(__name__)

WINDOW_SIZE = 500  # mediciones que se guardan por serie

HTTP_DURATION = Histogram(
    "http_request_duration_seconds", "Duración de las peticiones HTTP",
    ["method", "route", "status"], buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)
AI_DURATION = Histogram(
    "ai_call_duration_seconds", "Duración de las llamadas a Gemini", ["kind", "outcome"],
    buckets=(0.5, 1, 2, 4, 8, 15, 30, 60),
)
GRPC_DURATION = Histogram(
    "grpc_call_duration_seconds", "Duración de las llamadas al motor gRPC", ["method", "outcome"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5),
)
EVENT_LOOP_LAG = Gauge("event_loop_lag_seconds", "Retraso del event loop de la API")
ENGINE_FALLBACKS = Counter("matching_engine_fallbacks_total", "Veces que se calculó localmente porque el motor gRPC no respondió")
WEB_VITALS = Histogram(
    "web_vitals", "Web Vitals reportados por el navegador (ms; CLS sin unidad)", ["name"],
    buckets=(0.05, 0.1, 0.25, 100, 200, 500, 800, 1000, 1800, 2500, 4000),
)


def percentile(values: list[float], p: float) -> float | None:
    """Percentil con el método del rango más cercano."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]


class RollingWindow:
    def __init__(self, size: int = WINDOW_SIZE):
        self._values: deque[float] = deque(maxlen=size)
        self.total = 0  # mediciones desde que arrancó el proceso

    def add(self, value: float) -> None:
        self._values.append(value)
        self.total += 1

    def stats(self, scale: float = 1000.0, percentiles=(50, 95, 99)) -> dict:
        values = list(self._values)
        out = {"count": self.total}
        for p in percentiles:
            v = percentile(values, p)
            out[f"p{p}"] = round(v * scale, 2) if v is not None else None
        return out


class MetricsRegistry:
    def __init__(self):
        self._lock = Lock()  # también se registra desde hilos (to_thread)
        self.http: dict[tuple[str, str], RollingWindow] = defaultdict(RollingWindow)
        self.http_errors: dict[tuple[str, str], int] = defaultdict(int)
        self.ai: dict[str, RollingWindow] = defaultdict(RollingWindow)
        self.ai_errors: dict[str, int] = defaultdict(int)
        self.grpc: dict[str, RollingWindow] = defaultdict(RollingWindow)
        self.grpc_errors: dict[str, int] = defaultdict(int)
        self.loop_lag = RollingWindow()
        self.fallbacks = 0
        self.web_vitals: dict[str, RollingWindow] = defaultdict(RollingWindow)
        self.started_at = time.time()

    def observe_http(self, method: str, route: str, status: int, seconds: float) -> None:
        HTTP_DURATION.labels(method, route, str(status)).observe(seconds)
        with self._lock:
            self.http[(method, route)].add(seconds)
            if status >= 500:
                self.http_errors[(method, route)] += 1

    def observe_ai(self, kind: str, seconds: float, ok: bool) -> None:
        AI_DURATION.labels(kind, "ok" if ok else "error").observe(seconds)
        with self._lock:
            self.ai[kind].add(seconds)
            if not ok:
                self.ai_errors[kind] += 1

    def observe_grpc(self, method: str, seconds: float, ok: bool) -> None:
        GRPC_DURATION.labels(method, "ok" if ok else "error").observe(seconds)
        with self._lock:
            self.grpc[method].add(seconds)
            if not ok:
                self.grpc_errors[method] += 1

    def observe_loop_lag(self, seconds: float) -> None:
        EVENT_LOOP_LAG.set(seconds)
        with self._lock:
            self.loop_lag.add(seconds)

    def engine_fallback(self) -> None:
        ENGINE_FALLBACKS.inc()
        with self._lock:
            self.fallbacks += 1

    def observe_web_vital(self, name: str, value: float) -> None:
        WEB_VITALS.labels(name).observe(value)
        with self._lock:
            self.web_vitals[name].add(value)

    def summary(self) -> dict:
        with self._lock:
            routes = sorted(
                (
                    {"method": m, "route": r, **w.stats(), "errors": self.http_errors.get((m, r), 0)}
                    for (m, r), w in self.http.items()
                ),
                key=lambda x: -(x["p95"] or 0),
            )
            return {
                "uptime_seconds": round(time.time() - self.started_at),
                "http": routes,
                "ai": [{"kind": k, **w.stats(), "errors": self.ai_errors.get(k, 0)} for k, w in self.ai.items()],
                "grpc": [{"method": k, **w.stats(), "errors": self.grpc_errors.get(k, 0)} for k, w in self.grpc.items()],
                "engine_fallbacks": self.fallbacks,
                "event_loop_lag_ms": {
                    "current": round(self.loop_lag._values[-1] * 1000, 2) if self.loop_lag._values else None,
                    **self.loop_lag.stats(percentiles=(50, 95, 99)),
                },
                # Web Vitals se evalúan en el percentil 75 (criterio de Google)
                "web_vitals": {
                    name: w.stats(scale=1.0, percentiles=(75,)) for name, w in self.web_vitals.items()
                },
            }


metrics = MetricsRegistry()


async def monitor_event_loop_lag(interval: float = 0.5) -> None:
    """Duerme `interval` segundos y mide cuánto se atrasó en despertar. Si algo
    bloquea el event loop (código síncrono pesado), el retraso sube: es la
    señal de que hay trabajo que debería ir a un hilo o a otro proceso."""
    loop = asyncio.get_running_loop()
    while True:
        started = loop.time()
        await asyncio.sleep(interval)
        metrics.observe_loop_lag(max(0.0, loop.time() - started - interval))
