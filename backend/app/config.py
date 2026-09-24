from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    storage: Literal["postgres", "memory"] = "postgres"
    database_url: str = "postgresql+psycopg://muevete:muevete@localhost:5432/muevete"
    id_salt: str = "cambia-este-salt"
    admin_api_key: str = ""

    llm_provider: Literal["gemini", "none"] = "none"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"
    llm_timeout_s: float = 4.0

    conversation_ttl_min: int = 30
    cors_origins: str = "*"

    telegram_token: str = ""
    telegram_webhook_secret: str = ""
    whatsapp_token: str = ""
    whatsapp_phone_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_api_version: str = "v21.0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
