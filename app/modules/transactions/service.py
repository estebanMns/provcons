from collections import defaultdict
from dataclasses import astuple
from datetime import datetime, timezone
from app.modules.forecast.service import ForecastCache
from app.modules.transactions.credit import evaluate, installment_plan
from app.modules.transactions.credit_narrator import CreditNarrator, TemplateCreditNarrator
from app.modules.transactions.repository import OrderRepository
from app.modules.transactions.models import Order, OrderItem, OrderStatus, PaymentTerms
from app.modules.matching.models import QuotationStatus
from app.core.exceptions import NotFoundError, ConflictError, ForbiddenError, ValidationError
from app.core.audit import AuditService
from app.core.logging import get_logger

logger = get_logger(__name__)


class OrderService:
    """Reglas de las órdenes:
    - la constructora dueña de la cotización crea las órdenes y puede cancelarlas
    - el proveedor evalúa a la constructora y acepta con sus condiciones
      (cuotas y días de entrega). Si cambian la forma de pago, quedan como
      propuesta hasta que la constructora la acepte
    - el proveedor rechaza, o marca en tránsito y entregada
    - nadie ve ni toca órdenes de las que su organización no es parte"""

    def __init__(
        self, repository: OrderRepository, audit: AuditService,
        credit_narrator: CreditNarrator | None = None, cache: ForecastCache | None = None,
    ):
        self.repository = repository
        self.audit = audit
        self.credit_narrator = credit_narrator or TemplateCreditNarrator()
        self.cache = cache

    async def create_orders(
        self, quotation_id: int, match_ids: list[int], payment_terms: PaymentTerms,
        actor_user_id: int, actor_org_id: int,
    ) -> list[dict]:
        quotation = await self.repository.get_quotation(quotation_id)
        if quotation is None:
            raise NotFoundError("Cotización no encontrada")
        if quotation.constructora_org_id != actor_org_id:
            raise ForbiddenError("Solo la constructora dueña de la cotización puede crear órdenes")

        match_ids = list(dict.fromkeys(match_ids))
        offers = await self.repository.get_offers(match_ids)
        if len(offers) != len(match_ids):
            raise NotFoundError("Alguna de las ofertas elegidas ya no existe; vuelve a comparar proveedores")

        items_seen: dict[int, str] = {}
        for match, quotation_item, _ in offers:
            if quotation_item.quotation_id != quotation_id:
                raise ValidationError("Las ofertas elegidas no pertenecen a esta cotización")
            if quotation_item.id in items_seen:
                raise ValidationError(f"Elegiste más de una oferta para «{quotation_item.material_name}»")
            items_seen[quotation_item.id] = quotation_item.material_name

        already_ordered = await self.repository.ordered_quotation_items(list(items_seen))
        if already_ordered:
            names = ", ".join(sorted(items_seen[i] for i in already_ordered))
            raise ConflictError(f"Ya existe una orden activa para: {names}")

        by_provider: dict[int, list[OrderItem]] = defaultdict(list)
        for match, quotation_item, inventory in offers:
            unit_price = inventory.unit_price
            by_provider[match.provider_org_id].append(OrderItem(
                match_id=match.id,
                quotation_item_id=quotation_item.id,
                requested_material=quotation_item.material_name,
                material_name=inventory.material_name,
                quantity=quotation_item.quantity,
                unit=inventory.unit or quotation_item.unit,
                unit_price=unit_price,
                subtotal=round(unit_price * quotation_item.quantity, 2) if unit_price else None,
            ))

        orders = [
            Order(
                quotation_id=quotation_id,
                constructora_org_id=actor_org_id,
                provider_org_id=provider_org_id,
                payment_terms=payment_terms,
                total_amount=round(sum(i.subtotal or 0 for i in items), 2),
                items=items,
            )
            for provider_org_id, items in by_provider.items()
        ]
        await self.repository.save_all(orders)

        if quotation.status == QuotationStatus.abierta:
            quotation.status = QuotationStatus.en_negociacion
            await self.repository.save_quotation(quotation)

        for order in orders:
            logger.info("Orden creada: id=%s proveedor=%s items=%s", order.id, order.provider_org_id, len(order.items))
            await self.audit.record(
                action="order.created", resource_type="Order", resource_id=order.id,
                actor_user_id=actor_user_id, actor_organization_id=actor_org_id,
                details={
                    "quotation_id": quotation_id, "provider_org_id": order.provider_org_id,
                    "items_count": len(order.items), "total_amount": order.total_amount,
                },
            )
        return await self._to_out(orders)

    async def list_orders(self, org_id: int) -> list[dict]:
        return await self._to_out(await self.repository.list_by_organization(org_id))

    async def get_order(self, order_id: int, actor_org_id: int) -> dict:
        order = await self._get_for_party(order_id, actor_org_id)
        return (await self._to_out([order]))[0]

    async def evaluate_order(self, order_id: int, actor_org_id: int) -> dict:
        """Lo que ve el proveedor antes de aceptar: cómo cumple la constructora
        y cuántas cuotas le conviene darle."""
        order = await self._get_for_party(order_id, actor_org_id)
        if order.provider_org_id != actor_org_id:
            raise ForbiddenError("Solo el proveedor ve la evaluación de la constructora")
        if order.status != OrderStatus.pendiente:
            raise ConflictError("La evaluación solo está disponible antes de aceptar la orden")

        history = await self.repository.client_history(
            order.constructora_org_id, order.provider_org_id, exclude_order_id=order.id,
        )
        amount = order.total_amount or 0.0
        key = (order.id, amount, astuple(history))
        if self.cache and (cached := self.cache.get(key)):
            return cached

        names = await self.repository.get_organization_names({order.constructora_org_id})
        evaluation = {
            "order_id": order.id,
            "constructora_name": names.get(order.constructora_org_id),
            "amount": amount,
            "requested_payment_terms": order.payment_terms,
            **evaluate(amount, history),
        }
        narrative = await self.credit_narrator.narrate(evaluation)
        evaluation["narrative"] = {"source": narrative.source, "summary": narrative.summary, "advice": narrative.advice}
        if self.cache:
            self.cache.set(key, evaluation)
        return evaluation

    async def confirm_order(
        self, order_id: int, actor_user_id: int, actor_org_id: int, *,
        delivery_days: int, installments: int = 1, monthly_rate_pct: float = 0.0,
        note: str | None = None, now: datetime | None = None,
    ) -> dict:
        """El proveedor acepta con sus condiciones. Si deja el pago de contado
        como lo pidió la constructora, la orden queda confirmada; si no, se
        envía como propuesta."""
        order = await self._get_for_party(order_id, actor_org_id)
        if order.provider_org_id != actor_org_id:
            raise ForbiddenError("Solo el proveedor puede confirmar la orden")
        now = now or datetime.now(timezone.utc)
        # El valor de la cuota se recalcula aquí: nunca se guarda el del navegador
        plan = installment_plan(order.total_amount or 0.0, installments, monthly_rate_pct)
        terms = {
            "installments": plan["installments"],
            "monthly_rate_pct": plan["monthly_rate_pct"],
            "installment_amount": plan["installment_amount"],
            "financed_total": plan["financed_total"],
            "delivery_days": delivery_days,
            "note": (note or "").strip() or None,
        }
        needs_approval = order.requires_client_approval(installments)
        try:
            if needs_approval:
                order.propose(terms, now)
            else:
                order.confirm_directly(terms, now)
        except ValueError as e:
            raise ConflictError(str(e))
        action = "order.proposed" if needs_approval else "order.confirmed"
        return await self._save_and_record(order, action, actor_user_id, actor_org_id, details=terms)

    async def respond_proposal(
        self, order_id: int, actor_user_id: int, actor_org_id: int, accept: bool, now: datetime | None = None,
    ) -> dict:
        order = await self._get_for_party(order_id, actor_org_id)
        if order.constructora_org_id != actor_org_id:
            raise ForbiddenError("Solo la constructora puede responder la propuesta")
        try:
            if accept:
                order.accept_proposal(now or datetime.now(timezone.utc))
            else:
                order.reject_proposal()
        except ValueError as e:
            raise ConflictError(str(e))
        action = "order.proposal_accepted" if accept else "order.proposal_rejected"
        return await self._save_and_record(order, action, actor_user_id, actor_org_id)

    async def advance_order(self, order_id: int, actor_user_id: int, actor_org_id: int) -> dict:
        order = await self._get_for_party(order_id, actor_org_id)
        if order.provider_org_id != actor_org_id:
            raise ForbiddenError("Solo el proveedor puede actualizar el envío")
        try:
            order.advance()
        except ValueError as e:
            raise ConflictError(str(e))
        return await self._save_and_record(order, f"order.{order.status.value}", actor_user_id, actor_org_id)

    async def cancel_order(self, order_id: int, actor_user_id: int, actor_org_id: int) -> dict:
        """La constructora la cancela; el proveedor la rechaza. Ambas dejan la
        orden cancelada y liberan los materiales para pedirlos a otro proveedor."""
        order = await self._get_for_party(order_id, actor_org_id)
        if not order.can_be_cancelled():
            raise ConflictError("Esta orden ya no puede cancelarse")
        action = "order.rejected" if actor_org_id == order.provider_org_id else "order.cancelled"
        order.status = OrderStatus.cancelada
        order.proposal = None
        return await self._save_and_record(order, action, actor_user_id, actor_org_id)

    async def _get_for_party(self, order_id: int, actor_org_id: int) -> Order:
        order = await self.repository.get_by_id(order_id)
        if order is None:
            raise NotFoundError("Orden no encontrada")
        if actor_org_id not in (order.constructora_org_id, order.provider_org_id):
            raise ForbiddenError("No tienes acceso a esta orden")
        return order

    async def _save_and_record(
        self, order: Order, action: str, actor_user_id: int, actor_org_id: int, details: dict | None = None,
    ) -> dict:
        await self.repository.save(order)
        logger.info("Orden %s: id=%s estado=%s", action, order.id, order.status.value)
        await self.audit.record(
            action=action, resource_type="Order", resource_id=order.id,
            actor_user_id=actor_user_id, actor_organization_id=actor_org_id,
            details={"status": order.status.value, **(details or {})},
        )
        return (await self._to_out([order]))[0]

    async def _to_out(self, orders: list[Order]) -> list[dict]:
        names = await self.repository.get_organization_names(
            {o.constructora_org_id for o in orders} | {o.provider_org_id for o in orders}
        )
        titles = await self.repository.get_quotation_titles({o.quotation_id for o in orders if o.quotation_id})
        now = datetime.now(timezone.utc)
        return [
            {
                "id": o.id,
                "quotation_id": o.quotation_id,
                "quotation_title": titles.get(o.quotation_id),
                "constructora_org_id": o.constructora_org_id,
                "constructora_name": names.get(o.constructora_org_id),
                "provider_org_id": o.provider_org_id,
                "provider_name": names.get(o.provider_org_id),
                "status": o.status,
                "payment_terms": o.payment_terms,
                "total_amount": o.total_amount,
                "items": o.items,
                "installments": o.installments,
                "monthly_rate_pct": o.monthly_rate_pct,
                "installment_amount": o.installment_amount,
                "financed_total": o.financed_total,
                "delivery_days": o.delivery_days,
                "promised_delivery_at": o.promised_delivery_at,
                "delivered_at": o.delivered_at,
                "delay_days": o.delay_days(now),
                "proposal": o.proposal,
                "created_at": o.created_at,
                "updated_at": o.updated_at,
            }
            for o in orders
        ]
