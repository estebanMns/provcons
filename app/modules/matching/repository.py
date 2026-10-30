from sqlalchemy import select, delete, func, or_, exists
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.matching.models import Quotation, QuotationItem, Match
from app.modules.documents_ai.models import ProviderInventoryItem
from app.modules.transactions.models import Order
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

    async def get_items(self, quotation_id: int) -> list[QuotationItem]:
        result = await self.db.execute(
            select(QuotationItem).where(QuotationItem.quotation_id == quotation_id).order_by(QuotationItem.id)
        )
        return list(result.scalars().all())


class MatchRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_candidate_inventory(self, terms: list[str]) -> list[ProviderInventoryItem]:
        """Pre-filtro amplio: ítems cuyo nombre contiene alguna de las palabras
        del material pedido (sin tildes ni mayúsculas). La decisión fina de si
        es el mismo material la toma text_matching.material_similarity."""
        if not terms:
            return []
        normalized_name = func.translate(func.lower(ProviderInventoryItem.material_name), "áéíóúüñ", "aeiouun")
        result = await self.db.execute(
            select(ProviderInventoryItem).where(or_(*(normalized_name.like(f"%{term}%") for term in terms)))
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
            )
        )

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
