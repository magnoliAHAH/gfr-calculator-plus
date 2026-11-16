"""Настройки приложения из переменных окружения (ТЗ 9.3). Секреты — только из env."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Владелец схемы / роль с обходом RLS: миграции, логин, super_admin, онбординг.
    database_url: str = "postgresql+psycopg://cdss:cdss@localhost:5432/cdss"
    # Роль без BYPASSRLS: все обычные запросы. Если не задана — используется database_url
    # (тогда RLS НЕ действует, если роль суперпользователь; допустимо только для локальной отладки).
    app_database_url: str | None = None
    app_db_password: str = "cdss_app"

    jwt_secret: str = ""
    jwt_ttl_hours: int = 24
    hmac_key: str = ""

    app_version: str = "1.0.0"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173"

    super_admin_email: str | None = None
    super_admin_password: str | None = None
    super_admin_name: str = "Super Admin"

    public_base_url: str = "http://localhost"

    @property
    def effective_app_database_url(self) -> str:
        return self.app_database_url or self.database_url

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


def normalize_url(url: str) -> str:
    """postgresql:// из ТЗ -> драйвер psycopg3 для SQLAlchemy."""
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
