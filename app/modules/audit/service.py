from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditLog, AuditRepository
from app.modules.users.models import Organization, User


# Filtros del historial: categoría -> prefijos de las acciones que incluye
CATEGORY_PREFIXES = {
    "ordenes": ("order.",),
    "cotizaciones": ("quotation.", "matching."),
    "inventario": ("inventory.",),
    "cuenta": ("user.", "organization."),
}


def _cop(value) -> str:
    try:
        return "$" + f"{float(value):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return ""


def describe(entry: AuditLog, org_names: dict[int, str]) -> str:
    """Frase en español para mostrar el evento en el historial."""
    d = entry.details or {}
    rid = entry.resource_id
    # Los eventos antiguos no traen todos los datos: cada parte se agrega solo si existe
    provider = f" a {org_names[d['provider_org_id']]}" if d.get("provider_org_id") in org_names else ""
    total = f" por {_cop(d['total_amount'])}" if d.get("total_amount") else ""
    providers = f" de {d['providers_compared']} proveedor(es)" if d.get("providers_compared") is not None else ""
    texts = {
        "user.registered": "Se registró un usuario",
        "user.login": "Inició sesión",
        "organization.created": "Creó la organización",
        "inventory.item_added": f"Agregó «{d.get('material_name', 'un producto')}» al inventario",
        "inventory.bulk_import": f"Importó {d.get('items_count', 0)} productos al inventario",
        "inventory.file_imported": f"Subió el archivo de inventario «{d.get('file_name', '')}»".replace(" «»", ""),
        "quotation.created": f"Creó la cotización «{d.get('title', f'#{rid}')}» con {d.get('items_count', 0)} materiales",
        "matching.run": f"Comparó proveedores para la cotización #{rid}: {d.get('matches_generated', 0)} ofertas{providers}",
        "order.created": f"Creó la orden #{rid}{provider}{total}",
        "order.confirmed": f"Confirmó la orden #{rid}",
        "order.en_transito": f"Despachó la orden #{rid}",
        "order.entregada": f"Marcó como entregada la orden #{rid}",
        "order.cancelled": f"Canceló la orden #{rid}",
        "order.rejected": f"Rechazó la orden #{rid}",
    }
    return texts.get(entry.action, f"{entry.action} ({entry.resource_type} #{rid})")


class AuditQueryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = AuditRepository(db)

    async def list_for_organization(
        self, org_id: int, limit: int = 50, offset: int = 0, category: str | None = None,
    ) -> list[dict]:
        prefixes = CATEGORY_PREFIXES.get(category) if category else None
        entries = await self.repository.list_for_organization(org_id, limit, offset, prefixes)

        user_ids = {e.actor_user_id for e in entries if e.actor_user_id}
        org_ids = {e.actor_organization_id for e in entries if e.actor_organization_id}
        org_ids |= {e.details.get("provider_org_id") for e in entries if (e.details or {}).get("provider_org_id")}
        users = dict((await self.db.execute(select(User.id, User.full_name).where(User.id.in_(user_ids)))).all()) if user_ids else {}
        orgs = dict((await self.db.execute(select(Organization.id, Organization.name).where(Organization.id.in_(org_ids)))).all()) if org_ids else {}

        return [
            {
                "id": e.id,
                "created_at": e.created_at,
                "action": e.action,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "actor_name": users.get(e.actor_user_id),
                "actor_organization_name": orgs.get(e.actor_organization_id),
                "own_organization": e.actor_organization_id == org_id,
                "description": describe(e, orgs),
            }
            for e in entries
        ]
