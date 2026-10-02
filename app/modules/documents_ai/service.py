from app.modules.documents_ai.repository import ProviderInventoryRepository
from app.modules.documents_ai.models import ProviderInventoryItem
from app.core.audit import AuditService
from app.core.logging import get_logger
from app.modules.documents_ai.normalizer import DocumentNormalizer

logger = get_logger(__name__)


class InventoryService:
    def __init__(self, repository: ProviderInventoryRepository, audit: AuditService, normalizer: DocumentNormalizer | None = None):
        self.repository = repository
        self.audit = audit
        self.normalizer = normalizer

    async def import_from_text(
        self, provider_org_id: int, raw_text: str, actor_user_id: int | None = None,
    ) -> list[ProviderInventoryItem]:
        """Punto de entrada real: recibe texto crudo (de un PDF/Excel/foto ya
        extraído), lo normaliza con IA, y lo guarda como inventario."""
        if self.normalizer is None:
            raise ValueError("Este service no tiene normalizer configurado")

        items_data = await self.normalizer.normalize_inventory_text(raw_text)
        return await self.bulk_import(provider_org_id, items_data, actor_user_id)

    async def add_item(
        self, provider_org_id: int, material_name: str, unit: str,
        unit_price: float, quantity_available: float, specs: dict | None = None,
        actor_user_id: int | None = None,
    ) -> ProviderInventoryItem:
        item = ProviderInventoryItem(
            provider_org_id=provider_org_id, material_name=material_name,
            unit=unit, unit_price=unit_price, quantity_available=quantity_available,
            specs=specs or {},
        )
        saved = await self.repository.save(item)

        logger.info("Ítem de inventario agregado: id=%s material=%s org=%s", saved.id, material_name, provider_org_id)
        await self.audit.record(
            action="inventory.item_added", resource_type="ProviderInventoryItem", resource_id=saved.id,
            actor_user_id=actor_user_id, actor_organization_id=provider_org_id,
            details={"material_name": material_name, "unit_price": unit_price},
        )
        return saved

    async def list_inventory(self, provider_org_id: int) -> list[ProviderInventoryItem]:
        return await self.repository.list_by_provider(provider_org_id)

    async def bulk_import(
        self, provider_org_id: int, rows: list[dict], actor_user_id: int | None = None,
    ) -> list[ProviderInventoryItem]:
        """Punto de entrada que va a usar el futuro pipeline de OCR/LLM:
        recibe filas ya estructuradas y las guarda todas."""
        logger.info("Iniciando importación masiva: %s filas para org=%s", len(rows), provider_org_id)
        saved_items = []
        for row in rows:
            item = await self.add_item(
                provider_org_id=provider_org_id,
                material_name=row["material_name"],
                unit=row["unit"],
                unit_price=row["unit_price"],
                quantity_available=row.get("quantity_available", 0),
                specs=row.get("specs", {}),
                actor_user_id=actor_user_id,
            )
            saved_items.append(item)

        await self.audit.record(
            action="inventory.bulk_import", resource_type="ProviderInventoryItem",
            actor_user_id=actor_user_id, actor_organization_id=provider_org_id,
            details={"items_count": len(saved_items)},
        )
        return saved_items