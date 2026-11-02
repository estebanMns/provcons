from typing import Literal

from fastapi import APIRouter, Depends, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from app.core.metrics import metrics
from app.dependencies.auth import require_platform_admin
from app.modules.users.models import User

router = APIRouter(prefix="/metrics", tags=["Métricas de rendimiento"])
prometheus_router = APIRouter(tags=["Métricas de rendimiento"])


@prometheus_router.get("/metrics", include_in_schema=False)
async def prometheus_metrics() -> Response:
    """Formato estándar de Prometheus. Solo cifras agregadas (sin datos de
    usuarios), por eso es público como en la mayoría de servicios."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/summary")
async def metrics_summary(admin: User = Depends(require_platform_admin)) -> dict:
    """Percentiles por ruta, IA, gRPC, event loop y Web Vitals (pantalla
    Rendimiento). Solo el administrador de la app."""
    return metrics.summary()


class WebVital(BaseModel):
    # Las métricas de Core Web Vitals y afines que reporta Next.js
    name: Literal["LCP", "INP", "CLS", "FCP", "TTFB", "FID"]
    value: float = Field(ge=0, le=120_000)


@router.post("/web-vitals", status_code=204)
async def report_web_vital(vital: WebVital) -> Response:
    """Lo envía el navegador al cargar cada página. No requiere sesión (se
    reporta también desde páginas públicas) y solo guarda el valor agregado."""
    metrics.observe_web_vital(vital.name, vital.value)
    return Response(status_code=204)
