from app.modules.transactions.repository import OrderRepository
from app.modules.transactions.models import Order, PaymentTerms, OrderStatus
from app.core.exceptions import NotFoundError, ConflictError
from app.core.audit import AuditService
from app.core.logging import get_logger

logger = get_logger(__name__)


class OrderService:
    def __init__(self, repository: OrderRepository, audit: AuditService):
        self.repository = repository
        self.audit = audit

    async def create_order(
        self, match_id: int, constructora_org_id: int, provider_org_id: int, actor_user_id: int,
    ) -> Order:
        order = Order(
            match_id=match_id, constructora_org_id=constructora_org_id,
            provider_org_id=provider_org_id, status=OrderStatus.pendiente,
        )
        saved = await self.repository.save(order)

        logger.info("Orden creada: id=%s match=%s", saved.id, match_id)
        await self.audit.record(
            action="order.created", resource_type="Order", resource_id=saved.id,
            actor_user_id=actor_user_id, actor_organization_id=constructora_org_id,
        )
        return saved

    async def get_order_or_raise(self, order_id: int) -> Order:
        order = await self.repository.get_by_id(order_id)
        if order is None:
            raise NotFoundError("Orden no encontrada")
        return order

    async def confirm_order(self, order_id: int, payment_terms: PaymentTerms, actor_user_id: int) -> Order:
        order = await self.get_order_or_raise(order_id)
        try:
            order.confirm(payment_terms)
        except ValueError as e:
            raise ConflictError(str(e))
        saved = await self.repository.save(order)

        logger.info("Orden confirmada: id=%s payment_terms=%s", saved.id, payment_terms.value)
        await self.audit.record(
            action="order.confirmed", resource_type="Order", resource_id=saved.id,
            actor_user_id=actor_user_id, actor_organization_id=saved.constructora_org_id,
            details={"payment_terms": payment_terms.value},
        )
        return saved

    async def cancel_order(self, order_id: int, actor_user_id: int) -> Order:
        order = await self.get_order_or_raise(order_id)
        if not order.can_be_cancelled():
            raise ConflictError("Esta orden ya no puede cancelarse")

        order.status = OrderStatus.cancelada
        saved = await self.repository.save(order)

        logger.info("Orden cancelada: id=%s", saved.id)
        await self.audit.record(
            action="order.cancelled", resource_type="Order", resource_id=saved.id,
            actor_user_id=actor_user_id, actor_organization_id=saved.constructora_org_id,
        )
        return saved