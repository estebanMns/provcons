import hashlib
from datetime import datetime, timedelta, timezone
import jwt

from app.core.config import settings
from app.core.exceptions import UnauthorizedError, ValidationError

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
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("El token ha expirado")
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Token inválido")
    # Un enlace de recuperación no sirve como sesión
    if payload.get("purpose"):
        raise UnauthorizedError("Token inválido")
    return payload


# --- Recuperación de contraseña ----------------------------------------------
# El token no se guarda en la base: lleva una huella del hash de la contraseña
# actual. Cuando la contraseña cambia, la huella deja de coincidir y el enlace
# queda inválido, así que sirve una sola vez.

RESET_PURPOSE = "password_reset"


def password_fingerprint(password_hash: str) -> str:
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def create_reset_token(user_id: int, password_hash: str, minutes: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes or settings.password_reset_minutes)
    payload = {
        "sub": str(user_id), "exp": expire,
        "purpose": RESET_PURPOSE, "pwh": password_fingerprint(password_hash),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_reset_token(token: str) -> dict:
    """Devuelve el contenido del enlace de recuperación. Un token de sesión
    no sirve aquí, y uno vencido o adulterado tampoco."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise ValidationError("El enlace venció. Pide uno nuevo.")
    except jwt.InvalidTokenError:
        raise ValidationError("El enlace no es válido. Pide uno nuevo.")
    if payload.get("purpose") != RESET_PURPOSE or "pwh" not in payload:
        raise ValidationError("El enlace no es válido. Pide uno nuevo.")
    return payload