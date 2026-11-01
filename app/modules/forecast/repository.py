from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditLog
from app.modules.forecast.predictors import PricePoint, ProviderHistory
from app.modules.matching.text_matching import normalize_text
from app.modules.transactions.models import Order, OrderItem, OrderStatus

PRICE_HISTORY_DAYS = 365
MAX_PRICE_POINTS = 5000
_OPEN = (OrderStatus.pendiente, OrderStatus.confirmada, OrderStatus.en_transito)


class ProviderHistoryRepository:
    """Historial de los proveedores, armado con consultas agregadas (una por
    señal, no una por proveedor) sobre las órdenes y el registro de auditoría."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def provider_history(
        self, provider_ids: set[int], constructora_org_id: int, now: datetime | None = None,
    ) -> dict[int, ProviderHistory]:
        if not provider_ids:
            return {}
        now = now or datetime.now(timezone.utc)
        data: dict[int, dict] = {
            pid: {"delivered": 0, "rejected": 0, "open_orders": 0, "orders_with_client": 0,
                  "lead_times_days": [], "price_points": []}
            for pid in provider_ids
        }

        # 1. Órdenes por estado, y cuántas son con esta constructora
        counts = await self.db.execute(
            select(
                Order.provider_org_id, Order.status, func.count(Order.id),
                func.sum(case((Order.constructora_org_id == constructora_org_id, 1), else_=0)),
            )
            .where(Order.provider_org_id.in_(provider_ids))
            .group_by(Order.provider_org_id, Order.status)
        )
        for provider_id, status, total, with_client in counts.all():
            d = data[provider_id]
            d["orders_with_client"] += int(with_client or 0)
            if status == OrderStatus.entregada:
                d["delivered"] += total
            elif status in _OPEN:
                d["open_orders"] += total

        # 2. Rechazos: canceladas por el proveedor (la constructora cancelando
        # no habla mal del proveedor, así que no cuenta)
        rejected = await self.db.execute(
            select(Order.provider_org_id, func.count(func.distinct(Order.id)))
            .join(AuditLog, (AuditLog.resource_type == "Order") & (AuditLog.resource_id == Order.id))
            .where(Order.provider_org_id.in_(provider_ids), AuditLog.action == "order.rejected")
            .group_by(Order.provider_org_id)
        )
        for provider_id, total in rejected.all():
            data[provider_id]["rejected"] = total

        # 3. Días entre la creación de la orden y su entrega
        deliveries = await self.db.execute(
            select(Order.provider_org_id, Order.created_at, AuditLog.created_at)
            .join(AuditLog, (AuditLog.resource_type == "Order") & (AuditLog.resource_id == Order.id))
            .where(Order.provider_org_id.in_(provider_ids), AuditLog.action == "order.entregada")
        )
        for provider_id, created, delivered in deliveries.all():
            days = (delivered - created).total_seconds() / 86400
            if days >= 0:
                data[provider_id]["lead_times_days"].append(round(days, 2))

        # 4. Precios con los que se le compró en el último año (congelados en
        # cada orden), para la tendencia
        since = now - timedelta(days=PRICE_HISTORY_DAYS)
        prices = await self.db.execute(
            select(Order.provider_org_id, OrderItem.material_name, OrderItem.unit_price, OrderItem.created_at)
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                Order.provider_org_id.in_(provider_ids),
                OrderItem.unit_price.is_not(None), OrderItem.created_at >= since,
            )
            .order_by(OrderItem.created_at.desc())
            .limit(MAX_PRICE_POINTS)
        )
        for provider_id, name, price, created in prices.all():
            data[provider_id]["price_points"].append(PricePoint(
                day=(created - since).total_seconds() / 86400,
                material_key=normalize_text(name), unit_price=float(price),
            ))

        return {
            pid: ProviderHistory(
                delivered=d["delivered"], rejected=d["rejected"], open_orders=d["open_orders"],
                orders_with_client=d["orders_with_client"],
                lead_times_days=tuple(d["lead_times_days"]), price_points=tuple(d["price_points"]),
            )
            for pid, d in data.items()
        }
