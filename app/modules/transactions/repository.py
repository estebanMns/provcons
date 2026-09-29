from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.transactions.models import Order


class OrderRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, order_id: int) -> Order | None:
        result = await self.db.execute(select(Order).where(Order.id == order_id))
        return result.scalar_one_or_none()

    async def list_by_organization(self, org_id: int) -> list[Order]:
        result = await self.db.execute(
            select(Order).where(
                (Order.constructora_org_id == org_id) | (Order.provider_org_id == org_id)
            )
        )
        return list(result.scalars().all())

    async def save(self, order: Order) -> Order:
        self.db.add(order)
        await self.db.commit()
        await self.db.refresh(order)
        return order