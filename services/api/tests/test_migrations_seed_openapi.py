"""Alembic migration, demo seed and the committed OpenAPI document."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import DateTime, bindparam, inspect, select, text

from oddvex_api.auth.security import hash_password
from oddvex_api.db import (
    AlertRule,
    Base,
    Bet,
    Notification,
    User,
    make_engine,
    make_session_factory,
)
from oddvex_api.providers import SyntheticProvider
from oddvex_api.seed import (
    DEMO_ADMIN_EMAIL,
    DEMO_BET_COUNT,
    DEMO_EMAIL,
    DEMO_GRADEABLE_COUNT,
    seed_demo,
)

from .conftest import EXTERNAL_DATABASE_URL, AppFactory, _reset_external_database
from .test_provider_synthetic import REAL_NAMES

API_ROOT = Path(__file__).resolve().parents[1]
TABLES = {
    "users",
    "bets",
    "bet_legs",
    "sync_connections",
    "sync_import_runs",
    "audit_log",
    "watchlist_items",
    "alert_rules",
    "notifications",
    "notification_preferences",
    "stake_reminders",
    "feature_flags",
    "email_tokens",
    "email_outbox",
    "community_profiles",
    "community_picks",
    "community_comments",
    "community_follows",
    "community_likes",
    "community_blocks",
    "community_reports",
}
NOW = datetime(2026, 3, 14, 19, 30, tzinfo=UTC)


def alembic_config(url: str) -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    return config


# ------------------------------------------------------------------ migration
def test_upgrade_head_on_a_fresh_database_matches_the_models(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    command.upgrade(alembic_config(url), "head")
    engine = make_engine(url)
    assert set(inspect(engine).get_table_names()) == TABLES | {"alembic_version"}
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == [], diff
    command.downgrade(alembic_config(url), "base")
    assert set(inspect(make_engine(url)).get_table_names()) == {"alembic_version"}


def _database_urls() -> list[str]:
    """SQLite always; the external (PostgreSQL) database too when one is configured."""
    return ["sqlite", *([EXTERNAL_DATABASE_URL] if EXTERNAL_DATABASE_URL else [])]


@pytest.mark.parametrize("backend", _database_urls())
def test_upgrade_from_0001_with_existing_data_then_downgrade(
    backend: str, tmp_path: Path, make_app: AppFactory
) -> None:
    if backend == "sqlite":
        url = f"sqlite:///{tmp_path / 'upgrade.db'}"
    else:
        url = backend
        _reset_external_database(url)
    config = alembic_config(url)
    command.upgrade(config, "0001")
    engine = make_engine(url)
    assert "watchlist_items" not in inspect(engine).get_table_names()

    # Rows written by the previous release.
    stamp = datetime(2026, 2, 1, 12, 0, tzinfo=UTC)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, email, password_hash, display_name, role, is_active, "
                "age_confirmed_at, created_at) VALUES (:id, :email, :hash, 'Old', 'user', "
                ":active, :at, :at)"
            ).bindparams(bindparam("at", type_=DateTime(timezone=True))),
            {
                "id": "u" * 32,
                "email": "old@example.test",
                "hash": hash_password("correct-horse-battery"),
                "active": True,
                "at": stamp,
            },
        )
        for bet_id, status, result, source in (
            ("b" * 32, "settled", "won", "manual"),
            ("c" * 32, "pending", None, "manual"),
            ("d" * 32, "settled", "lost", "sync"),
        ):
            connection.execute(
                text(
                    "INSERT INTO bets (id, user_id, bet_type, status, result, sport, sportsbook, "
                    "stake, odds_decimal, odds_source, payout, profit, placed_at, settled_at, "
                    "source, created_at, updated_at) VALUES (:id, :user, 'straight', :status, "
                    ":result, 'nba', 'Northline', 10, 2.0, 'legs', :payout, :profit, :at, "
                    ":settled, :source, :at, :at)"
                ).bindparams(
                    bindparam("at", type_=DateTime(timezone=True)),
                    bindparam("settled", type_=DateTime(timezone=True)),
                ),
                {
                    "id": bet_id,
                    "user": "u" * 32,
                    "status": status,
                    "result": result,
                    "payout": {"won": 20, "lost": 0}.get(result or ""),
                    "profit": {"won": 10, "lost": -10}.get(result or ""),
                    "settled": stamp if status == "settled" else None,
                    "source": source,
                    "at": stamp,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO bet_legs (id, bet_id, position, selection, market, event_id, "
                    "line, odds_decimal) VALUES (:id, :bet, 0, 'Tides -3.5', 'spread', "
                    "'evt_nba_20260201_0', -3.5, 2.0)"
                ),
                {"id": bet_id[:1].upper() * 32, "bet": bet_id},
            )

    command.upgrade(config, "head")
    engine = make_engine(url)
    assert "watchlist_items" in inspect(engine).get_table_names()
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == [], diff
    command.check(config)  # `alembic check`: models and migrations agree

    with make_session_factory(engine)() as db:
        user = db.scalar(select(User))
        assert user is not None and user.email == "old@example.test"
        assert user.token_version == 0 and user.password_changed_at is None
        bets = {b.id[0]: b for b in db.scalars(select(Bet))}
        assert len(bets) == 3
        # Backfill: bets settled by hand were settled by the user; imports and pending are null.
        assert bets["b"].settled_by == "user" and bets["b"].profit == 10
        assert bets["c"].settled_by is None and bets["d"].settled_by is None
        assert all(leg.outcome_key is None for b in bets.values() for leg in b.legs)
        assert all(float(leg.line or 0) == -3.5 for b in bets.values() for leg in b.legs)
    engine.dispose()

    # The current app runs on the upgraded data: old login, old bets, new features.
    app = make_app(database_url=url, env="production", jwt_secret="k" * 48)
    with TestClient(app) as client:
        login = client.post(
            "/v1/auth/login",
            json={"email": "old@example.test", "password": "correct-horse-battery"},
        )
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        listed = client.get("/v1/bets", headers=headers).json()
        assert len(listed) == 3
        assert all(b["legs"][0]["gradeable"] is False for b in listed)
        assert {b["settled_by"] for b in listed} == {"user", None}
        skipped = client.post("/v1/bets/auto-settle", headers=headers).json()
        assert skipped["settled"] == [] and skipped["skipped"][0]["reason"] == "not_gradeable"
        team_id = client.get("/v1/events").json()[0]["home_team"]["id"]
        added = client.post(
            "/v1/watchlist", json={"kind": "team", "ref_id": team_id}, headers=headers
        )
        assert added.status_code == 201
        assert len(client.get("/v1/me/export", headers=headers).json()["bets"]) == 3
    app.state.engine.dispose()

    # Downgrade removes only what 0002 added; the 0001 data is still there.
    command.downgrade(config, "0001")
    engine = make_engine(url)
    inspector = inspect(engine)
    assert "watchlist_items" not in inspector.get_table_names()
    assert "token_version" not in {c["name"] for c in inspector.get_columns("users")}
    assert "settled_by" not in {c["name"] for c in inspector.get_columns("bets")}
    assert "outcome_key" not in {c["name"] for c in inspector.get_columns("bet_legs")}
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM users")).scalar() == 1
        assert connection.execute(text("SELECT count(*) FROM bets")).scalar() == 3
        assert connection.execute(text("SELECT count(*) FROM bet_legs")).scalar() == 3
        assert connection.execute(text("SELECT email FROM users")).scalar() == "old@example.test"
    engine.dispose()

    # And back up again, then all the way down.
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    engine = make_engine(url)
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    engine.dispose()
    if backend != "sqlite":
        _reset_external_database(url)


NEW_TABLES = {"alert_rules", "notifications", "notification_preferences", "stake_reminders"}


@pytest.mark.parametrize("backend", _database_urls())
def test_upgrade_from_0002_with_existing_data_then_downgrade(
    backend: str, tmp_path: Path, make_app: AppFactory
) -> None:
    if backend == "sqlite":
        url = f"sqlite:///{tmp_path / 'upgrade_0003.db'}"
    else:
        url = backend
        _reset_external_database(url)
    config = alembic_config(url)
    command.upgrade(config, "0002")
    engine = make_engine(url)
    assert not NEW_TABLES & set(inspect(engine).get_table_names())

    # Rows written by the 0002 release: a user, a bet placed this week and a watched team.
    stamp = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, email, password_hash, display_name, role, is_active, "
                "age_confirmed_at, created_at, token_version) VALUES (:id, :email, :hash, "
                "'Old', 'user', :active, :at, :at, 0)"
            ).bindparams(bindparam("at", type_=DateTime(timezone=True))),
            {
                "id": "u" * 32,
                "email": "old@example.test",
                "hash": hash_password("correct-horse-battery"),
                "active": True,
                "at": stamp,
            },
        )
        connection.execute(
            text(
                "INSERT INTO bets (id, user_id, bet_type, status, sport, sportsbook, stake, "
                "odds_decimal, odds_source, placed_at, source, created_at, updated_at) VALUES "
                "(:id, :user, 'straight', 'pending', 'nba', 'Northline', 40, 2.0, 'legs', :at, "
                "'manual', :at, :at)"
            ).bindparams(bindparam("at", type_=DateTime(timezone=True))),
            {"id": "b" * 32, "user": "u" * 32, "at": stamp},
        )
        connection.execute(
            text(
                "INSERT INTO bet_legs (id, bet_id, position, selection, market, odds_decimal) "
                "VALUES (:id, :bet, 0, 'Tides ML', 'moneyline', 2.0)"
            ),
            {"id": "B" * 32, "bet": "b" * 32},
        )
        connection.execute(
            text(
                "INSERT INTO watchlist_items (id, user_id, kind, ref_id, label, league, "
                "created_at) VALUES (:id, :user, 'team', 'team_nba_cpr', 'Copper Ridge "
                "Kestrels', 'nba', :at)"
            ).bindparams(bindparam("at", type_=DateTime(timezone=True))),
            {"id": "w" * 32, "user": "u" * 32, "at": stamp},
        )

    command.upgrade(config, "head")
    engine = make_engine(url)
    assert set(inspect(engine).get_table_names()) >= NEW_TABLES
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
        assert diff == [], diff
        # Nothing was invented for existing users.
        for table in sorted(NEW_TABLES):
            assert connection.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0
    command.check(config)  # `alembic check`: models and migrations agree
    engine.dispose()

    # The current app on the upgraded data: old login and bet, defaults, then the new features.
    app = make_app(
        database_url=url, env="production", jwt_secret="k" * 48, alert_eval_min_seconds=0
    )
    with TestClient(app) as client:
        login = client.post(
            "/v1/auth/login",
            json={"email": "old@example.test", "password": "correct-horse-battery"},
        )
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert len(client.get("/v1/bets", headers=headers).json()) == 1
        assert len(client.get("/v1/watchlist", headers=headers).json()["items"]) == 1
        assert client.get("/v1/notifications", headers=headers).json() == {
            "items": [],
            "unread_count": 0,
            "next_before": None,
        }
        assert client.get("/v1/alerts", headers=headers).json() == {"items": []}
        preferences = client.get("/v1/me/notification-preferences", headers=headers).json()
        assert all(preferences["in_app"].values()) and len(preferences["in_app"]) == 10
        # The bet from before the migration counts towards this week's total.
        reminder = client.get("/v1/me/stake-reminder", headers=headers).json()
        assert reminder["weekly_stake_threshold"] is None and reminder["staked_this_week"] == 40.0

        event = client.get("/v1/events", params={"status": "upcoming"}).json()[0]
        alert = client.post(
            "/v1/alerts", json={"kind": "game_final", "event_id": event["id"]}, headers=headers
        )
        assert alert.status_code == 201, alert.text
        client.put("/v1/me/stake-reminder", json={"weekly_stake_threshold": 50}, headers=headers)
        client.put(
            "/v1/me/notification-preferences",
            json={"in_app": {"sync_finished": False}},
            headers=headers,
        )
        bet = {
            "bet_type": "straight",
            "stake": 10,
            "sportsbook": "Northline",
            "legs": [{"selection": "x", "market": "moneyline", "odds": -110}],
            "placed_at": "2026-03-14T12:00:00Z",
        }
        assert client.post("/v1/bets", json=bet, headers=headers).status_code == 201
        items = client.get("/v1/notifications", headers=headers).json()["items"]
        assert [n["kind"] for n in items] == ["stake_reminder"]  # 40 + 10 reached 50
        export = client.get("/v1/me/export", headers=headers).json()
        assert len(export["alerts"]) == 1 and len(export["notifications"]) == 1
    app.state.engine.dispose()

    # Downgrade removes only what 0003 added; the 0002 data is untouched.
    command.downgrade(config, "0002")
    engine = make_engine(url)
    tables = set(inspect(engine).get_table_names())
    assert not NEW_TABLES & tables and "watchlist_items" in tables
    with engine.connect() as connection:
        assert connection.execute(text("SELECT email FROM users")).scalar() == "old@example.test"
        assert connection.execute(text("SELECT count(*) FROM bets")).scalar() == 2
        assert connection.execute(text("SELECT count(*) FROM bet_legs")).scalar() == 2
        assert connection.execute(text("SELECT count(*) FROM watchlist_items")).scalar() == 1
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0002"
        )
    engine.dispose()

    # Up again (the new tables start empty), then all the way down.
    command.upgrade(config, "head")
    engine = make_engine(url)
    with engine.connect() as connection:
        for table in sorted(NEW_TABLES):
            assert connection.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0
    engine.dispose()
    command.downgrade(config, "base")
    engine = make_engine(url)
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    engine.dispose()
    if backend != "sqlite":
        _reset_external_database(url)


TABLES_0004 = {"feature_flags", "email_tokens", "email_outbox"}
COLUMNS_0004 = {"plan", "status", "last_login_at", "email_verified_at"}


@pytest.mark.parametrize("backend", _database_urls())
def test_upgrade_from_0003_with_existing_data_then_downgrade(
    backend: str, tmp_path: Path, make_app: AppFactory
) -> None:
    if backend == "sqlite":
        url = f"sqlite:///{tmp_path / 'upgrade_0004.db'}"
    else:
        url = backend
        _reset_external_database(url)
    config = alembic_config(url)
    command.upgrade(config, "0003")
    engine = make_engine(url)
    assert not TABLES_0004 & set(inspect(engine).get_table_names())
    assert not COLUMNS_0004 & {c["name"] for c in inspect(engine).get_columns("users")}

    # Rows written by the 0003 release: a user with a bet, an alert rule and a notification.
    stamp = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)
    at = bindparam("at", type_=DateTime(timezone=True))
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, email, password_hash, display_name, role, is_active, "
                "age_confirmed_at, created_at, token_version) VALUES (:id, :email, :hash, "
                "'Old', 'user', :active, :at, :at, 0)"
            ).bindparams(at),
            {
                "id": "u" * 32,
                "email": "old@example.test",
                "hash": hash_password("correct-horse-battery"),
                "active": True,
                "at": stamp,
            },
        )
        connection.execute(
            text(
                "INSERT INTO bets (id, user_id, bet_type, status, result, sport, sportsbook, "
                "stake, odds_decimal, odds_source, payout, profit, placed_at, settled_at, "
                "settled_by, source, created_at, updated_at) VALUES (:id, :user, 'straight', "
                "'settled', 'won', 'nba', 'Northline', 40, 2.0, 'legs', 80, 40, :at, :at, "
                "'user', 'manual', :at, :at)"
            ).bindparams(at),
            {"id": "b" * 32, "user": "u" * 32, "at": stamp},
        )
        connection.execute(
            text(
                "INSERT INTO bet_legs (id, bet_id, position, selection, market, odds_decimal) "
                "VALUES (:id, :bet, 0, 'Tides ML', 'moneyline', 2.0)"
            ),
            {"id": "B" * 32, "bet": "b" * 32},
        )
        connection.execute(
            text(
                "INSERT INTO notifications (id, user_id, kind, title, body, data, dedupe_key, "
                "created_at) VALUES (:id, :user, 'bet_settled', 'Bet settled', 'Won.', '{}', "
                "'k1', :at)"
            ).bindparams(at),
            {"id": "n" * 32, "user": "u" * 32, "at": stamp},
        )

    command.upgrade(config, "head")
    engine = make_engine(url)
    assert set(inspect(engine).get_table_names()) >= TABLES_0004
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
        assert diff == [], diff
        # Existing users get the safe defaults; nothing else is invented.
        row = connection.execute(
            text("SELECT plan, status, last_login_at, email_verified_at FROM users")
        ).one()
        assert tuple(row) == ("free", "active", None, None)
        for table in sorted(TABLES_0004):
            assert connection.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0
    command.check(config)  # `alembic check`: models and migrations agree
    engine.dispose()

    # The current app on the upgraded data: the old login, then the new features.
    app = make_app(
        database_url=url,
        env="production",
        jwt_secret="k" * 48,
        admin_emails="boss@example.test",
    )
    with TestClient(app) as client:
        login = client.post(
            "/v1/auth/login",
            json={"email": "old@example.test", "password": "correct-horse-battery"},
        )
        assert login.status_code == 200, login.text
        user = login.json()["user"]
        assert (user["plan"], user["email_verified"]) == ("free", False)
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert client.get("/v1/flags").json()["flags"]["community"] is False
        entitlements = client.get("/v1/me/entitlements", headers=headers).json()
        assert entitlements["plan"] == "free" and entitlements["preview"] is True
        analytics = client.get("/v1/bets/analytics", headers=headers).json()
        assert analytics["settled_count"] == 1 and analytics["sample_note"]
        assert client.get("/v1/value").status_code == 200
        # Production: ``email_flows`` is off until an operator turns it on.
        assert client.get("/v1/flags").json()["flags"]["email_flows"] is False
        off = client.post("/v1/auth/verify-email/request", headers=headers)
        assert off.status_code == 404 and off.json()["error"]["code"] == "feature_disabled"

        admin = client.post(
            "/v1/auth/register",
            json={
                "email": "boss@example.test",
                "password": "correct-horse-battery",
                "display_name": "Boss",
                "age_confirmed": True,
            },
        ).json()
        admin_headers = {"Authorization": f"Bearer {admin['access_token']}"}
        turned_on = client.put(
            "/v1/admin/flags/email_flows", json={"enabled": True}, headers=admin_headers
        )
        assert turned_on.status_code == 200, turned_on.text
        requested = client.post("/v1/auth/verify-email/request", headers=headers)
        assert requested.status_code == 202, requested.text
        reset = client.post("/v1/auth/password-reset/request", json={"email": user["email"]})
        assert reset.status_code == 202
        listed = client.get("/v1/admin/users", headers=admin_headers).json()
        assert listed["total"] == 2
        old = next(u for u in listed["items"] if u["email"] == "old@example.test")
        assert (old["bet_count"], old["status"], old["last_login_at"] is not None) == (
            1,
            "active",
            True,
        )
        assert (
            client.put(
                "/v1/admin/flags/community", json={"enabled": True}, headers=admin_headers
            ).status_code
            == 200
        )
        assert (
            client.put(
                f"/v1/admin/users/{old['id']}/plan", json={"plan": "premium"}, headers=admin_headers
            ).json()["plan"]
            == "premium"
        )
    app.state.engine.dispose()
    engine = make_engine(url)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM feature_flags")).scalar() == 2
        # Two emails queued for the old user, none sent. The administrator registered
        # while ``email_flows`` was still off, so no confirmation email was queued.
        assert connection.execute(text("SELECT count(*) FROM email_outbox")).scalar() == 2
        # Production: the outbox never holds a usable link.
        assert (
            connection.execute(
                text("SELECT count(*) FROM email_outbox WHERE dev_link IS NOT NULL")
            ).scalar()
            == 0
        )
    engine.dispose()

    # Downgrade removes only what 0004 added; the 0003 data is untouched.
    command.downgrade(config, "0003")
    engine = make_engine(url)
    tables = set(inspect(engine).get_table_names())
    assert not TABLES_0004 & tables and tables >= NEW_TABLES
    assert not COLUMNS_0004 & {c["name"] for c in inspect(engine).get_columns("users")}
    with engine.connect() as connection:
        emails = connection.execute(text("SELECT email FROM users ORDER BY created_at")).scalars()
        assert list(emails) == ["old@example.test", "boss@example.test"]
        assert connection.execute(text("SELECT count(*) FROM bets")).scalar() == 1
        assert connection.execute(text("SELECT count(*) FROM bet_legs")).scalar() == 1
        assert connection.execute(text("SELECT count(*) FROM notifications")).scalar() == 1
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0003"
        )
    engine.dispose()

    # Up again (defaults again, new tables empty), then all the way down.
    command.upgrade(config, "head")
    engine = make_engine(url)
    with engine.connect() as connection:
        plans = connection.execute(text("SELECT DISTINCT plan, status FROM users")).all()
        assert [tuple(r) for r in plans] == [("free", "active")]
        for table in sorted(TABLES_0004):
            assert connection.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0
    engine.dispose()
    command.downgrade(config, "base")
    engine = make_engine(url)
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    engine.dispose()
    if backend != "sqlite":
        _reset_external_database(url)


def test_app_works_on_a_migrated_database_without_auto_create(
    tmp_path: Path, make_app: AppFactory
) -> None:
    url = f"sqlite:///{tmp_path / 'prodlike.db'}"
    command.upgrade(alembic_config(url), "head")
    app = make_app(database_url=url, env="production", jwt_secret="k" * 48)
    with TestClient(app) as client:
        body = {
            "email": "ada@example.test",
            "password": "correct-horse-battery",
            "display_name": "Ada",
            "age_confirmed": True,
        }
        token = client.post("/v1/auth/register", json=body).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        bet = {
            "bet_type": "straight",
            "stake": 10,
            "sportsbook": "Northline",
            "legs": [{"selection": "x", "market": "moneyline", "odds": -110}],
        }
        assert client.post("/v1/bets", json=bet, headers=headers).status_code == 201
        connection = client.post("/v1/sync/connections", json={}, headers=headers).json()
        assert (
            client.post(
                f"/v1/sync/connections/{connection['id']}/sync", headers=headers
            ).status_code
            == 200
        )
        assert client.delete("/v1/me", headers=headers).status_code == 204


def test_alembic_cli_upgrade(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_ROOT,
        env={"DATABASE_URL": f"sqlite:///{tmp_path / 'cli.db'}", "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert set(inspect(make_engine(f"sqlite:///{tmp_path / 'cli.db'}")).get_table_names()) >= TABLES


def test_production_does_not_create_tables_on_startup(tmp_path: Path, make_app: AppFactory) -> None:
    url = f"sqlite:///{tmp_path / 'empty.db'}"
    with TestClient(make_app(database_url=url, env="production", jwt_secret="k" * 48)):
        pass
    assert inspect(make_engine(url)).get_table_names() == []
    with TestClient(make_app(database_url=url, env="development")):
        pass
    assert set(inspect(make_engine(url)).get_table_names()) >= TABLES


# ----------------------------------------------------------------------- seed
@pytest.fixture
def session_factory(tmp_path: Path):  # type: ignore[no-untyped-def]
    engine = make_engine(f"sqlite:///{tmp_path / 'seed.db'}")
    Base.metadata.create_all(engine)
    return make_session_factory(engine)


def test_seed_creates_a_varied_history(session_factory) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as db:
        assert seed_demo(db, "demo-password-123", NOW) == DEMO_BET_COUNT == 40
    with session_factory() as db:
        user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        assert user is not None and user.role == "user"
        assert user.password_hash.startswith("$argon2")
        bets = list(db.scalars(select(Bet).where(Bet.user_id == user.id)))
    assert len(bets) == 40
    settled = [b for b in bets if b.status == "settled"]
    pending = [b for b in bets if b.status == "pending"]
    assert len(pending) >= 7 and len(settled) >= 28
    assert {b.bet_type for b in bets} >= {"straight", "parlay", "future"}
    assert {b.result for b in settled} >= {"won", "lost"}
    assert len({b.sportsbook for b in bets}) >= 4
    assert len({b.sport for b in bets}) >= 4
    assert all(NOW - timedelta(days=61) <= b.placed_at <= NOW for b in bets)
    assert min(b.placed_at for b in bets) < NOW - timedelta(days=50)
    assert all(b.settled_at is not None and b.placed_at <= b.settled_at <= NOW for b in settled)
    assert all(b.payout is not None and b.profit == b.payout - b.stake for b in settled)
    assert all(b.payout is None for b in pending)
    assert any(leg.closing_odds_decimal is not None for b in bets for leg in b.legs)
    text = " ".join(
        f"{leg.selection} {leg.event_label} {b.sportsbook}" for b in bets for leg in b.legs
    ).lower()
    assert not any(real in text for real in REAL_NAMES)


def test_seed_is_idempotent_and_deterministic(session_factory, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as db:
        seed_demo(db, "demo-password-123", NOW)
        first = {
            b.external_bet_id: (b.stake, b.odds_decimal, b.result, b.payout)
            for b in db.scalars(select(Bet))
        }
        password_hash = db.scalar(select(User.password_hash))
    with session_factory() as db:
        assert seed_demo(db, "a-different-password", NOW) == 0
        assert len(list(db.scalars(select(Bet)))) == 40
        assert len(list(db.scalars(select(User)))) == 1
        assert db.scalar(select(User.password_hash)) == password_hash  # not reset

    # Deleting some bets and re-seeding restores exactly the missing ones.
    with session_factory() as db:
        for bet in list(
            db.scalars(select(Bet).where(Bet.external_bet_id.in_(["demo-005", "demo-020"])))
        ):
            db.delete(bet)
        db.commit()
    with session_factory() as db:
        assert seed_demo(db, "x" * 12, NOW) == 2
        again = {
            b.external_bet_id: (b.stake, b.odds_decimal, b.result, b.payout)
            for b in db.scalars(select(Bet))
        }
    assert again == first


def test_seed_with_a_provider_adds_alert_rules_and_notifications(session_factory) -> None:  # type: ignore[no-untyped-def]
    provider = SyntheticProvider(seed=20260101, clock=lambda: NOW)
    with session_factory() as db:
        assert seed_demo(db, "demo-password-123", NOW, provider=provider) == 44
    with session_factory() as db:
        rules = list(db.scalars(select(AlertRule).order_by(AlertRule.created_at, AlertRule.id)))
        notifications = list(db.scalars(select(Notification)))
        demo = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    assert demo is not None
    assert {r.user_id for r in rules} == {demo.id} == {n.user_id for n in notifications}
    assert {r.kind for r in rules} == {"price_at_least", "line_move", "game_start", "game_final"}
    by_state: dict[str, list[AlertRule]] = {}
    for rule in rules:
        by_state.setdefault(rule.state, []).append(rule)
    # One price alert was already met and fired; the rest are still waiting.
    assert [r.kind for r in by_state["triggered"]] == ["price_at_least"]
    assert {r.kind for r in by_state["active"]} >= {"price_at_least", "line_move"}
    assert set(by_state) == {"triggered", "active"}

    kinds = [n.kind for n in notifications]
    assert kinds.count("price_alert") == 1 and kinds.count("game_final") == 2
    assert 3 <= len(notifications) <= 6
    assert all(n.read_at is None and n.rule_id in {r.id for r in rules} for n in notifications)
    price = next(n for n in notifications if n.kind == "price_alert")
    assert re.fullmatch(r"Price reached [+-]\d{3,}", price.title)
    assert re.search(r"at or above your [+-]\d{3,} alert\.$", price.body)
    text = " ".join(f"{n.title} {n.body}" for n in notifications).lower()
    assert not any(real in text for real in REAL_NAMES)
    assert "!" not in text

    # Seeding again adds neither rules nor notifications.
    with session_factory() as db:
        assert seed_demo(db, "demo-password-123", NOW, provider=provider) == 0
        assert len(list(db.scalars(select(AlertRule)))) == len(rules)
        assert len(list(db.scalars(select(Notification)))) == len(notifications)
    # Without a provider there is nothing to build rules on.
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with make_session_factory(engine)() as db:
        assert seed_demo(db, "demo-password-123", NOW) == 40
        assert list(db.scalars(select(AlertRule))) == []


def test_demo_user_can_log_in_and_see_a_summary(make_app: AppFactory) -> None:
    app = make_app(auto_seed_demo=True, demo_password="demo-password-123")
    with TestClient(app) as client:
        login = client.post(
            "/v1/auth/login", json={"email": DEMO_EMAIL, "password": "demo-password-123"}
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        # 40 history bets plus the gradeable ones the app seeds with its provider.
        assert DEMO_BET_COUNT + DEMO_GRADEABLE_COUNT == 44
        assert len(client.get("/v1/bets", headers=headers).json()) == 44
        summary = client.get("/v1/bets/summary", headers=headers).json()
        assert summary["totals"]["settled_count"] >= 28
        assert summary["totals"]["pending_count"] >= 7
        assert summary["totals"]["avg_clv"] is not None
        assert len(summary["timeline"]) >= 15
        assert len(summary["by_sport"]) >= 4
        # The seeded alert rules and their notifications are there to look at.
        alerts = client.get("/v1/alerts", headers=headers).json()["items"]
        assert {a["state"] for a in alerts} == {"triggered", "active"}
        assert all(a["summary"] and a["available"] for a in alerts)
        listed = client.get("/v1/notifications", headers=headers).json()
        assert listed["unread_count"] == len(listed["items"]) >= 3


def test_production_never_auto_seeds(tmp_path: Path, make_app: AppFactory) -> None:
    url = f"sqlite:///{tmp_path / 'prod.db'}"
    command.upgrade(alembic_config(url), "head")
    app = make_app(database_url=url, env="production", jwt_secret="k" * 48, auto_seed_demo=True)
    with TestClient(app) as client:
        login = client.post(
            "/v1/auth/login", json={"email": DEMO_EMAIL, "password": "oddvex-demo-2026"}
        )
        assert login.status_code == 401
    with make_session_factory(make_engine(url))() as db:
        assert list(db.scalars(select(User))) == []


def test_seed_script_refuses_production(tmp_path: Path) -> None:
    env = {
        "DATABASE_URL": f"sqlite:///{tmp_path / 'script.db'}",
        "ODDVEX_ENV": "production",
        "ODDVEX_JWT_SECRET": "k" * 48,
        "PATH": "/usr/bin:/bin",
    }
    script = str(API_ROOT / "scripts" / "seed_demo.py")
    refused = subprocess.run(
        [sys.executable, script], cwd=tmp_path, env=env, capture_output=True, text=True, check=False
    )
    assert refused.returncode == 2
    assert "Refusing" in refused.stderr
    env["ODDVEX_ENV"] = "development"
    first = subprocess.run(
        [sys.executable, script], cwd=tmp_path, env=env, capture_output=True, text=True, check=False
    )
    assert first.returncode == 0, first.stderr
    assert "44 bet(s) created" in first.stdout  # 40 history bets + 4 gradeable
    second = subprocess.run(
        [sys.executable, script], cwd=tmp_path, env=env, capture_output=True, text=True, check=False
    )
    assert "0 bet(s) created" in second.stdout
    # No administrator unless the operator asks for one.
    assert "No admin user created" in first.stdout and "No admin user created" in second.stdout
    engine = make_engine(env["DATABASE_URL"])
    with make_session_factory(engine)() as db:
        assert [u.email for u in db.scalars(select(User))] == [DEMO_EMAIL]
        assert db.scalar(select(User)).email_verified is True

    env["ODDVEX_ADMIN_EMAILS"] = "someone@example.test, admin@oddvex.test"
    for _ in range(2):  # idempotent
        third = subprocess.run(
            [sys.executable, script],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert third.returncode == 0, third.stderr
        assert "Admin user admin@oddvex.test ready (role: admin)." in third.stdout
        assert "0 bet(s) created" in third.stdout
    with make_session_factory(engine)() as db:
        users = {u.email: u for u in db.scalars(select(User))}
        assert set(users) == {DEMO_EMAIL, DEMO_ADMIN_EMAIL}  # nobody else was invented
        assert (users[DEMO_ADMIN_EMAIL].role, users[DEMO_EMAIL].role) == ("admin", "user")
        assert users[DEMO_ADMIN_EMAIL].email_verified is True
    engine.dispose()


def test_seed_verifies_the_demo_user_and_only_creates_a_listed_admin(
    session_factory,
    make_settings,  # type: ignore[no-untyped-def]
) -> None:
    with session_factory() as db:
        seed_demo(db, "pw-one-1234", NOW)
        seed_demo(db, "pw-one-1234", NOW, settings=make_settings())
        seed_demo(db, "pw-one-1234", NOW, settings=make_settings(admin_emails="x@example.test"))
        (demo,) = db.scalars(select(User))
        assert demo.email == DEMO_EMAIL and demo.email_verified_at == NOW
        assert (demo.role, demo.plan, demo.status) == ("user", "free", "active")

        # A demo user from before email verification existed is marked verified too.
        demo.email_verified_at = None
        db.commit()
        later = NOW + timedelta(days=1)
        listed = make_settings(admin_emails="admin@oddvex.test")
        assert seed_demo(db, "pw-two-5678", later, settings=listed) == 0
        users = {u.email: u for u in db.scalars(select(User))}
        assert set(users) == {DEMO_EMAIL, DEMO_ADMIN_EMAIL}
        assert users[DEMO_EMAIL].email_verified_at == later
        admin = users[DEMO_ADMIN_EMAIL]
        assert (admin.role, admin.email_verified_at) == ("admin", later)
        first_hash = admin.password_hash

        # Idempotent: no second admin, password untouched.
        seed_demo(db, "pw-three-9012", later, settings=listed)
        assert len(list(db.scalars(select(User)))) == 2
        db.refresh(admin)
        assert admin.password_hash == first_hash
        assert db.scalar(select(Bet.id).where(Bet.user_id == admin.id)) is None


# -------------------------------------------------------------------- OpenAPI
EXPECTED_OPERATIONS = {
    ("GET", "/health"): "get_health",
    ("GET", "/v1/meta"): "get_meta",
    ("GET", "/v1/leagues"): "list_leagues",
    ("GET", "/v1/sportsbooks"): "list_sportsbooks",
    ("GET", "/v1/events"): "list_events",
    ("GET", "/v1/events/{event_id}"): "get_event",
    ("GET", "/v1/events/{event_id}/odds"): "get_event_odds",
    ("GET", "/v1/events/{event_id}/line-history"): "get_event_line_history",
    ("GET", "/v1/players"): "list_players",
    ("GET", "/v1/players/{player_id}"): "get_player",
    ("GET", "/v1/players/{player_id}/props"): "get_player_props",
    ("GET", "/v1/props"): "list_props",
    ("POST", "/v1/quant/convert"): "quant_convert",
    ("POST", "/v1/quant/no-vig"): "quant_no_vig",
    ("POST", "/v1/quant/ev"): "quant_ev",
    ("POST", "/v1/quant/parlay"): "quant_parlay",
    ("POST", "/v1/quant/clv"): "quant_clv",
    ("POST", "/v1/auth/register"): "register",
    ("POST", "/v1/auth/login"): "login",
    ("GET", "/v1/me"): "get_me",
    ("DELETE", "/v1/me"): "delete_me",
    ("GET", "/v1/me/export"): "export_my_data",
    ("POST", "/v1/me/password"): "change_password",
    ("GET", "/v1/watchlist"): "list_watchlist",
    ("POST", "/v1/watchlist"): "add_watchlist_item",
    ("GET", "/v1/watchlist/events"): "list_watchlist_events",
    ("DELETE", "/v1/watchlist/{item_id}"): "remove_watchlist_item",
    ("GET", "/v1/alerts"): "list_alerts",
    ("POST", "/v1/alerts"): "create_alert",
    ("POST", "/v1/alerts/evaluate"): "evaluate_alerts",
    ("PATCH", "/v1/alerts/{alert_id}"): "update_alert",
    ("DELETE", "/v1/alerts/{alert_id}"): "delete_alert",
    ("GET", "/v1/notifications"): "list_notifications",
    ("GET", "/v1/notifications/unread-count"): "get_unread_count",
    ("POST", "/v1/notifications/read-all"): "mark_all_notifications_read",
    ("POST", "/v1/notifications/{notification_id}/read"): "mark_notification_read",
    ("DELETE", "/v1/notifications/{notification_id}"): "delete_notification",
    ("GET", "/v1/me/notification-preferences"): "get_notification_preferences",
    ("PUT", "/v1/me/notification-preferences"): "update_notification_preferences",
    ("GET", "/v1/me/stake-reminder"): "get_stake_reminder",
    ("PUT", "/v1/me/stake-reminder"): "update_stake_reminder",
    ("POST", "/v1/bets/auto-settle"): "auto_settle_bets",
    ("GET", "/v1/bets"): "list_bets",
    ("POST", "/v1/bets"): "create_bet",
    ("GET", "/v1/bets/summary"): "get_bet_summary",
    ("GET", "/v1/bets/{bet_id}"): "get_bet",
    ("PATCH", "/v1/bets/{bet_id}"): "update_bet",
    ("DELETE", "/v1/bets/{bet_id}"): "delete_bet",
    ("POST", "/v1/bets/{bet_id}/settle"): "settle_bet",
    ("GET", "/v1/sync/providers"): "list_sync_providers",
    ("GET", "/v1/sync/connections"): "list_sync_connections",
    ("POST", "/v1/sync/connections"): "create_sync_connection",
    ("POST", "/v1/sync/connections/{connection_id}/sync"): "run_sync",
    ("GET", "/v1/sync/connections/{connection_id}/runs"): "list_sync_runs",
    ("DELETE", "/v1/sync/connections/{connection_id}"): "delete_sync_connection",
    ("POST", "/v1/assistant/query"): "assistant_query",
    ("GET", "/v1/admin/overview"): "get_admin_overview",
    ("GET", "/v1/flags"): "list_flags",
    ("GET", "/v1/me/entitlements"): "get_entitlements",
    ("GET", "/v1/value"): "list_value",
    ("GET", "/v1/bets/analytics"): "get_bet_analytics",
    ("GET", "/v1/admin/users"): "admin_list_users",
    ("POST", "/v1/admin/users/{user_id}/suspend"): "admin_suspend_user",
    ("POST", "/v1/admin/users/{user_id}/unsuspend"): "admin_unsuspend_user",
    ("PUT", "/v1/admin/users/{user_id}/plan"): "admin_set_user_plan",
    ("GET", "/v1/admin/flags"): "admin_list_flags",
    ("PUT", "/v1/admin/flags/{key}"): "admin_set_flag",
    ("GET", "/v1/admin/audit"): "admin_list_audit",
    ("GET", "/v1/admin/email-outbox"): "admin_list_email_outbox",
    ("POST", "/v1/auth/verify-email/request"): "request_email_verification",
    ("POST", "/v1/auth/verify-email/confirm"): "confirm_email_verification",
    ("POST", "/v1/auth/password-reset/request"): "request_password_reset",
    ("POST", "/v1/auth/password-reset/confirm"): "confirm_password_reset",
    ("GET", "/v1/dev/email-outbox/latest"): "dev_latest_email",
    ("POST", "/v1/auth/logout"): "logout",
    ("GET", "/v1/community/guidelines"): "get_community_guidelines",
    ("PUT", "/v1/community/profile"): "upsert_my_profile",
    ("GET", "/v1/community/profile"): "get_my_profile",
    ("GET", "/v1/community/profiles/{handle}"): "get_profile",
    ("POST", "/v1/community/picks"): "create_pick",
    ("GET", "/v1/community/picks"): "list_picks",
    ("GET", "/v1/community/picks/{pick_id}"): "get_pick",
    ("DELETE", "/v1/community/picks/{pick_id}"): "delete_pick",
    ("GET", "/v1/community/feed"): "get_feed",
    ("PUT", "/v1/community/picks/{pick_id}/like"): "like_pick",
    ("DELETE", "/v1/community/picks/{pick_id}/like"): "unlike_pick",
    ("POST", "/v1/community/picks/{pick_id}/comments"): "create_comment",
    ("GET", "/v1/community/picks/{pick_id}/comments"): "list_comments",
    ("DELETE", "/v1/community/comments/{comment_id}"): "delete_comment",
    ("POST", "/v1/community/follows/{handle}"): "follow_profile",
    ("DELETE", "/v1/community/follows/{handle}"): "unfollow_profile",
    ("GET", "/v1/community/following"): "list_following",
    ("GET", "/v1/community/followers"): "list_followers",
    ("PUT", "/v1/community/blocks/{handle}"): "block_profile",
    ("DELETE", "/v1/community/blocks/{handle}"): "unblock_profile",
    ("GET", "/v1/community/blocks"): "list_blocks",
    ("POST", "/v1/community/reports"): "create_report",
    ("GET", "/v1/community/leaderboard"): "get_leaderboard",
    ("GET", "/v1/admin/community/overview"): "admin_community_overview",
    ("GET", "/v1/admin/community/reports"): "admin_list_reports",
    ("POST", "/v1/admin/community/reports/{report_id}/resolve"): "admin_resolve_report",
}


def test_every_route_has_a_stable_operation_id_and_response_model(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    found = {
        (method.upper(), path): operation
        for path, item in schema["paths"].items()
        for method, operation in item.items()
    }
    assert {key: op["operationId"] for key, op in found.items()} == EXPECTED_OPERATIONS
    for key, operation in found.items():
        assert re.fullmatch(r"[a-z][a-z0-9_]*", operation["operationId"])
        success = next(code for code in operation["responses"] if code.startswith("2"))
        if success == "204":
            continue
        body = operation["responses"][success]["content"]["application/json"]["schema"]
        ref = body.get("$ref") or body.get("items", {}).get("$ref")
        assert ref and ref.startswith("#/components/schemas/"), key
        for code, response in operation["responses"].items():
            if code.startswith(("4", "5")):
                error_schema = response["content"]["application/json"]["schema"]
                assert error_schema == {"$ref": "#/components/schemas/ErrorResponse"}, (key, code)
    names = set(schema["components"]["schemas"])
    assert "HTTPValidationError" not in names and "ValidationError" not in names
    assert {"ErrorResponse", "ErrorBody", "PriceOut", "EventOddsOut", "BetOut"} <= names


def test_committed_openapi_json_is_current_and_deterministic() -> None:
    path = API_ROOT / "openapi.json"
    script = [sys.executable, str(API_ROOT / "scripts" / "export_openapi.py"), "--check"]
    # A hostile environment must not change the output.
    env = {
        "PATH": "/usr/bin:/bin",
        "ODDVEX_ENV": "production",
        "ODDVEX_CORS_ORIGINS": "https://x.example.test",
    }
    result = subprocess.run(
        script, cwd=API_ROOT, env=env, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    text = path.read_text(encoding="utf-8")
    assert text.endswith("}\n") and not text.endswith("\n\n")
    document = json.loads(text)
    assert text == json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    assert document["info"]["title"] == "OddVex API"
