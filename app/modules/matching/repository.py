from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.matching.models import Quotation, QuotationItem, Match
from app.modules.documents_ai.models import ProviderInventoryItem


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
            select(QuotationItem).where(QuotationItem.quotation_id == quotation_id)
        )
        return list(result.scalars().all())


class MatchRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_candidate_inventory(self, material_name: str) -> list[ProviderInventoryItem]:
        result = await self.db.execute(
            select(ProviderInventoryItem).where(ProviderInventoryItem.material_name == material_name)
        )
        return list(result.scalars().all())

    async def save(self, match: Match) -> Match:
        self.db.add(match)
        await self.db.commit()
        await self.db.refresh(match)
        return match