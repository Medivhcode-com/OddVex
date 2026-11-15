"""Runtime configuration, read from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-insecure-secret-change-me-0123456789"
DEV_DEMO_PASSWORD = "oddvex-demo-2026"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ODDVEX_", env_file=".env", extra="ignore", populate_by_name=True
    )

    env: Literal["development", "test", "production"] = "development"
    database_url: str = Field(default="sqlite:///./oddvex_dev.db", validation_alias="DATABASE_URL")
    db_auto_create: bool | None = None
    jwt_secret: str = DEV_JWT_SECRET
    jwt_ttl_minutes: int = 60
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"

    synthetic_seed: int = 20260101
    stale_live_seconds: int = 120
    stale_pregame_seconds: int = 900

    rate_limit_auth_per_minute: int = 10
    rate_limit_assistant_per_minute: int = 20
    rate_limit_window_seconds: int = 60

    auto_seed_demo: bool = False
    demo_password: str = DEV_DEMO_PASSWORD

    sync_max_attempts: int = 3

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]

    @property
    def should_auto_create_tables(self) -> bool:
        """Create tables on startup outside production unless explicitly disabled."""
        if self.db_auto_create is not None:
            return self.db_auto_create and not self.is_production
        return not self.is_production

    def validate_for_startup(self) -> None:
        """Refuse insecure configuration in production."""
        if not self.is_production:
            return
        if self.jwt_secret == DEV_JWT_SECRET:
            raise RuntimeError(
                "ODDVEX_JWT_SECRET must be set to a strong secret when ODDVEX_ENV=production"
            )
        if len(self.jwt_secret) < 32:
            raise RuntimeError("ODDVEX_JWT_SECRET must be at least 32 characters in production")
        if "*" in self.cors_origin_list:
            raise RuntimeError("ODDVEX_CORS_ORIGINS must be an explicit allowlist in production")


@lru_cache
def get_settings() -> Settings:
    return Settings()
