from sqlalchemy import String, Integer, ForeignKey, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import Base
from app.db.mixins import TimestampMixin


class AuditLog(Base, TimestampMixin):
    """Registro inmutable de acciones de negocio. Nunca se actualiza ni se
    borra — solo se inserta. created_at (del TimestampMixin) es el momento
    exacto del evento."""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=True)

    action: Mapped[str] = mapped_column(String(100))          # ej. "order.confirmed", "user.login"
    resource_type: Mapped[str] = mapped_column(String(50))    # ej. "Order", "User"
    resource_id: Mapped[int] = mapped_column(Integer, nullable=True)

    details: Mapped[dict] = mapped_column(JSONB, default=dict)  # cualquier dato extra relevante


class AuditRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save(self, entry: AuditLog) -> AuditLog:
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def list_by_resource(self, resource_type: str, resource_id: int) -> list[AuditLog]:
        result = await self.db.execute(
            select(AuditLog).where(
                AuditLog.resource_type == resource_type,
                AuditLog.resource_id == resource_id,
            ).order_by(AuditLog.created_at)
        )
        return list(result.scalars().all())


class AuditService:
    """Único punto por el que cualquier módulo registra un evento de auditoría.
    Se inyecta en los services de negocio (OrderService, UserService, etc.)
    igual que un repository más."""

    def __init__(self, repository: AuditRepository):
        self.repository = repository

    async def record(
        self, action: str, resource_type: str, resource_id: int | None = None,
        actor_user_id: int | None = None, actor_organization_id: int | None = None,
        details: dict | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            action=action, resource_type=resource_type, resource_id=resource_id,
            actor_user_id=actor_user_id, actor_organization_id=actor_organization_id,
            details=details or {},
        )
        return await self.repository.save(entry)