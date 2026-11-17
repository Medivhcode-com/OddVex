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

    #: ``synthetic`` generates everything. ``replay`` serves a real past season shifted in
    #: time (real team and player names, internal previews only) and needs ``replay_data_path``.
    data_provider: Literal["synthetic", "replay"] = "synthetic"
    #: Dataset written by ``scripts/build_replay_data.py``. Never committed.
    replay_data_path: str = ""
    #: Days every replayed game is moved forward. Must be a multiple of 7.
    replay_shift_days: int = Field(default=728, ge=0)

    synthetic_seed: int = 20260101
    stale_live_seconds: int = 120
    stale_pregame_seconds: int = 900

    #: Trust ``X-Forwarded-For`` for the rate-limit client IP (only behind a trusted proxy).
    trust_proxy: bool = False
    #: Comma-separated emails that receive the admin role at registration / login.
    admin_emails: str = ""

    rate_limit_enabled: bool = True
    rate_limit_auth_per_minute: int = 10
    rate_limit_assistant_per_minute: int = 20
    rate_limit_window_seconds: int = 60

    #: Per-account limits. They are keyed on the email address (or user id), not the IP,
    #: and share one window. Disabled together with ``rate_limit_enabled``.
    account_limit_window_seconds: int = Field(default=900, ge=1)
    #: Failed logins for one email inside the window before further attempts get 429.
    login_max_failures: int = Field(default=8, ge=1)
    #: Verification or password-reset emails one address can request inside the window.
    email_requests_per_window: int = Field(default=3, ge=1)

    #: ``outbox`` writes emails to the ``email_outbox`` table and sends nothing.
    #: ``resend`` is a stub that refuses to start: real email needs Founder approval.
    email_provider: Literal["outbox", "resend"] = "outbox"
    #: Base URL of the web app, used for the links in emails.
    web_base_url: str = "http://localhost:3000"
    email_verification_ttl_hours: int = Field(default=24, ge=1)
    password_reset_ttl_minutes: int = Field(default=60, ge=1)

    auto_seed_demo: bool = False
    demo_password: str = DEV_DEMO_PASSWORD

    sync_max_attempts: int = 3

    #: Minimum seconds between two lazy alert evaluations for one user (triggered by the
    #: notification read routes). 0 evaluates on every request.
    alert_eval_min_seconds: int = Field(default=30, ge=0)

    #: Community limits per user (in process memory, off with ``rate_limit_enabled``).
    community_picks_per_day: int = Field(default=20, ge=1)
    community_comments_per_hour: int = Field(default=30, ge=1)
    community_reports_per_hour: int = Field(default=10, ge=1)
    community_follows_per_hour: int = Field(default=60, ge=1)
    #: Minimum seconds between two lazy grading passes over pending community picks
    #: (triggered by the community read routes). 0 grades on every read.
    community_grade_min_seconds: int = Field(default=15, ge=0)

    #: Largest request body accepted, in bytes. Larger requests get 413.
    max_body_bytes: int = Field(default=64 * 1024, ge=1024)

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    @property
    def should_auto_create_tables(self) -> bool:
        """Create tables on startup outside production unless explicitly disabled."""
        if self.db_auto_create is not None:
            return self.db_auto_create and not self.is_production
        return not self.is_production

    def validate_for_startup(self) -> None:
        """Refuse insecure configuration in production."""
        if self.data_provider == "replay" and not self.replay_data_path:
            raise RuntimeError(
                "ODDVEX_REPLAY_DATA_PATH must point to a replay dataset when "
                "ODDVEX_DATA_PROVIDER=replay"
            )
        if not self.is_production:
            return
        if self.data_provider == "replay":
            raise RuntimeError(
                "ODDVEX_DATA_PROVIDER=replay is for internal previews only and is refused when "
                "ODDVEX_ENV=production: it shows real team and player names with simulated prices"
            )
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
