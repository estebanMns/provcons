from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuración de la aplicación, cargada desde variables de entorno o .env"""

    app_name: str = "ProvCons - Backend"
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:3000"]

    # IA
    gemini_api_key: str = ""
    gemini_default_model: str = "gemini-3.5-flash-lite"

    # Base de datos - Se carga del .env
    database_url: str

    # JWT / Auth - Se carga del .env
    secret_key: str
    access_token_expire_minutes: int = 60

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()