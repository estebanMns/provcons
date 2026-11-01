"""Recuperación de contraseña: "olvidé mi contraseña" → correo con enlace →
nueva contraseña.

Reglas:
- la respuesta es la misma exista o no el correo, para no revelar quién
  tiene cuenta
- el enlace vence (30 minutos) y sirve una sola vez (ver security.py)
- máximo 3 solicitudes por correo cada 15 minutos, para que nadie agote la
  cuota gratuita de Resend ni llene el buzón de otra persona
"""

import time
from collections import defaultdict, deque
from html import escape

from app.core.audit import AuditService
from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError, ValidationError
from app.core.logging import get_logger
from app.core.security import create_reset_token, decode_reset_token, password_fingerprint
from app.infrastructure.email import EmailSender
from app.modules.users.repository import UserRepository

logger = get_logger(__name__)

FORGOT_MESSAGE = "Si el correo está registrado, te enviamos un enlace para crear una nueva contraseña. Revisa tu bandeja de entrada y el spam."


class RateLimiter:
    """Ventana deslizante en memoria. Una por proceso: Render free corre una
    sola instancia (igual que la caché de predicciones)."""

    def __init__(self, max_requests: int = 3, window_seconds: float = 900):
        self.max_requests, self.window = max_requests, window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.max_requests:
            return False
        hits.append(now)
        return True


def _email_content(full_name: str, link: str, minutes: int) -> tuple[str, str, str]:
    subject = "Restablece tu contraseña de ProvCons"
    text = (
        f"Hola {full_name},\n\n"
        f"Recibimos una solicitud para cambiar la contraseña de tu cuenta en ProvCons.\n"
        f"Abre este enlace para crear una nueva (vence en {minutes} minutos y sirve una sola vez):\n\n"
        f"{link}\n\n"
        "Si no fuiste tú, ignora este correo: tu contraseña no cambiará."
    )
    safe_link, safe_name = escape(link, quote=True), escape(full_name)
    html = f"""\
<div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;color:#182523">
  <h2 style="color:#154f46">ProvCons</h2>
  <p>Hola {safe_name},</p>
  <p>Recibimos una solicitud para cambiar la contraseña de tu cuenta.</p>
  <p style="margin:28px 0">
    <a href="{safe_link}" style="background:#154f46;color:#fff;padding:12px 20px;border-radius:8px;text-decoration:none">
      Crear nueva contraseña
    </a>
  </p>
  <p style="font-size:13px;color:#52615e">El enlace vence en {minutes} minutos y sirve una sola vez.
  Si no fuiste tú, ignora este correo: tu contraseña no cambiará.</p>
</div>"""
    return subject, html, text


class PasswordResetService:
    def __init__(
        self, user_repo: UserRepository, audit: AuditService,
        email_sender: EmailSender | None, rate_limiter: RateLimiter,
    ):
        self.user_repo = user_repo
        self.audit = audit
        self.email_sender = email_sender
        self.rate_limiter = rate_limiter

    async def request_reset(self, email: str) -> str:
        if self.email_sender is None:
            raise ServiceUnavailableError(
                "La recuperación por correo no está configurada. Pide ayuda al administrador."
            )
        email = email.strip()
        if not self.rate_limiter.allow(email.lower()):
            logger.warning("Demasiadas solicitudes de recuperación para %s", email)
            return FORGOT_MESSAGE  # misma respuesta: no se revela nada

        user = await self.user_repo.get_by_email_insensitive(email)
        if user is None:
            logger.info("Recuperación pedida para un correo no registrado")
            return FORGOT_MESSAGE

        token = create_reset_token(user.id, user.password_hash)
        link = f"{settings.frontend_url.rstrip('/')}/restablecer?token={token}"
        subject, html, text = _email_content(user.full_name, link, settings.password_reset_minutes)
        try:
            await self.email_sender.send(user.email, subject, html, text)
        except Exception as e:  # el usuario recibe la misma respuesta; el motivo queda en el log
            logger.error("No se pudo enviar el correo de recuperación a user_id=%s: %s", user.id, e)
            return FORGOT_MESSAGE

        await self.audit.record(
            action="user.password_reset_requested", resource_type="User", resource_id=user.id,
            actor_user_id=user.id, actor_organization_id=user.organization_id,
        )
        return FORGOT_MESSAGE

    async def reset(self, token: str, new_password: str) -> None:
        payload = decode_reset_token(token)
        user = await self.user_repo.get_by_id(int(payload["sub"]))
        # Si la contraseña ya cambió (el enlace se usó), la huella no coincide
        if user is None or password_fingerprint(user.password_hash) != payload["pwh"]:
            raise ValidationError("Este enlace ya se usó o no es válido. Pide uno nuevo.")

        user.set_password(new_password)
        await self.user_repo.save(user)
        logger.info("Contraseña restablecida: user_id=%s", user.id)
        await self.audit.record(
            action="user.password_reset", resource_type="User", resource_id=user.id,
            actor_user_id=user.id, actor_organization_id=user.organization_id,
        )
