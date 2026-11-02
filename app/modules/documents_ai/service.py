from dataclasses import dataclass, field

from app.modules.documents_ai.repository import ProviderInventoryRepository
from app.modules.documents_ai.models import AUTO_SKU, ProviderInventoryItem, clean_sku
from app.modules.matching.text_matching import normalize_text
from app.core.audit import AuditService
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.modules.documents_ai.normalizer import DocumentNormalizer

logger = get_logger(__name__)


@dataclass
class ImportResult:
    created: list[ProviderInventoryItem] = field(default_factory=list)
    updated: list[ProviderInventoryItem] = field(default_factory=list)
    skipped: int = 0

    @property
    def items(self) -> list[ProviderInventoryItem]:
        return self.created + self.updated


def _number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _name_key(name: str, unit: str) -> tuple[str, str]:
    return normalize_text(name), normalize_text(unit)


class InventoryService:
    """Inventario de un proveedor:
    - cada producto tiene un código (sku) único dentro del proveedor
    - al importar un archivo, una fila con un código que ya existe SUMA su
      cantidad a ese producto; sin código se busca por nombre y unidad; si no
      existe, se crea
    - las ventas confirmadas descuentan stock (ver OrderService)"""

    def __init__(self, repository: ProviderInventoryRepository, audit: AuditService, normalizer: DocumentNormalizer | None = None):
        self.repository = repository
        self.audit = audit
        self.normalizer = normalizer

    async def import_from_text(
        self, provider_org_id: int, raw_text: str, actor_user_id: int | None = None,
    ) -> ImportResult:
        """Recibe texto crudo (de un PDF/Excel/foto ya extraído), lo normaliza
        con IA y lo guarda en el inventario sumando por código."""
        if self.normalizer is None:
            raise ValueError("Este service no tiene normalizer configurado")
        items_data = await self.normalizer.normalize_inventory_text(raw_text)
        return await self.bulk_import(provider_org_id, items_data, actor_user_id)

    async def list_inventory(self, provider_org_id: int) -> list[ProviderInventoryItem]:
        return await self.repository.list_by_provider(provider_org_id)

    async def add_item(
        self, provider_org_id: int, material_name: str, unit: str,
        unit_price: float, quantity_available: float, specs: dict | None = None,
        sku: str | None = None, actor_user_id: int | None = None,
    ) -> ProviderInventoryItem:
        existing = await self.repository.list_by_provider(provider_org_id, include_inactive=True)
        sku = clean_sku(sku)
        if sku and any(i.sku == sku for i in existing):
            raise ConflictError(f"Ya tienes un producto con el código {sku}")
        item = ProviderInventoryItem(
            provider_org_id=provider_org_id, sku=sku or self._next_sku(existing),
            material_name=material_name, unit=unit, unit_price=unit_price,
            quantity_available=quantity_available, specs=specs or {}, is_active=True,
        )
        saved = await self.repository.save(item)
        logger.info("Ítem de inventario agregado: id=%s sku=%s org=%s", saved.id, saved.sku, provider_org_id)
        await self.audit.record(
            action="inventory.item_added", resource_type="ProviderInventoryItem", resource_id=saved.id,
            actor_user_id=actor_user_id, actor_organization_id=provider_org_id,
            details={"sku": saved.sku, "material_name": material_name, "unit_price": unit_price},
        )
        return saved

    async def bulk_import(
        self, provider_org_id: int, rows: list[dict], actor_user_id: int | None = None,
    ) -> ImportResult:
        existing = await self.repository.list_by_provider(provider_org_id, include_inactive=True)
        by_sku = {i.sku: i for i in existing}
        # Por nombre y unidad se prefieren los productos activos
        by_name: dict[tuple[str, str], ProviderInventoryItem] = {}
        for item in sorted(existing, key=lambda i: i.is_active):
            by_name[_name_key(item.material_name, item.unit)] = item

        result = ImportResult()
        touched: dict[int, ProviderInventoryItem] = {}  # id(obj) -> item, para no repetir
        added: dict[int, float] = {}                     # id(obj) -> cantidad sumada
        for row in rows:
            name = str(row.get("material_name") or "").strip()[:200]
            unit = str(row.get("unit") or "").strip()[:20]
            quantity = _number(row.get("quantity_available")) or 0.0
            price = _number(row.get("unit_price"))
            sku = clean_sku(row.get("sku"))
            if len(name) < 2:
                result.skipped += 1
                continue

            item = by_sku.get(sku) if sku else None
            if item is None:
                item = by_name.get(_name_key(name, unit))
                # Si el producto tenía un código automático y el archivo trae
                # el código real, se adopta para que la próxima vez coincida
                if item is not None and sku and sku not in by_sku and AUTO_SKU.match(item.sku or ""):
                    by_sku.pop(item.sku, None)
                    item.sku = sku
                    by_sku[sku] = item

            if item is not None:
                item.add_stock(quantity)
                if price:
                    item.unit_price = price
                item.is_active = True
                added[id(item)] = added.get(id(item), 0) + quantity
                if id(item) not in touched and item not in result.created:
                    result.updated.append(item)
                touched[id(item)] = item
                continue

            if not price:  # un producto nuevo necesita precio para poder ofrecerse
                result.skipped += 1
                continue
            item = ProviderInventoryItem(
                provider_org_id=provider_org_id, sku=sku or self._next_sku(list(by_sku.values())),
                material_name=name, unit=unit or "unidad", unit_price=price,
                quantity_available=quantity, specs=row.get("specs") if isinstance(row.get("specs"), dict) else {},
                is_active=True,
            )
            by_sku[item.sku] = item
            by_name[_name_key(name, item.unit)] = item
            touched[id(item)] = item
            result.created.append(item)

        if not result.items:
            raise ValidationError("No se encontró ningún producto válido en el archivo")
        await self.repository.save_all(result.items)

        logger.info("Importación: org=%s nuevos=%s sumados=%s omitidos=%s",
                    provider_org_id, len(result.created), len(result.updated), result.skipped)
        for item in result.updated:
            await self.audit.record(
                action="inventory.stock_added", resource_type="ProviderInventoryItem", resource_id=item.id,
                actor_user_id=actor_user_id, actor_organization_id=provider_org_id,
                details={"sku": item.sku, "added": added.get(id(item), 0), "quantity_available": item.quantity_available},
            )
        await self.audit.record(
            action="inventory.bulk_import", resource_type="ProviderInventoryItem",
            actor_user_id=actor_user_id, actor_organization_id=provider_org_id,
            details={"created": len(result.created), "updated": len(result.updated), "skipped": result.skipped},
        )
        return result

    async def update_item(
        self, provider_org_id: int, item_id: int, changes: dict, actor_user_id: int | None = None,
    ) -> ProviderInventoryItem:
        item = await self._get_own(provider_org_id, item_id)
        if "sku" in changes and changes["sku"] is not None:
            sku = clean_sku(changes["sku"])
            if not sku:
                raise ValidationError("El código no puede quedar vacío")
            other = await self.repository.get_by_sku(provider_org_id, sku)
            if other is not None and other.id != item.id:
                raise ConflictError(f"Ya tienes otro producto con el código {sku}")
            item.sku = sku
        for field_name in ("material_name", "unit", "unit_price", "quantity_available"):
            if changes.get(field_name) is not None:
                setattr(item, field_name, changes[field_name])
        saved = await self.repository.save(item)
        await self.audit.record(
            action="inventory.item_updated", resource_type="ProviderInventoryItem", resource_id=saved.id,
            actor_user_id=actor_user_id, actor_organization_id=provider_org_id,
            details={k: v for k, v in changes.items() if v is not None},
        )
        return saved

    async def delete_item(self, provider_org_id: int, item_id: int, actor_user_id: int | None = None) -> None:
        item = await self._get_own(provider_org_id, item_id)
        item.is_active = False
        await self.repository.save(item)
        await self.audit.record(
            action="inventory.item_deleted", resource_type="ProviderInventoryItem", resource_id=item.id,
            actor_user_id=actor_user_id, actor_organization_id=provider_org_id,
            details={"sku": item.sku, "material_name": item.material_name},
        )

    async def _get_own(self, provider_org_id: int, item_id: int) -> ProviderInventoryItem:
        item = await self.repository.get_by_id(item_id)
        if item is None or not item.is_active:
            raise NotFoundError("Producto no encontrado")
        if item.provider_org_id != provider_org_id:
            raise ForbiddenError("Ese producto no es de tu inventario")
        return item

    @staticmethod
    def _next_sku(items: list[ProviderInventoryItem]) -> str:
        numbers = [int(m.group(1)) for i in items if (m := AUTO_SKU.match(i.sku or ""))]
        return f"P-{(max(numbers) if numbers else 0) + 1:04d}"
