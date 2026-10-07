from app.modules.users.repository import UserRepository, OrganizationRepository
from app.modules.users.models import User, UserRole, Organization, OrgType
from app.core.exceptions import ConflictError, NotFoundError, UnauthorizedError
from app.core.security import create_access_token
from app.core.audit import AuditService
from app.core.logging import get_logger

logger = get_logger(__name__)


class UserService:
    def __init__(self, user_repo: UserRepository, org_repo: OrganizationRepository, audit: AuditService):
        self.user_repo = user_repo
        self.org_repo = org_repo
        self.audit = audit

    async def register_user(
        self, organization_id: int, email: str, raw_password: str,
        full_name: str, role: UserRole = UserRole.lector,
    ) -> User:
        existing = await self.user_repo.get_by_email(email)
        if existing is not None:
            logger.warning("Intento de registro con correo duplicado: %s", email)
            raise ConflictError("Ya existe un usuario con ese correo")

        organization = await self.org_repo.get_by_id(organization_id)
        if organization is None:
            raise NotFoundError("La organización no existe")

        user = User(email=email, full_name=full_name, role=role, organization_id=organization_id)
        user.set_password(raw_password)
        saved = await self.user_repo.save(user)

        logger.info("Usuario registrado: id=%s email=%s org=%s", saved.id, saved.email, organization_id)
        await self.audit.record(
            action="user.registered", resource_type="User", resource_id=saved.id,
            actor_user_id=saved.id, actor_organization_id=organization_id,
        )
        return saved

    async def authenticate(self, email: str, raw_password: str) -> User:
        user = await self.user_repo.get_by_email(email)
        if user is None or not user.verify_password(raw_password):
            logger.warning("Intento de login fallido: %s", email)
            raise UnauthorizedError("Credenciales inválidas")
        return user

    async def login(self, email: str, raw_password: str) -> str:
        user = await self.authenticate(email, raw_password)
        logger.info("Login exitoso: id=%s email=%s", user.id, user.email)
        await self.audit.record(
            action="user.login", resource_type="User", resource_id=user.id,
            actor_user_id=user.id, actor_organization_id=user.organization_id,
        )
        return create_access_token(
            subject=user.id,
            extra_claims={"organization_id": user.organization_id, "role": user.role.value},
        )

    async def signup_with_organization(
        self, organization_name: str, organization_type: OrgType, tax_id: str | None,
        email: str, raw_password: str, full_name: str,
    ) -> User:
        """Onboarding: crea la organización + primer usuario (admin) en una sola operación."""
        existing_user = await self.user_repo.get_by_email(email)
        if existing_user is not None:
            raise ConflictError("Ya existe un usuario con ese correo")

        if tax_id:
            existing_org = await self.org_repo.get_by_tax_id(tax_id)
            if existing_org is not None:
                raise ConflictError("Ya existe una organización con ese NIT")

        org = Organization(name=organization_name, type=organization_type, tax_id=tax_id)
        saved_org = await self.org_repo.save(org)

        user = User(
            email=email, full_name=full_name, role=UserRole.admin,
            organization_id=saved_org.id,
        )
        user.set_password(raw_password)
        saved_user = await self.user_repo.save(user)

        logger.info(
            "Signup completado: user_id=%s email=%s org_id=%s org_type=%s",
            saved_user.id, saved_user.email, saved_org.id, organization_type,
        )
        await self.audit.record(
            action="organization.created", resource_type="Organization", resource_id=saved_org.id,
            actor_user_id=saved_user.id, actor_organization_id=saved_org.id,
        )
        saved_user.organization = saved_org
        return saved_user