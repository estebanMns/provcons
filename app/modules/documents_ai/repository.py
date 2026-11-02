from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.documents_ai.models import ProviderInventoryItem


class ProviderInventoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_provider(self, provider_org_id: int, include_inactive: bool = False) -> list[ProviderInventoryItem]:
        query = select(ProviderInventoryItem).where(ProviderInventoryItem.provider_org_id == provider_org_id)
        if not include_inactive:
            query = query.where(ProviderInventoryItem.is_active.is_(True))
        result = await self.db.execute(query.order_by(ProviderInventoryItem.id))
        return list(result.scalars().all())

    async def get_by_id(self, item_id: int) -> ProviderInventoryItem | None:
        result = await self.db.execute(
            select(ProviderInventoryItem).where(ProviderInventoryItem.id == item_id)
        )
        return result.scalar_one_or_none()

    async def get_by_sku(self, provider_org_id: int, sku: str) -> ProviderInventoryItem | None:
        """Incluye los eliminados: el código sigue siendo de ese producto."""
        result = await self.db.execute(
            select(ProviderInventoryItem).where(
                ProviderInventoryItem.provider_org_id == provider_org_id, ProviderInventoryItem.sku == sku,
            )
        )
        return result.scalar_one_or_none()

    async def save(self, item: ProviderInventoryItem) -> ProviderInventoryItem:
        return (await self.save_all([item]))[0]

    async def save_all(self, items: list[ProviderInventoryItem]) -> list[ProviderInventoryItem]:
        """Una sola transacción: un archivo se guarda completo o no se guarda."""
        self.db.add_all(items)
        await self.db.commit()
        for item in items:
            await self.db.refresh(item)
        return items
