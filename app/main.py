import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import DomainError
from app.core.logging import configure_logging, get_logger

from app.modules.users.router import router as users_router
from app.modules.documents_ai.router import router as documents_ai_router
from app.modules.matching.router import router as matching_router
from app.modules.transactions.router import router as transactions_router

# El logging se configura ANTES de crear la app, así cualquier log durante
# el arranque ya sale formateado correctamente.
configure_logging()
logger = get_logger(__name__)

app = FastAPI(title=settings.app_name)

app.include_router(users_router)
app.include_router(documents_ai_router)
app.include_router(matching_router)
app.include_router(transactions_router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Registra método, ruta, código de respuesta y duración de cada request.
    Esto es lo que te permite ver en consola si algo está lento o fallando,
    sin tener que instrumentar cada endpoint a mano."""
    start = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start) * 1000, 2)
    logger.info(
        "%s %s -> %s (%sms)",
        request.method, request.url.path, response.status_code, duration_ms,
    )
    return response


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    """Único lugar que traduce errores de negocio a respuestas HTTP.
    Ningún router necesita try/except manual."""
    logger.warning("DomainError: %s (%s) en %s", exc.message, exc.status_code, request.url.path)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Red de seguridad final: cualquier error no controlado (un bug real,
    no una regla de negocio) se loguea completo para que tú lo veas, pero
    al cliente nunca le llega el detalle interno — solo un mensaje genérico.
    Esto es justo lo que evita que un error tumbe el proceso completo."""
    logger.error("Error no controlado en %s: %s", request.url.path, str(exc), exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})


@app.on_event("startup")
async def on_startup():
    logger.info("=== %s iniciando en modo '%s' ===", settings.app_name, settings.environment)


@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.environment}