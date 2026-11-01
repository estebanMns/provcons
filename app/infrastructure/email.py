"""Envío de correos. Igual que AIClient, ningún módulo habla con el proveedor
de correo directamente: todos usan un EmailSender.

Se usa Resend por API HTTPS porque Render gratis bloquea los puertos SMTP.
En desarrollo, sin API key, el correo se escribe en el log para poder probar
el flujo sin configurar nada.
"""

from typing import Protocol

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

RESEND_URL = "https://api.resend.com/emails"


class EmailError(Exception):
    pass


class EmailSender(Protocol):
    async def send(self, to: str, subject: str, html: str, text: str) -> None: ...


class ResendEmailSender:
    def __init__(self, api_key: str, sender: str, transport: httpx.AsyncBaseTransport | None = None):
        self.api_key, self.sender, self.transport = api_key, sender, transport

    async def send(self, to: str, subject: str, html: str, text: str) -> None:
        async with httpx.AsyncClient(timeout=10, transport=self.transport) as client:
            response = await client.post(
                RESEND_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"from": self.sender, "to": [to], "subject": subject, "html": html, "text": text},
            )
        if response.status_code >= 300:
            # Resend explica el motivo en el cuerpo (ej. "solo puedes enviar a tu propio correo")
            raise EmailError(f"Resend respondió {response.status_code}: {response.text[:300]}")
        logger.info("Correo enviado con Resend: id=%s", response.json().get("id"))


class ConsoleEmailSender:
    """Solo para desarrollo: el correo, con su enlace, queda en el log."""

    async def send(self, to: str, subject: str, html: str, text: str) -> None:
        logger.warning("Correo NO enviado (desarrollo sin Resend). Para: %s | %s\n%s", to, subject, text)


def get_email_sender() -> EmailSender | None:
    """None si no hay forma de enviar correos (producción sin Resend)."""
    if settings.resend_emails and settings.resend_api_key:
        return ResendEmailSender(settings.resend_api_key, settings.email_from)
    if settings.environment == "development":
        return ConsoleEmailSender()
    return None
