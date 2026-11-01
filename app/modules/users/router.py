from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.modules.users.repository import UserRepository, OrganizationRepository
from app.modules.users.service import UserService
from app.modules.users.schemas import (
    SignupRequest, UserOut, LoginRequest, TokenResponse, MeOut,
    ForgotPasswordRequest, ResetPasswordRequest, MessageOut,
)
from app.modules.users.password_reset import PasswordResetService, RateLimiter
from app.infrastructure.email import get_email_sender
from app.dependencies.auth import get_current_user
from app.modules.users.models import User
from app.core.audit import AuditService, AuditRepository


router = APIRouter(prefix="/users", tags=["Usuarios y auth"])


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    audit = AuditService(AuditRepository(db))
    return UserService(UserRepository(db), OrganizationRepository(db), audit)


# Uno por proceso, para que el límite de solicitudes valga entre peticiones
_reset_limiter = RateLimiter(max_requests=3, window_seconds=900)


def get_password_reset_service(db: AsyncSession = Depends(get_db)) -> PasswordResetService:
    return PasswordResetService(
        UserRepository(db), AuditService(AuditRepository(db)), get_email_sender(), _reset_limiter,
    )


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


@router.post("/password/forgot", response_model=MessageOut)
async def forgot_password(payload: ForgotPasswordRequest, service: PasswordResetService = Depends(get_password_reset_service)):
    """Envía un enlace para crear una nueva contraseña. Responde lo mismo
    exista o no el correo, para no revelar quién tiene cuenta."""
    return MessageOut(message=await service.request_reset(payload.email))


@router.post("/password/reset", response_model=MessageOut)
async def reset_password(payload: ResetPasswordRequest, service: PasswordResetService = Depends(get_password_reset_service)):
    await service.reset(payload.token, payload.new_password)
    return MessageOut(message="Tu contraseña se actualizó. Ya puedes ingresar con la nueva.")


@router.get("/me", response_model=MeOut)
async def me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(current_user.id, load_organization=True)
    return user or current_user