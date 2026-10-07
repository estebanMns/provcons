import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import DomainError
from app.core.logging import configure_logging, get_logger
from app.db.session import engine, Base

from app.modules.users.router import router as users_router
from app.modules.documents_ai.router import router as documents_ai_router
from app.modules.matching.router import router as matching_router
from app.modules.transactions.router import router as transactions_router

# El logging se configura ANTES de crear la app, así cualquier log durante
# el arranque ya sale formateado correctamente.
configure_logging()
logger = get_logger(__name__)

_is_dev = settings.environment == "development"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Reemplaza a @app.on_event('startup'), que está deprecado en FastAPI."""
    logger.info("=== %s iniciando en modo '%s' ===", settings.app_name, settings.environment)

    # Crear tablas en desarrollo
    if _is_dev:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Tablas de base de datos creadas/verificadas")

    yield
    logger.info("=== %s detenido ===", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    docs_url="/docs" if _is_dev else None,
    redoc_url="/redoc" if _is_dev else None,
    openapi_url="/openapi.json" if _is_dev else None,
)

app.include_router(users_router, prefix="/api")
app.include_router(documents_ai_router, prefix="/api")
app.include_router(matching_router, prefix="/api")
app.include_router(transactions_router, prefix="/api")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Registra método, ruta, código de respuesta y duración de cada request."""
    start = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start) * 1000, 2)
    logger.info(
        "%s %s -> %s (%sms)",
        request.method, request.url.path, response.status_code, duration_ms,
    )
    return response


# CORS se agrega AL FINAL a propósito: en Starlette el último middleware
# agregado es el más externo, así las respuestas de error (401, 403, 422)
# también llevan los headers CORS y el navegador puede leer el mensaje.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    """Único lugar que traduce errores de negocio a respuestas HTTP."""
    logger.warning("DomainError: %s (%s) en %s", exc.message, exc.status_code, request.url.path)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Red de seguridad final: el detalle interno se loguea, nunca se envía al cliente."""
    logger.error("Error no controlado en %s: %s", request.url.path, str(exc), exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})


@app.get("/health")
async def health():
    return {"status": "ok"}