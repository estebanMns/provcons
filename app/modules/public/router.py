from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.documents_ai.models import ProviderInventoryItem
from app.modules.matching.models import Match, Quotation, QuotationItem
from app.modules.transactions.models import Order, OrderStatus
from app.modules.users.models import Organization, OrgType

router = APIRouter(prefix="/public", tags=["Público"])


class PublicStats(BaseModel):
    providers: int
    constructoras: int
    catalog_products: int
    quotations_compared: int
    orders_delivered: int


@router.get("/stats", response_model=PublicStats)
async def public_stats(response: Response, db: AsyncSession = Depends(get_db)) -> PublicStats:
    """Cifras agregadas de la plataforma para la página de presentación
    (generada con SSG/ISR en el frontend). Solo conteos: ningún dato privado."""

    async def scalar(query) -> int:
        return int((await db.execute(query)).scalar_one() or 0)

    org_count = lambda org_type: select(func.count(Organization.id)).where(Organization.type == org_type)  # noqa: E731
    stats = PublicStats(
        providers=await scalar(org_count(OrgType.proveedor)),
        constructoras=await scalar(org_count(OrgType.constructora)),
        catalog_products=await scalar(select(func.count(func.distinct(func.lower(ProviderInventoryItem.material_name))))),
        quotations_compared=await scalar(
            select(func.count(func.distinct(Quotation.id)))
            .join(QuotationItem, QuotationItem.quotation_id == Quotation.id)
            .join(Match, Match.quotation_item_id == QuotationItem.id)
        ),
        orders_delivered=await scalar(select(func.count(Order.id)).where(Order.status == OrderStatus.entregada)),
    )
    # Cualquier caché intermedia puede guardar la respuesta 5 minutos
    response.headers["Cache-Control"] = "public, max-age=300"
    return stats
