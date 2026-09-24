from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    storage: Literal["postgres", "memory"] = "postgres"
    database_url: str = "postgresql+psycopg://muevete:muevete@localhost:5432/muevete"
    id_salt: str = "cambia-este-salt"
    admin_api_key: str = ""

    llm_provider: Literal["gemini", "none"] = "none"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    # Si el principal no responde en gemini_primary_timeout_s (o falla), se usa el de respaldo
    gemini_fallback_model: str = "gemini-3.5-flash-lite"
    gemini_primary_timeout_s: float = 6.0
    gemini_thinking: str = "minimal"  # minimal | low | medium | high; vacío = el del modelo
    llm_timeout_s: float = 12.0

    conversation_ttl_min: int = 30
    # URL pública del backend (para que Telegram/WhatsApp descarguen el mapa). Vacía = la del request.
    public_base_url: str = ""
    # Teselas del mapa de rutas. Vacía = sin fondo (solo la ruta).
    map_tile_url: str = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    cors_origins: str = "*"

    telegram_token: str = ""
    telegram_webhook_secret: str = ""
    whatsapp_token: str = ""
    whatsapp_phone_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_api_version: str = "v21.0"

    # Carpeta de la web estática; si existe se sirve en "/" (en Docker: /web)
    web_dir: str = ""

    @field_validator("database_url")
    @classmethod
    def _driver_psycopg(cls, v: str) -> str:
        # Railway/Heroku entregan postgres:// o postgresql://; SQLAlchemy necesita el driver psycopg 3
        for prefijo in ("postgres://", "postgresql://"):
            if v.startswith(prefijo):
                return "postgresql+psycopg://" + v[len(prefijo):]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
