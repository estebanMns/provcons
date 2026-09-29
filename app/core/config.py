from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuración de la aplicación, cargada desde variables de entorno o .env"""

    app_name: str = "ProvCons - Backend"
    environment: str = "development"

    # Base de datos
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/provcons"

    # JWT / Auth
    secret_key: str = "cambia-esta-clave-en-produccion"
    access_token_expire_minutes: int = 60

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()