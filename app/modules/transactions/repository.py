from datetime import datetime, timezone
from sqlalchemy import case, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.audit import AuditLog
from app.modules.transactions.credit import ClientHistory
from app.modules.transactions.models import Order, OrderItem, OrderStatus
from app.modules.matching.models import Match, Quotation, QuotationItem
from app.modules.documents_ai.models import ProviderInventoryItem
from app.modules.users.models import Organization


_OPEN = (OrderStatus.pendiente, OrderStatus.confirmada, OrderStatus.en_transito)


class OrderRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, order_id: int) -> Order | None:
        result = await self.db.execute(
            select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
        )
        return result.scalar_one_or_none()

    async def list_by_organization(self, org_id: int) -> list[Order]:
        result = await self.db.execute(
            select(Order).options(selectinload(Order.items))
            .where((Order.constructora_org_id == org_id) | (Order.provider_org_id == org_id))
            .order_by(Order.created_at.desc(), Order.id.desc())
        )
        return list(result.scalars().all())

    async def save(self, order: Order) -> Order:
        return (await self.save_all([order]))[0]

    async def save_all(self, orders: list[Order]) -> list[Order]:
        self.db.add_all(orders)
        await self.db.commit()
        # created_at/updated_at los pone la base de datos: se releen solo esas
        # columnas (un refresh completo descargaría también los items).
        for order in orders:
            await self.db.refresh(order, attribute_names=["created_at", "updated_at"])
        return orders

    async def get_quotation(self, quotation_id: int) -> Quotation | None:
        result = await self.db.execute(select(Quotation).where(Quotation.id == quotation_id))
        return result.scalar_one_or_none()

    async def save_quotation(self, quotation: Quotation) -> None:
        self.db.add(quotation)
        await self.db.commit()

    async def get_offers(self, match_ids: list[int]) -> list[tuple[Match, QuotationItem, ProviderInventoryItem]]:
        """Cada oferta elegida con el material pedido y el producto del proveedor."""
        result = await self.db.execute(
            select(Match, QuotationItem, ProviderInventoryItem)
            .join(QuotationItem, QuotationItem.id == Match.quotation_item_id)
            .join(ProviderInventoryItem, ProviderInventoryItem.id == Match.provider_inventory_id)
            .where(Match.id.in_(match_ids))
        )
        return [tuple(row) for row in result.all()]

    async def ordered_quotation_items(self, quotation_item_ids: list[int]) -> set[int]:
        """Materiales de la cotización que ya están en una orden activa."""
        if not quotation_item_ids:
            return set()
        result = await self.db.execute(
            select(OrderItem.quotation_item_id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(OrderItem.quotation_item_id.in_(quotation_item_ids), Order.status != OrderStatus.cancelada)
        )
        return set(result.scalars().all())

    async def get_organization_names(self, org_ids: set[int]) -> dict[int, str]:
        if not org_ids:
            return {}
        result = await self.db.execute(select(Organization.id, Organization.name).where(Organization.id.in_(org_ids)))
        return dict(result.all())

    async def get_quotation_titles(self, quotation_ids: set[int]) -> dict[int, str]:
        if not quotation_ids:
            return {}
        result = await self.db.execute(select(Quotation.id, Quotation.title).where(Quotation.id.in_(quotation_ids)))
        return dict(result.all())

    async def client_history(
        self, constructora_org_id: int, provider_org_id: int, exclude_order_id: int | None = None,
    ) -> ClientHistory:
        """Cómo ha cumplido la constructora con todos los proveedores, con
        consultas agregadas. No cuenta la orden que se está evaluando."""
        not_this = Order.id != exclude_order_id if exclude_order_id is not None else true()
        rows = await self.db.execute(
            select(
                Order.status, func.count(Order.id),
                func.coalesce(func.sum(Order.total_amount), 0),
                func.sum(case((Order.provider_org_id == provider_org_id, 1), else_=0)),
            )
            .where(Order.constructora_org_id == constructora_org_id, not_this)
            .group_by(Order.status)
        )
        delivered = open_orders = with_provider = delivered_with_provider = 0
        purchased = 0.0
        for status, total, amount, with_prov in rows.all():
            with_provider += int(with_prov or 0)
            if status == OrderStatus.entregada:
                delivered, purchased, delivered_with_provider = total, float(amount), int(with_prov or 0)
            elif status in _OPEN:
                open_orders += total

        # Canceladas por la constructora; los rechazos del proveedor no le restan
        cancelled = await self.db.scalar(
            select(func.count(func.distinct(Order.id)))
            .join(AuditLog, (AuditLog.resource_type == "Order") & (AuditLog.resource_id == Order.id))
            .where(Order.constructora_org_id == constructora_org_id, AuditLog.action == "order.cancelled")
        )
        created = await self.db.scalar(select(Organization.created_at).where(Organization.id == constructora_org_id))
        months = (datetime.now(timezone.utc) - created).days / 30 if created else 0.0

        return ClientHistory(
            delivered=delivered, cancelled_by_client=int(cancelled or 0), open_orders=open_orders,
            total_purchased=purchased, orders_with_provider=with_provider,
            delivered_with_provider=delivered_with_provider, months_on_platform=months,
        )
