import logging
import sys

from app.core.config import settings


def configure_logging() -> None:
    """Configura el logging de toda la aplicación. Se llama una sola vez,
    al arrancar, desde main.py."""

    level = logging.DEBUG if settings.environment == "development" else logging.INFO

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers = [handler]  # evita handlers duplicados si se llama más de una vez

    # SQLAlchemy es muy ruidoso en INFO — lo bajamos a WARNING salvo que
    # quieras ver cada query SQL explícitamente
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Cada módulo pide su propio logger así: logger = get_logger(__name__)"""
    return logging.getLogger(name)