from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.documents_ai.models import ProviderInventoryItem


class ProviderInventoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_provider(self, provider_org_id: int) -> list[ProviderInventoryItem]:
        result = await self.db.execute(
            select(ProviderInventoryItem).where(
                ProviderInventoryItem.provider_org_id == provider_org_id
            )
        )
        return list(result.scalars().all())

    async def get_by_id(self, item_id: int) -> ProviderInventoryItem | None:
        result = await self.db.execute(
            select(ProviderInventoryItem).where(ProviderInventoryItem.id == item_id)
        )
        return result.scalar_one_or_none()

    async def save(self, item: ProviderInventoryItem) -> ProviderInventoryItem:
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return item