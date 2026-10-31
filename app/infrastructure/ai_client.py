import json
import asyncio
import time

from google import genai

from app.core.config import settings
from app.core.exceptions import DomainError
from app.core.logging import get_logger
from app.core.metrics import metrics
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

    async def generate_json(
        self, prompt: str, system_instruction: str,
        model: str | None = None, max_retries: int = 3,
    ) -> dict | None:
        """Genera JSON a partir de un prompt de texto."""
        return await self._generate(
            "texto", prompt, system_instruction, model, max_retries,
            "El servicio de IA no pudo procesar la solicitud",
        )

    async def generate_json_from_file(
        self, file_bytes: bytes, mime_type: str, system_instruction: str,
        model: str | None = None, max_retries: int = 3,
    ) -> dict | None:
        """Genera JSON a partir de un archivo (PDF o imagen). Gemini lo lee
        directamente — no necesitamos un OCR tradicional por separado."""
        return await self._generate(
            "archivo", [types.Part.from_bytes(data=file_bytes, mime_type=mime_type)],
            system_instruction, model, max_retries,
            "El servicio de IA no pudo procesar el documento",
        )

    async def _generate(
        self, kind: str, contents, system_instruction: str,
        model: str | None, max_retries: int, error_message: str,
    ) -> dict | None:
        """Llamada con reintentos, tiempo límite y medición de rendimiento.
        Las esperas entre intentos son asyncio.sleep: no bloquean el event
        loop, que sigue atendiendo otras peticiones mientras tanto."""
        model_name = model or self.default_model

        for attempt in range(1, max_retries + 1):
            started = time.perf_counter()
            try:
                response = await asyncio.wait_for(
                    self._client.aio.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config={
                            "system_instruction": system_instruction,
                            "response_mime_type": "application/json",
                        },
                    ),
                    timeout=settings.ai_timeout_seconds,
                )
                result = self._parse_json(response.text)
                metrics.observe_ai(kind, time.perf_counter() - started, ok=True)
                return result

            except Exception as e:
                metrics.observe_ai(kind, time.perf_counter() - started, ok=False)
                wait = 2 ** attempt
                logger.warning(
                    "Fallo en llamada a IA con %s (intento %s/%s): %s. Reintentando en %ss...",
                    kind, attempt, max_retries, str(e) or type(e).__name__, wait,
                )
                if attempt == max_retries:
                    logger.error("IA agotó reintentos procesando %s: %s", kind, str(e) or type(e).__name__)
                    raise AIServiceError(error_message)
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