from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from app.core.config import settings


class Base(DeclarativeBase):
    """Clase base para todos los modelos de cada módulo"""
    pass


engine = create_async_engine(
    settings.database_url,
    echo=(settings.environment == "development"),
    poolclass=StaticPool if "sqlite" in settings.database_url else None,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    """Dependencia de FastAPI: entrega una sesión de BD por cada request y la cierra al terminar"""
    async with AsyncSessionLocal() as session:
        yield session