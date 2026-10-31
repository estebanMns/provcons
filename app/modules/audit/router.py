from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.modules.audit.service import AuditQueryService
from app.modules.users.models import User

router = APIRouter(prefix="/audit", tags=["Historial de actividad"])


class AuditEntryOut(BaseModel):
    id: int
    created_at: datetime
    action: str
    resource_type: str
    resource_id: int | None
    actor_name: str | None
    actor_organization_name: str | None
    own_organization: bool
    description: str


@router.get("", response_model=list[AuditEntryOut])
async def list_activity(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    category: Literal["ordenes", "cotizaciones", "inventario", "cuenta"] | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Historial de solo lectura de la organización, del más reciente al más antiguo."""
    return await AuditQueryService(db).list_for_organization(current_user.organization_id, limit, offset, category)
