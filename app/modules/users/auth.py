from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.security import decode_access_token
from app.core.exceptions import UnauthorizedError, ForbiddenError
from app.modules.users.repository import UserRepository
from app.modules.users.models import User

_bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extrae y valida el JWT del header Authorization, devuelve el usuario real."""
    payload = decode_access_token(credentials.credentials)
    user_id = int(payload["sub"])

    user = await UserRepository(db).get_by_id(user_id)
    if user is None:
        raise UnauthorizedError("El usuario del token ya no existe")
    return user


def require_same_organization(resource_org_id: int, current_user: User) -> None:
    """Regla central de multi-tenancy: un usuario solo puede operar sobre
    recursos de su propia organización."""
    if current_user.organization_id != resource_org_id:
        raise ForbiddenError("No tienes acceso a recursos de otra organización")