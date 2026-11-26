"""Runtime configuration, read from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-insecure-secret-change-me-0123456789"
DEV_DEMO_PASSWORD = "oddvex-demo-2026"

#: Snapshot archive (P0.1): fixed figures the archive settings below are checked against.
#: Hours a game lasts at most, for the props look-back.
SNAPSHOT_PROP_GAME_HOURS = 12
#: An unchanged prop offer is stored again once its latest row is this many hours old.
SNAPSHOT_PROP_REFRESH_HOURS = 24
#: The worker loop's period, in seconds.
SNAPSHOT_WORKER_TURN_SECONDS = 120


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

    #: Trust ``X-Forwarded-For`` for the client IP used by the rate limits, the login
    #: lockout and audit rows (only behind a trusted proxy).
    trust_proxy: bool = False
    #: Comma-separated emails that may hold the admin role. An account gets it only when
    #: its address is listed here and verified (``deps.sync_admin_role``).
    admin_emails: str = ""

    rate_limit_enabled: bool = True
    rate_limit_auth_per_minute: int = 10
    rate_limit_assistant_per_minute: int = 20
    rate_limit_window_seconds: int = 60

    #: Per-account limits. They are keyed on the email address (or user id) and share one
    #: window. Disabled together with ``rate_limit_enabled``.
    account_limit_window_seconds: int = Field(default=900, ge=1)
    #: Failed logins for one email from one client network (an IPv4 address, or the /64
    #: prefix of an IPv6 address) inside the window before further attempts for that
    #: email from that network get 429. Other networks are not affected.
    login_max_failures: int = Field(default=8, ge=1)
    #: Failed logins for one email from all networks together inside the window before
    #: every attempt for that email gets 429. Much higher than ``login_max_failures``:
    #: it is there for guessing spread over many addresses.
    login_max_failures_per_email: int = Field(default=50, ge=1)
    #: Verification or password-reset emails one address can request inside the window.
    email_requests_per_window: int = Field(default=3, ge=1)

    #: argon2 operations (login, sign-up, password change and reset) that may run at once
    #: in this process. Each one holds about 64 MiB while it runs, on top of about 85 MiB
    #: idle: the default of 2 peaks near 235 MiB under load. Size it to the container's
    #: memory limit: about ten slots reach 768 MB.
    password_hash_concurrency: int = Field(default=2, ge=1, le=32)
    #: Seconds a request waits for one of those slots before it gets 429 with
    #: ``Retry-After``. 0 never waits. A shed request is not counted as a failed login.
    password_hash_wait_seconds: float = Field(default=1.0, ge=0, le=30)

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

    #: Most bets one account can hold, manual and imported together. ``POST /v1/bets``
    #: answers 409 ``bet_limit_reached`` at the cap and an import stops there. It bounds
    #: the disk one account can use (a bet with 20 legs and 2,000 characters of notes is
    #: about 22 KiB of database) and what the summary, analytics and export read.
    max_bets_per_user: int = Field(default=5000, ge=1)
    #: Per-user ceilings on bet writes (create, update, delete, settle, auto-settle) and
    #: sync writes, keyed on the user id whatever the address. In process memory, off
    #: with ``rate_limit_enabled``.
    rate_limit_user_writes_per_minute: int = Field(default=120, ge=1)
    rate_limit_user_writes_per_day: int = Field(default=2000, ge=1)
    #: ``GET /v1/me/export`` requests one user can make in an hour.
    rate_limit_export_per_hour: int = Field(default=10, ge=1)
    #: Streamed responses (the bet list and the export) one user can have in progress at
    #: the same moment. Each holds one batch of bets while the client reads.
    rate_limit_user_streams_at_once: int = Field(default=8, ge=1)

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

    #: Snapshot archive (P0.1, flag ``snapshot_archive``, off by default). The capture
    #: script (``scripts/capture_snapshots.py``) runs in the worker loop every 120 s and
    #: captures odds when the last odds capture is at least this old (less 15 s of slack):
    #: 360 s is every third turn of the loop.
    snapshot_odds_interval_seconds: int = Field(default=360, ge=60)
    #: The same for player-prop offers.
    snapshot_props_interval_seconds: int = Field(default=3600, ge=60)
    #: Events captured: every live event and every upcoming one starting within this many hours.
    snapshot_horizon_hours: int = Field(default=36, ge=1, le=168)
    #: Days every captured row is kept at full resolution.
    snapshot_retention_days: int = Field(default=7, ge=1)
    #: Days a game's kept captures (first, closing, last and the rows a stored bet's
    #: placement time points at), status rows and capture runs are kept. A game's rows
    #: leave together, when its last capture is this old. Never shorter than
    #: ``snapshot_retention_days``.
    snapshot_keep_days: int = Field(default=400, ge=1)
    #: Counted size (rows times measured bytes per row) at which capture stops
    #: (``skipped_full`` runs) while the prune keeps running. 1.5 GiB; measured use is
    #: about 0.55 GB after a week and 0.95 GB by day 400 (1.3 GB with every game at the
    #: bet-anchor bound) on the synthetic schedule.
    snapshot_max_bytes: int = Field(default=1_610_612_736, ge=1)
    #: PostgreSQL only: size of the archive's files (tables and indexes) at which capture
    #: also stops, whatever the counted size. A hard ceiling, 2 GiB: with bloated indexes
    #: rebuilt (``archive/reclaim.py``) the files stay within 1.25 times the largest
    #: counted size, 1.9 GiB at the cap. Keep it above ``snapshot_max_bytes``: the table
    #: files never shrink, so a ceiling below them would not release.
    snapshot_max_disk_bytes: int = Field(default=2_147_483_648, ge=1)
    #: A time more than this many seconds after the last capture is an archive gap: two
    #: odds intervals plus one worker turn, so one missed pass is tolerated and two are not.
    snapshot_max_gap_seconds: int = Field(default=840, ge=60)
    #: Minimum seconds between two prune passes.
    snapshot_prune_interval_seconds: int = Field(default=3600, ge=60)
    #: PostgreSQL only: seconds one index rebuild of the archive may take
    #: (``statement_timeout`` of ``archive/reclaim.py``). 120 s is about eight times what
    #: the largest index took at the size of the cap on the development machine; raise it
    #: if rebuilds on a slower server are recorded as failed with ``QueryCanceled``.
    snapshot_reclaim_timeout_seconds: int = Field(default=120, ge=1, le=3600)

    @property
    def snapshot_props_max_gap_seconds(self) -> int:
        """A time more than this after the last props capture is a gap for the props
        read: two props intervals plus one worker turn (7,320 s with hourly props)."""
        return 2 * self.snapshot_props_interval_seconds + SNAPSHOT_WORKER_TURN_SECONDS

    @property
    def snapshot_prop_lookback_seconds(self) -> int:
        """How far back from T the props read looks for an offer's latest row.

        Two rules, and the look-back is the longer. An offer is stored when its game
        enters scope, ``snapshot_horizon_hours`` before the start, and can stay valid
        until the game ends (``SNAPSHOT_PROP_GAME_HOURS``). And an unchanged offer is
        stored again at the first props capture after its row is
        ``SNAPSHOT_PROP_REFRESH_HOURS`` old, while a read is answered from a props capture
        up to ``snapshot_props_max_gap_seconds`` before T: so an open offer's latest row
        is less than the refresh age plus that gap before T. The second rule holds at
        every setting; with the first alone, a horizon of 14 hours or less left an offer
        unchanged for a day out of the read (review round 4)."""
        return max(
            (self.snapshot_horizon_hours + SNAPSHOT_PROP_GAME_HOURS) * 3600,
            SNAPSHOT_PROP_REFRESH_HOURS * 3600 + self.snapshot_props_max_gap_seconds,
        )

    def snapshot_settings_problem(self) -> str | None:
        """Why the archive settings cannot work together, or ``None``. The props read
        answers ``archive_pruned`` whenever its look-back reaches past the keep horizon;
        with a keep period no longer than the look-back that is every time."""
        keep_seconds = max(self.snapshot_keep_days, self.snapshot_retention_days) * 86_400
        lookback = self.snapshot_prop_lookback_seconds
        if keep_seconds <= lookback:
            return (
                "ODDVEX_SNAPSHOT_KEEP_DAYS (or ODDVEX_SNAPSHOT_RETENTION_DAYS, when larger) "
                f"must be longer than the props look-back of {lookback} seconds "
                "(ODDVEX_SNAPSHOT_HORIZON_HOURS plus 12 hours, or 24 hours plus two props "
                "intervals and 120 seconds): otherwise no archived props read ever answers"
            )
        return None

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
        """Refuse configuration that cannot work, and insecure configuration in
        production."""
        problem = self.snapshot_settings_problem()
        if problem is not None:
            raise RuntimeError(problem)
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
