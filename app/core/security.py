from datetime import datetime, timedelta, timezone
import jwt

from app.core.config import settings
from app.core.exceptions import UnauthorizedError

ALGORITHM = "HS256"


def create_access_token(subject: int, extra_claims: dict | None = None) -> str:
    """Crea un JWT firmado. `subject` es el id del usuario (se guarda en 'sub')."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(subject), "exp": expire}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Valida el token y devuelve su contenido. Lanza UnauthorizedError si es
    inválido, está mal firmado, o expiró."""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("El token ha expirado")
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Token inválido")