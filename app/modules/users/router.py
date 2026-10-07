from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.users.repository import UserRepository, OrganizationRepository
from app.modules.users.service import UserService
from app.modules.users.schemas import (
    SignupRequest, UserOut, LoginRequest, TokenResponse,
    MeOut, OrganizationCreate, OrganizationOut,
)
from app.dependencies.auth import get_current_user
from app.modules.users.models import User
from app.core.audit import AuditService, AuditRepository


router = APIRouter(prefix="/users", tags=["Usuarios y auth"])


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    audit = AuditService(AuditRepository(db))
    return UserService(UserRepository(db), OrganizationRepository(db), audit)


@router.post("/signup", response_model=MeOut)
async def signup(payload: SignupRequest, service: UserService = Depends(get_user_service)):
    """Onboarding público: crea organización + primer usuario (admin) en una operación."""
    user = await service.signup_with_organization(
        payload.organization_name, payload.organization_type, payload.tax_id,
        payload.email, payload.password, payload.full_name,
    )
    return user


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, service: UserService = Depends(get_user_service)):
    token = await service.login(payload.email, payload.password)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeOut)
async def me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(current_user.id, load_organization=True)
    return user or current_user