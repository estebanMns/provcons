from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.modules.dashboard.service import DashboardService
from app.modules.users.models import User

router = APIRouter(prefix="/dashboard", tags=["Resumen"])


@router.get("/summary", response_model=dict)
async def summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Indicadores del Resumen. Constructora: cotizaciones, órdenes y gasto.
    Proveedor: inventario, órdenes por atender, ventas y oportunidades."""
    return await DashboardService(db).summary(current_user.organization_id)
