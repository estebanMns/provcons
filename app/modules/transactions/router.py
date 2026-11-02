from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.transactions.repository import OrderRepository
from app.modules.transactions.service import OrderService
from app.modules.transactions.schemas import OrderCreate, OrderEvaluationOut, OrderOut, OrderTermsRequest
from app.modules.transactions.credit_narrator import AICreditNarrator, TemplateCreditNarrator
from app.modules.forecast.service import ForecastCache
from app.infrastructure.ai_client import AIClient
from app.core.config import settings
from app.dependencies.auth import get_current_user
from app.modules.users.models import User
from app.core.audit import AuditService, AuditRepository

router = APIRouter(prefix="/orders", tags=["Transacciones y negociación"])


# Una por proceso: no gastar la cuota de Gemini cada vez que se reabre la evaluación
_evaluation_cache = ForecastCache()


def get_order_service(db: AsyncSession = Depends(get_db)) -> OrderService:
    audit = AuditService(AuditRepository(db))
    narrator = AICreditNarrator(AIClient()) if settings.gemini_api_key else TemplateCreditNarrator()
    return OrderService(OrderRepository(db), audit, credit_narrator=narrator, cache=_evaluation_cache)


@router.post("", response_model=list[OrderOut])
async def create_orders(
    payload: OrderCreate,
    service: OrderService = Depends(get_order_service),
    current_user: User = Depends(get_current_user),
):
    """Crea órdenes a partir de las ofertas elegidas en una comparación: una
    orden por proveedor (ej. "comprar la mejor combinación" crea varias)."""
    return await service.create_orders(
        quotation_id=payload.quotation_id, match_ids=payload.match_ids,
        payment_terms=payload.payment_terms,
        actor_user_id=current_user.id, actor_org_id=current_user.organization_id,
    )


@router.get("", response_model=list[OrderOut])
async def list_orders(
    service: OrderService = Depends(get_order_service),
    current_user: User = Depends(get_current_user),
):
    """Órdenes de la organización: las que creó (constructora) o recibió (proveedor)."""
    return await service.list_orders(current_user.organization_id)


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: int,
    service: OrderService = Depends(get_order_service),
    current_user: User = Depends(get_current_user),
):
    return await service.get_order(order_id, current_user.organization_id)


@router.get("/{order_id}/evaluation", response_model=OrderEvaluationOut)
async def evaluate_order(
    order_id: int,
    service: OrderService = Depends(get_order_service),
    current_user: User = Depends(get_current_user),
):
    """Para el proveedor, antes de aceptar: cómo cumple la constructora y
    cuántas cuotas le conviene darle, con la explicación de la IA."""
    return await service.evaluate_order(order_id, current_user.organization_id)


@router.post("/{order_id}/confirm", response_model=OrderOut)
async def confirm_order(
    order_id: int,
    payload: OrderTermsRequest,
    service: OrderService = Depends(get_order_service),
    current_user: User = Depends(get_current_user),
):
    """El proveedor acepta con sus condiciones. De contado se confirma de una
    vez; con cuotas queda como propuesta para la constructora."""
    return await service.confirm_order(
        order_id, current_user.id, current_user.organization_id,
        delivery_days=payload.delivery_days, installments=payload.installments,
        monthly_rate_pct=payload.monthly_rate_pct, note=payload.note,
    )


@router.post("/{order_id}/proposal/accept", response_model=OrderOut)
async def accept_proposal(
    order_id: int,
    service: OrderService = Depends(get_order_service),
    current_user: User = Depends(get_current_user),
):
    return await service.respond_proposal(order_id, current_user.id, current_user.organization_id, accept=True)


@router.post("/{order_id}/proposal/reject", response_model=OrderOut)
async def reject_proposal(
    order_id: int,
    service: OrderService = Depends(get_order_service),
    current_user: User = Depends(get_current_user),
):
    """La orden vuelve a esperar al proveedor, que puede proponer otras condiciones."""
    return await service.respond_proposal(order_id, current_user.id, current_user.organization_id, accept=False)


@router.post("/{order_id}/advance", response_model=OrderOut)
async def advance_order(
    order_id: int,
    service: OrderService = Depends(get_order_service),
    current_user: User = Depends(get_current_user),
):
    """El proveedor marca la orden en tránsito y luego entregada."""
    return await service.advance_order(order_id, current_user.id, current_user.organization_id)


@router.post("/{order_id}/cancel", response_model=OrderOut)
async def cancel_order(
    order_id: int,
    service: OrderService = Depends(get_order_service),
    current_user: User = Depends(get_current_user),
):
    return await service.cancel_order(order_id, current_user.id, current_user.organization_id)
