# Importa aquí todos los modelos de todos los módulos, para que Alembic
# los detecte al generar migraciones automáticas.
from app.db.session import Base  # noqa
from app.core.audit import AuditLog  # noqa
from app.modules.users.models import Organization, User  # noqa
from app.modules.documents_ai.models import ProviderInventoryItem  # noqa
from app.modules.matching.models import Quotation, QuotationItem, Match  # noqa
from app.modules.transactions.models import Order  # noqa