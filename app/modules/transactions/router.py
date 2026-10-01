from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.transactions.repository import OrderRepository
from app.modules.transactions.service import OrderService
from app.modules.transactions.schemas import OrderCreate, OrderConfirmRequest, OrderOut
from app.dependencies.auth import get_current_user
from app.modules.users.models import User
from app.core.exceptions import ForbiddenError
from app.core.audit import AuditService, AuditRepository

router = APIRouter(prefix="/orders", tags=["Transacciones y negociación"])


def get_order_service(db: AsyncSession = Depends(get_db)) -> OrderService:
    audit = AuditService(AuditRepository(db))
    return OrderService(OrderRepository(db), audit)


def _check_belongs_to_order(order, current_user: User) -> None:
    if current_user.organization_id not in (order.constructora_org_id, order.provider_org_id):
        raise ForbiddenError("No tienes acceso a esta orden")

@router.post("", response_model=OrderOut)
async def create_order(
    payload: OrderCreate,
    service: OrderService = Depends(get_order_service),
    current_user: User = Depends(get_current_user),
):
    return await service.create_order(
        match_id=payload.match_id,
        constructora_org_id=payload.constructora_org_id,
        provider_org_id=payload.provider_org_id,
        actor_user_id=current_user.id,
    )

@router.post("/{order_id}/confirm", response_model=OrderOut)
async def confirm_order(
    order_id: int,
    payload: OrderConfirmRequest,
    service: OrderService = Depends(get_order_service),
    current_user: User = Depends(get_current_user),
):
    order = await service.get_order_or_raise(order_id)
    _check_belongs_to_order(order, current_user)
    return await service.confirm_order(order_id, payload.payment_terms, current_user.id)


@router.post("/{order_id}/cancel", response_model=OrderOut)
async def cancel_order(
    order_id: int,
    service: OrderService = Depends(get_order_service),
    current_user: User = Depends(get_current_user),
):
    order = await service.get_order_or_raise(order_id)
    _check_belongs_to_order(order, current_user)
    return await service.cancel_order(order_id, current_user.id)