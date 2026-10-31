"""Indicadores del Resumen (dashboard) según el tipo de organización."""

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents_ai.models import ProviderInventoryItem
from app.modules.matching.models import Match, Quotation, QuotationItem, QuotationStatus
from app.modules.transactions.models import Order, OrderItem, OrderStatus
from app.modules.users.models import Organization, OrgType

ACTIVE = (OrderStatus.pendiente, OrderStatus.confirmada, OrderStatus.en_transito)
OPEN_QUOTATION = (QuotationStatus.abierta, QuotationStatus.en_negociacion)
RECENT_LIMIT = 5


class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def summary(self, org_id: int) -> dict:
        org_type = (await self.db.execute(select(Organization.type).where(Organization.id == org_id))).scalar_one()
        return await (self._provider(org_id) if org_type == OrgType.proveedor else self._constructora(org_id))

    async def _count_orders(self, column, org_id: int, statuses) -> int:
        return (await self.db.execute(
            select(func.count(Order.id)).where(column == org_id, Order.status.in_(statuses))
        )).scalar_one()

    async def _sum_orders(self, column, org_id: int, statuses) -> float:
        return float((await self.db.execute(
            select(func.coalesce(func.sum(Order.total_amount), 0)).where(column == org_id, Order.status.in_(statuses))
        )).scalar_one())

    async def _recent_orders(self, column, org_id: int, counterpart_column) -> list[dict]:
        result = await self.db.execute(
            select(Order, Organization.name)
            .join(Organization, Organization.id == counterpart_column)
            .where(column == org_id)
            .order_by(Order.created_at.desc(), Order.id.desc())
            .limit(RECENT_LIMIT)
        )
        return [
            {"id": o.id, "counterpart": name, "status": o.status.value, "total_amount": o.total_amount, "created_at": o.created_at}
            for o, name in result.all()
        ]

    async def _constructora(self, org_id: int) -> dict:
        open_quotations = (await self.db.execute(
            select(func.count(Quotation.id)).where(Quotation.constructora_org_id == org_id, Quotation.status.in_(OPEN_QUOTATION))
        )).scalar_one()
        return {
            "role": "constructora",
            "open_quotations": open_quotations,
            "active_orders": await self._count_orders(Order.constructora_org_id, org_id, ACTIVE),
            "awaiting_confirmation": await self._count_orders(Order.constructora_org_id, org_id, (OrderStatus.pendiente,)),
            "in_transit": await self._count_orders(Order.constructora_org_id, org_id, (OrderStatus.en_transito,)),
            "delivered_orders": await self._count_orders(Order.constructora_org_id, org_id, (OrderStatus.entregada,)),
            "committed_spend": await self._sum_orders(
                Order.constructora_org_id, org_id, (*ACTIVE, OrderStatus.entregada),
            ),
            "recent_orders": await self._recent_orders(Order.constructora_org_id, org_id, Order.provider_org_id),
        }

    async def _provider(self, org_id: int) -> dict:
        inventory_products = (await self.db.execute(
            select(func.count(func.distinct(func.lower(ProviderInventoryItem.material_name))))
            .where(ProviderInventoryItem.provider_org_id == org_id)
        )).scalar_one()
        opportunities = await self._opportunities(org_id)
        return {
            "role": "proveedor",
            "inventory_products": inventory_products,
            "orders_to_confirm": await self._count_orders(Order.provider_org_id, org_id, (OrderStatus.pendiente,)),
            "orders_to_ship": await self._count_orders(Order.provider_org_id, org_id, (OrderStatus.confirmada,)),
            "in_transit": await self._count_orders(Order.provider_org_id, org_id, (OrderStatus.en_transito,)),
            "delivered_sales": await self._sum_orders(Order.provider_org_id, org_id, (OrderStatus.entregada,)),
            "opportunities_value": round(sum(o["estimated_value"] for o in opportunities), 2),
            "opportunities": opportunities,
            "recent_orders": await self._recent_orders(Order.provider_org_id, org_id, Order.constructora_org_id),
        }

    async def _opportunities(self, org_id: int) -> list[dict]:
        """Cotizaciones abiertas donde el inventario del proveedor coincidió en
        algún material que todavía no está en una orden activa."""
        ordered_items = (
            select(OrderItem.quotation_item_id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.status != OrderStatus.cancelada, OrderItem.quotation_item_id.is_not(None))
        )
        rows = (await self.db.execute(
            select(Match, QuotationItem, Quotation, Organization.name)
            .join(QuotationItem, QuotationItem.id == Match.quotation_item_id)
            .join(Quotation, Quotation.id == QuotationItem.quotation_id)
            .join(Organization, Organization.id == Quotation.constructora_org_id)
            .where(Quotation.status.in_(OPEN_QUOTATION), QuotationItem.id.not_in(ordered_items))
            .order_by(Match.id)
        )).all()

        # Por material y proveedor vale el match más reciente (tras recalcular)
        latest: dict[tuple[int, int], tuple] = {}
        for match, item, quotation, constructora in rows:
            latest[(item.id, match.provider_org_id)] = (match, item, quotation, constructora)

        best_price: dict[int, float] = {}
        for match, item, _, _ in latest.values():
            price = match.criteria_breakdown.get("unit_price")
            if price and (item.id not in best_price or price < best_price[item.id]):
                best_price[item.id] = price

        by_quotation: dict[int, dict] = {}
        for match, item, quotation, constructora in latest.values():
            if match.provider_org_id != org_id:
                continue
            op = by_quotation.setdefault(quotation.id, {
                "quotation_id": quotation.id, "title": quotation.title, "constructora": constructora,
                "created_at": quotation.created_at, "items_matched": 0, "cheapest_items": 0,
                "estimated_value": 0.0, "_scores": [],
            })
            op["items_matched"] += 1
            op["estimated_value"] += match.criteria_breakdown.get("subtotal") or 0
            op["_scores"].append(match.score)
            price = match.criteria_breakdown.get("unit_price")
            if price and price == best_price.get(item.id):
                op["cheapest_items"] += 1
        if not by_quotation:
            return []

        totals = defaultdict(int, dict((await self.db.execute(
            select(QuotationItem.quotation_id, func.count(QuotationItem.id))
            .where(QuotationItem.quotation_id.in_(by_quotation)).group_by(QuotationItem.quotation_id)
        )).all()))
        result = []
        for op in by_quotation.values():
            scores = op.pop("_scores")
            op["items_total"] = totals[op["quotation_id"]]
            op["score"] = round(sum(scores) / len(scores), 3)
            op["estimated_value"] = round(op["estimated_value"], 2)
            result.append(op)
        return sorted(result, key=lambda o: (-o["estimated_value"], -o["score"]))
