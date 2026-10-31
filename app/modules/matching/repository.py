from sqlalchemy import select, delete, exists, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.matching.models import Quotation, QuotationItem, Match
from app.modules.documents_ai.models import ProviderInventoryItem
from app.modules.transactions.models import Order, OrderItem, OrderStatus
from app.modules.users.models import Organization


class QuotationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, quotation_id: int) -> Quotation | None:
        result = await self.db.execute(select(Quotation).where(Quotation.id == quotation_id))
        return result.scalar_one_or_none()

    async def save(self, quotation: Quotation) -> Quotation:
        self.db.add(quotation)
        await self.db.commit()
        await self.db.refresh(quotation)
        return quotation

    async def list_by_organization(self, org_id: int) -> list[dict]:
        """Cotizaciones de la constructora con cuántos materiales tienen y
        cuántas órdenes activas salieron de ellas."""
        items_count = (
            select(func.count(QuotationItem.id)).where(QuotationItem.quotation_id == Quotation.id).scalar_subquery()
        )
        active_orders = (
            select(func.count(Order.id))
            .where(Order.quotation_id == Quotation.id, Order.status != OrderStatus.cancelada)
            .scalar_subquery()
        )
        result = await self.db.execute(
            select(Quotation, items_count, active_orders)
            .where(Quotation.constructora_org_id == org_id)
            .order_by(Quotation.created_at.desc(), Quotation.id.desc())
        )
        return [
            {
                "id": q.id, "title": q.title, "status": q.status, "created_at": q.created_at,
                "items_count": n_items, "active_orders": n_orders,
            }
            for q, n_items, n_orders in result.all()
        ]

    async def get_items(self, quotation_id: int) -> list[QuotationItem]:
        result = await self.db.execute(
            select(QuotationItem).where(QuotationItem.quotation_id == quotation_id).order_by(QuotationItem.id)
        )
        return list(result.scalars().all())


class MatchRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_inventory(self, limit: int = 5000) -> list[ProviderInventoryItem]:
        """Catálogo de todos los proveedores. Se carga una vez por cotización:
        la comparación por texto se hace en memoria y la revisión con IA
        necesita ver el catálogo completo para encontrar sinónimos."""
        result = await self.db.execute(
            select(ProviderInventoryItem).order_by(ProviderInventoryItem.id).limit(limit)
        )
        return list(result.scalars().all())

    async def delete_unordered_for_items(self, item_ids: list[int]) -> None:
        """Al recalcular se borran los matches anteriores, salvo los que ya
        tienen una orden asociada (esos son historia de la negociación)."""
        if not item_ids:
            return
        await self.db.execute(
            delete(Match).where(
                Match.quotation_item_id.in_(item_ids),
                ~exists().where(Order.match_id == Match.id),
                ~exists().where(OrderItem.match_id == Match.id),
            )
        )

    async def get_offers_for_items(self, item_ids: list[int]) -> list[tuple[Match, ProviderInventoryItem]]:
        """Matches guardados de una cotización con el producto del proveedor."""
        if not item_ids:
            return []
        result = await self.db.execute(
            select(Match, ProviderInventoryItem)
            .join(ProviderInventoryItem, ProviderInventoryItem.id == Match.provider_inventory_id)
            .where(Match.quotation_item_id.in_(item_ids))
            .order_by(Match.id)
        )
        return [tuple(row) for row in result.all()]

    async def save_all(self, matches: list[Match]) -> list[Match]:
        # Un solo commit para todos; con expire_on_commit=False los ids ya
        # quedan cargados tras el flush, sin un refresh por cada fila.
        self.db.add_all(matches)
        await self.db.commit()
        return matches

    async def get_organization_names(self, org_ids: set[int]) -> dict[int, str]:
        if not org_ids:
            return {}
        result = await self.db.execute(select(Organization.id, Organization.name).where(Organization.id.in_(org_ids)))
        return dict(result.all())
