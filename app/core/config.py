from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la aplicación, cargada desde variables de entorno o .env"""

    app_name: str = "ProvCons - Backend"
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # IA
    gemini_api_key: str = ""
    gemini_default_model: str = "gemini-3.5-flash-lite"
    ai_timeout_seconds: float = 90.0  # por intento; una llamada colgada no bloquea la petición
    # Revisión con IA del inventario en el matching (si es False, o no hay
    # GEMINI_API_KEY, se usa solo la comparación por texto)
    matching_ai_review: bool = True

    # Motor de comparación: "grpc" = microservicio (app/grpc_engine, con
    # respaldo local si no responde); "local" = en el mismo proceso
    matching_engine_mode: str = "grpc"
    matching_engine_addr: str = "127.0.0.1:50051"
    matching_engine_timeout: float = 10.0

    # Base de datos - Se carga del .env
    database_url: str

    # JWT / Auth - Se carga del .env
    secret_key: str
    access_token_expire_minutes: int = 60

    # Recuperación de contraseña por correo (Resend, por API HTTPS: Render
    # gratis bloquea SMTP). Sin dominio verificado, Resend solo entrega
    # correos desde onboarding@resend.dev al dueño de la cuenta.
    resend_emails: bool = True
    resend_api_key: str = ""
    email_from: str = "ProvCons <onboarding@resend.dev>"
    frontend_url: str = "http://localhost:3000"  # para armar el enlace del correo
    password_reset_minutes: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()