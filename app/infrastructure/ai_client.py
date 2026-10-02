import json
import asyncio

from google import genai

from app.core.config import settings
from app.core.exceptions import DomainError
from app.core.logging import get_logger
from google.genai import types

logger = get_logger(__name__)


class AIServiceError(DomainError):
    """La IA no pudo responder tras varios intentos. 502 porque el problema
    está en un servicio externo, no en nuestra propia API."""
    status_code = 502


class AIClient:
    """Punto único de acceso al LLM. Ningún otro módulo llama a la API de
    Gemini directamente — todos pasan por aquí. Esto es lo que permite:
    - centralizar reintentos y manejo de errores
    - cambiar de modelo o de proveedor sin tocar la lógica de negocio
    - loguear cada llamada en un solo lugar
    """

    def __init__(self, api_key: str | None = None, default_model: str | None = None):
        self._client = genai.Client(api_key=api_key or settings.gemini_api_key)
        self.default_model = default_model or settings.gemini_default_model

        async def generate_json_from_file(
            self, file_bytes: bytes, mime_type: str, system_instruction: str,
            model: str | None = None, max_retries: int = 3,
            ) -> dict | None:
            """Igual que generate_json, pero el 'prompt' es un archivo (PDF o
            imagen) en vez de texto. Gemini lo lee directamente — no necesitamos
            un OCR tradicional por separado."""
            model_name = model or self.default_model

            for attempt in range(1, max_retries + 1):
                try:
                    response = await self._client.aio.models.generate_content(
                        model=model_name,
                        contents=[types.Part.from_bytes(data=file_bytes, mime_type=mime_type)],
                        config={
                            "system_instruction": system_instruction,
                            "response_mime_type": "application/json",
                        },
                    )
                    return self._parse_json(response.text)

                except Exception as e:
                    wait = 2 ** attempt
                    logger.warning(
                        "Fallo en llamada a IA con archivo (intento %s/%s): %s. Reintentando en %ss...",
                        attempt, max_retries, str(e), wait,
                    )
                    if attempt == max_retries:
                        logger.error("IA agotó reintentos procesando archivo: %s", str(e))
                        raise AIServiceError("El servicio de IA no pudo procesar el documento")
                    await asyncio.sleep(wait)

    @staticmethod
    def _parse_json(raw_text: str) -> dict:
        """El modelo a veces envuelve el JSON en ```json ... ``` aunque se
        le pida texto plano — lo limpiamos antes de parsear."""
        cleaned = raw_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("Respuesta de IA no es JSON válido: %s", raw_text[:200])
            raise AIServiceError(f"La IA devolvió un formato inválido: {e}")