"""Alembic migration, demo seed and the committed OpenAPI document."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import DateTime, bindparam, func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from oddvex_api.auth.security import hash_password
from oddvex_api.community.content_rules import check_text
from oddvex_api.community.seed import FICTIONAL_PROFILES
from oddvex_api.db import (
    AlertRule,
    Base,
    Bet,
    CommunityComment,
    CommunityFollow,
    CommunityLike,
    CommunityPick,
    CommunityProfile,
    FeatureFlag,
    Notification,
    User,
    make_engine,
    make_session_factory,
)
from oddvex_api.flags import service as flags_service
from oddvex_api.providers import SyntheticProvider
from oddvex_api.quant import grade_leg
from oddvex_api.seed import (
    DEMO_ADMIN_EMAIL,
    DEMO_BET_COUNT,
    DEMO_EMAIL,
    DEMO_GRADEABLE_COUNT,
    seed_demo,
)

from .conftest import (
    EXTERNAL_DATABASE_URL,
    AppFactory,
    _reset_external_database,
    mark_email_verified,
)
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
    "community_reserved_handles",
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
        # The list alone gives nobody the role: the address has to be verified, and in
        # production that is an operator step.
        assert client.get("/v1/admin/users", headers=admin_headers).status_code == 403
        mark_email_verified(client, "boss@example.test")
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


TABLES_0005 = {
    "community_profiles",
    "community_picks",
    "community_comments",
    "community_follows",
    "community_likes",
    "community_blocks",
    "community_reports",
}


@pytest.mark.parametrize("backend", _database_urls())
def test_upgrade_from_0004_with_existing_data_then_downgrade(
    backend: str, tmp_path: Path, make_app: AppFactory
) -> None:
    if backend == "sqlite":
        url = f"sqlite:///{tmp_path / 'upgrade_0005.db'}"
    else:
        url = backend
        _reset_external_database(url)
    config = alembic_config(url)
    command.upgrade(config, "0004")
    engine = make_engine(url)
    assert not TABLES_0005 & set(inspect(engine).get_table_names())
    assert "search_key" not in {c["name"] for c in inspect(engine).get_columns("users")}
    assert "sportsbook_key" not in {c["name"] for c in inspect(engine).get_columns("bets")}

    # Rows written by the 0004 release: two users and bets at sportsbooks whose names
    # SQL lower() cannot fold on SQLite or on PostgreSQL with the C locale.
    stamp = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)
    at = bindparam("at", type_=DateTime(timezone=True))
    users = (("u" * 32, "old@example.test", "Zoë ÜNSAL"), ("v" * 32, "jose@example.test", "JOSÉ"))
    bets = (
        ("a" * 32, "u" * 32, "Éclair Sports"),
        ("b" * 32, "u" * 32, "ÉCLAIR SPORTS"),
        ("c" * 32, "u" * 32, "Northline"),
        ("d" * 32, "v" * 32, "STRASSE Wetten"),
    )
    with engine.begin() as connection:
        for user_id, email, name in users:
            connection.execute(
                text(
                    "INSERT INTO users (id, email, password_hash, display_name, role, "
                    "is_active, age_confirmed_at, created_at, token_version, plan, status) "
                    "VALUES (:id, :email, :hash, :name, 'user', :active, :at, :at, 0, 'free', "
                    "'active')"
                ).bindparams(at),
                {
                    "id": user_id,
                    "email": email,
                    "name": name,
                    "hash": hash_password("correct-horse-battery"),
                    "active": True,
                    "at": stamp,
                },
            )
        for bet_id, user_id, sportsbook in bets:
            connection.execute(
                text(
                    "INSERT INTO bets (id, user_id, bet_type, status, sport, sportsbook, stake, "
                    "odds_decimal, odds_source, placed_at, source, created_at, updated_at) "
                    "VALUES (:id, :user, 'straight', 'pending', 'nba', :sportsbook, 10, 2.0, "
                    "'legs', :at, 'manual', :at, :at)"
                ).bindparams(at),
                {"id": bet_id, "user": user_id, "sportsbook": sportsbook, "at": stamp},
            )
            connection.execute(
                text(
                    "INSERT INTO bet_legs (id, bet_id, position, selection, market, "
                    "odds_decimal) VALUES (:id, :bet, 0, 'Tides ML', 'moneyline', 2.0)"
                ),
                {"id": bet_id.upper(), "bet": bet_id},
            )

    command.upgrade(config, "head")
    engine = make_engine(url)
    assert set(inspect(engine).get_table_names()) >= TABLES_0005
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
        assert diff == [], diff
        # Nothing was invented: nobody has a profile until they create one.
        for table in sorted(TABLES_0005):
            assert connection.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0
        # Existing rows were backfilled with the keys the application computes.
        keys = dict(connection.execute(text("SELECT email, search_key FROM users")).all())
        assert keys == {
            "old@example.test": "old@example.test\nzoë ünsal",
            "jose@example.test": "jose@example.test\njosé",
        }
        books = dict(connection.execute(text("SELECT id, sportsbook_key FROM bets")).all())
        assert books == {
            "a" * 32: "éclair sports",
            "b" * 32: "éclair sports",
            "c" * 32: "northline",
            "d" * 32: "strasse wetten",
        }
        # The names themselves are untouched.
        names = connection.execute(text("SELECT sportsbook FROM bets ORDER BY id")).scalars()
        assert list(names) == [b[2] for b in bets]
    command.check(config)  # `alembic check`: models and migrations agree
    engine.dispose()

    # The current app on the upgraded data: the filters work on the old rows, and the
    # new features work for the old account.
    app = make_app(
        database_url=url,
        env="production",
        jwt_secret="k" * 48,
        admin_emails="boss@example.test",
        community_grade_min_seconds=0,
    )
    with TestClient(app) as client:
        login = client.post(
            "/v1/auth/login",
            json={"email": "old@example.test", "password": "correct-horse-battery"},
        )
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        found = client.get("/v1/bets", params={"sportsbook": "éclair sports"}, headers=headers)
        assert sorted(b["sportsbook"] for b in found.json()) == ["ÉCLAIR SPORTS", "Éclair Sports"]
        assert len(client.get("/v1/bets", headers=headers).json()) == 3
        assert client.get("/health").json()["database"] == "ok"

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
        mark_email_verified(client, "boss@example.test")  # the admin role needs it
        searched = client.get("/v1/admin/users", params={"q": "ZOË ünsal"}, headers=admin_headers)
        assert [u["email"] for u in searched.json()["items"]] == ["old@example.test"]
        searched = client.get("/v1/admin/users", params={"q": "josé"}, headers=admin_headers)
        assert [u["email"] for u in searched.json()["items"]] == ["jose@example.test"]

        # Community: off, then on, then used by the account from before the migration.
        assert client.get("/v1/community/feed", headers=headers).status_code == 404
        for key in ("community", "community_leaderboard"):
            turned_on = client.put(
                f"/v1/admin/flags/{key}", json={"enabled": True}, headers=admin_headers
            )
            assert turned_on.status_code == 200, turned_on.text
        profile = client.put(
            "/v1/community/profile",
            json={"handle": "old_timer", "is_public": True},
            headers=headers,
        )
        assert profile.status_code == 201, profile.text
        event = client.get("/v1/events", params={"status": "upcoming"}).json()[0]
        pick = client.post(
            "/v1/community/picks",
            json={"event_id": event["id"], "market": "moneyline", "outcome_key": "home"},
            headers=headers,
        )
        assert pick.status_code == 201, pick.text
        liked = client.put(f"/v1/community/picks/{pick.json()['id']}/like", headers=admin_headers)
        assert liked.json()["like_count"] == 1
        reported = client.post(
            "/v1/community/reports",
            json={"target_type": "pick", "target_id": pick.json()["id"], "reason": "other"},
            headers=admin_headers,
        )
        assert reported.status_code == 201, reported.text
        assert (
            len(client.get("/v1/community/feed?scope=everyone", headers=headers).json()["items"])
            == 1
        )
        assert client.get("/v1/community/leaderboard", headers=headers).json()["items"] == []
        export = client.get("/v1/me/export", headers=headers).json()
        assert export["community"]["profile"]["handle"] == "old_timer"
        assert len(export["community"]["picks"]) == 1 and len(export["bets"]) == 3
        assert client.post("/v1/auth/logout", headers=headers).status_code == 204
        assert client.get("/v1/me", headers=headers).status_code == 401
    app.state.engine.dispose()

    # Downgrade removes only what 0005 added; the 0004 data is untouched.
    command.downgrade(config, "0004")
    engine = make_engine(url)
    tables = set(inspect(engine).get_table_names())
    assert not TABLES_0005 & tables and tables >= TABLES_0004 | NEW_TABLES
    assert "search_key" not in {c["name"] for c in inspect(engine).get_columns("users")}
    assert "sportsbook_key" not in {c["name"] for c in inspect(engine).get_columns("bets")}
    with engine.connect() as connection:
        emails = connection.execute(text("SELECT email FROM users ORDER BY created_at, email"))
        assert list(emails.scalars()) == [
            "jose@example.test",
            "old@example.test",
            "boss@example.test",
        ]
        assert connection.execute(text("SELECT count(*) FROM bets")).scalar() == 4
        assert connection.execute(text("SELECT count(*) FROM bet_legs")).scalar() == 4
        names = connection.execute(text("SELECT sportsbook FROM bets ORDER BY id")).scalars()
        assert list(names) == [b[2] for b in bets]
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0004"
        )
    engine.dispose()

    # Up again: the keys are backfilled again and the community tables start empty.
    command.upgrade(config, "head")
    engine = make_engine(url)
    with engine.connect() as connection:
        for table in sorted(TABLES_0005):
            assert connection.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0
        missing = connection.execute(
            text("SELECT count(*) FROM bets WHERE sportsbook_key IS NULL")
        ).scalar()
        assert missing == 0
        missing = connection.execute(
            text("SELECT count(*) FROM users WHERE search_key IS NULL")
        ).scalar()
        assert missing == 0
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
        assert diff == [], diff
    command.check(config)
    engine.dispose()
    command.downgrade(config, "base")
    engine = make_engine(url)
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    engine.dispose()
    if backend != "sqlite":
        _reset_external_database(url)


@pytest.mark.parametrize("backend", _database_urls())
def test_upgrade_from_0005_with_existing_data_then_downgrade(
    backend: str, tmp_path: Path, make_app: AppFactory
) -> None:
    if backend == "sqlite":
        url = f"sqlite:///{tmp_path / 'upgrade_0006.db'}"
    else:
        url = backend
        _reset_external_database(url)
    config = alembic_config(url)
    command.upgrade(config, "0005")
    engine = make_engine(url)
    assert "client_request_id" not in {c["name"] for c in inspect(engine).get_columns("bets")}
    assert "uq_bets_user_client_request" not in {
        index["name"] for index in inspect(engine).get_indexes("bets")
    }

    # Rows written by the 0005 release: one user with three bets and their legs. One of
    # the bets holds what that release could store and the current one refuses: a price
    # rounded to exactly 1.000000 and a stake rounded to 0.00.
    stamp = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)
    at = bindparam("at", type_=DateTime(timezone=True))
    bets = (
        ("a" * 32, "Northline", "10", "2.0"),
        ("b" * 32, "Harbor", "25", "1.909091"),
        ("c" * 32, "Rounded", "0", "1.000000"),
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, email, password_hash, display_name, role, "
                "is_active, age_confirmed_at, created_at, token_version, plan, status, "
                "search_key) VALUES (:id, :email, :hash, 'Old', 'user', :active, :at, :at, 0, "
                "'free', 'active', :key)"
            ).bindparams(at),
            {
                "id": "u" * 32,
                "email": "old@example.test",
                "hash": hash_password("correct-horse-battery"),
                "active": True,
                "at": stamp,
                "key": "old@example.test\nold",
            },
        )
        for bet_id, sportsbook, stake, odds in bets:
            connection.execute(
                text(
                    "INSERT INTO bets (id, user_id, bet_type, status, sport, sportsbook, "
                    "sportsbook_key, stake, odds_decimal, odds_source, placed_at, source, "
                    "created_at, updated_at) VALUES (:id, :user, 'straight', 'pending', 'nba', "
                    ":sportsbook, :key, :stake, :odds, 'legs', :at, 'manual', :at, :at)"
                ).bindparams(at),
                {
                    "id": bet_id,
                    "user": "u" * 32,
                    "sportsbook": sportsbook,
                    "key": sportsbook.lower(),
                    "stake": stake,
                    "odds": odds,
                    "at": stamp,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO bet_legs (id, bet_id, position, selection, market, "
                    "odds_decimal) VALUES (:id, :bet, 0, 'Tides ML', 'moneyline', :odds)"
                ),
                {"id": bet_id.upper(), "bet": bet_id, "odds": odds},
            )

    command.upgrade(config, "head")
    engine = make_engine(url)
    columns = {c["name"]: c for c in inspect(engine).get_columns("bets")}
    assert columns["client_request_id"]["nullable"] is True
    indexes = {index["name"]: index for index in inspect(engine).get_indexes("bets")}
    assert indexes["uq_bets_user_client_request"]["column_names"] == [
        "user_id",
        "client_request_id",
    ]
    assert bool(indexes["uq_bets_user_client_request"]["unique"]) is True
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
        assert diff == [], diff
        # Nothing existing was touched: every old bet is still there, without an id.
        rows = connection.execute(
            text("SELECT id, sportsbook, client_request_id FROM bets ORDER BY id")
        ).all()
        assert [tuple(row) for row in rows] == [(b[0], b[1], None) for b in bets]
        assert connection.execute(text("SELECT count(*) FROM bet_legs")).scalar() == 3
    command.check(config)  # `alembic check`: models and migrations agree

    # The index does its job in the database itself: one bet per user and id, any number
    # of bets without one.
    duplicate = text(
        "INSERT INTO bets (id, user_id, bet_type, status, sport, sportsbook, stake, "
        "odds_decimal, odds_source, placed_at, source, created_at, updated_at, "
        "client_request_id) VALUES (:id, :user, 'straight', 'pending', 'nba', 'Dup', 10, 2.0, "
        "'legs', :at, 'manual', :at, :at, :request)"
    ).bindparams(at)
    with engine.begin() as connection:
        connection.execute(
            duplicate, {"id": "d" * 32, "user": "u" * 32, "at": stamp, "request": "request-0001"}
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            duplicate, {"id": "e" * 32, "user": "u" * 32, "at": stamp, "request": "request-0001"}
        )
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM bets WHERE id = :id"), {"id": "d" * 32})
    engine.dispose()

    # The current app on the upgraded data: the old account's bets load everywhere,
    # including the one this release would refuse, and a create can be repeated safely.
    app = make_app(database_url=url, env="production", jwt_secret="k" * 48)
    with TestClient(app) as client:
        login = client.post(
            "/v1/auth/login",
            json={"email": "old@example.test", "password": "correct-horse-battery"},
        )
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        listed = client.get("/v1/bets", headers=headers)
        assert listed.status_code == 200, listed.text
        by_book = {b["sportsbook"]: b for b in listed.json()}
        assert set(by_book) == {"Northline", "Harbor", "Rounded"}
        assert by_book["Rounded"]["stake"] == 0 and by_book["Rounded"]["potential_payout"] == 0
        assert by_book["Rounded"]["combined_price"]["american"] == -100000000
        assert client.get("/v1/bets/summary", headers=headers).status_code == 200
        assert client.get("/v1/bets/analytics", headers=headers).status_code == 200
        export = client.get("/v1/me/export", headers=headers)
        assert export.status_code == 200 and len(export.json()["bets"]) == 3

        body = {
            "bet_type": "straight",
            "stake": 10,
            "sportsbook": "Northline",
            "legs": [{"selection": "x", "market": "moneyline", "odds": -110}],
            "client_request_id": "after-upgrade-0001",
        }
        first = client.post("/v1/bets", json=body, headers=headers)
        again = client.post("/v1/bets", json=body, headers=headers)
        assert (first.status_code, again.status_code) == (201, 200), (first.text, again.text)
        assert again.json() == first.json()
        assert len(client.get("/v1/bets", headers=headers).json()) == 4
        # The old bet that could not be stored today can still be corrected or deleted.
        assert (
            client.delete(f"/v1/bets/{by_book['Rounded']['id']}", headers=headers).status_code
            == 204
        )
        assert client.get("/health").json()["database"] == "ok"
    app.state.engine.dispose()

    # Downgrade removes only what 0006 added; every bet, old and new, is kept.
    command.downgrade(config, "0005")
    engine = make_engine(url)
    assert "client_request_id" not in {c["name"] for c in inspect(engine).get_columns("bets")}
    assert "uq_bets_user_client_request" not in {
        index["name"] for index in inspect(engine).get_indexes("bets")
    }
    assert set(inspect(engine).get_table_names()) >= TABLES_0005
    with engine.connect() as connection:
        books = connection.execute(text("SELECT sportsbook FROM bets ORDER BY sportsbook"))
        assert list(books.scalars()) == ["Harbor", "Northline", "Northline"]
        assert connection.execute(text("SELECT count(*) FROM bet_legs")).scalar() == 3
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0005"
        )
    engine.dispose()

    # Up again: the column comes back empty and the models and migrations agree.
    command.upgrade(config, "head")
    engine = make_engine(url)
    with engine.connect() as connection:
        with_id = connection.execute(
            text("SELECT count(*) FROM bets WHERE client_request_id IS NOT NULL")
        ).scalar()
        assert with_id == 0
        assert connection.execute(text("SELECT count(*) FROM bets")).scalar() == 3
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
        assert diff == [], diff
    command.check(config)
    engine.dispose()
    command.downgrade(config, "base")
    engine = make_engine(url)
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    engine.dispose()
    if backend != "sqlite":
        _reset_external_database(url)


SNAPSHOT_COLUMNS = {"target_text_snapshot", "target_summary_snapshot"}


@pytest.mark.parametrize("backend", _database_urls())
def test_upgrade_from_0006_with_existing_data_then_downgrade(
    backend: str, tmp_path: Path, make_app: AppFactory
) -> None:
    if backend == "sqlite":
        url = f"sqlite:///{tmp_path / 'upgrade_0007.db'}"
    else:
        url = backend
        _reset_external_database(url)
    config = alembic_config(url)
    command.upgrade(config, "0006")
    engine = make_engine(url)
    assert "community_reserved_handles" not in inspect(engine).get_table_names()
    columns = {c["name"] for c in inspect(engine).get_columns("community_reports")}
    assert not SNAPSHOT_COLUMNS & columns

    # Rows written by the 0006 release: two members, a reported pick and an open report
    # on it, and a profile of the first member.
    stamp = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)
    at = bindparam("at", type_=DateTime(timezone=True))
    with engine.begin() as connection:
        for user_id, email in (("u" * 32, "old@example.test"), ("v" * 32, "other@example.test")):
            connection.execute(
                text(
                    "INSERT INTO users (id, email, password_hash, display_name, role, "
                    "is_active, age_confirmed_at, created_at, token_version, plan, status, "
                    "search_key) VALUES (:id, :email, :hash, 'Old', 'user', :active, :at, "
                    ":at, 0, 'free', 'active', :key)"
                ).bindparams(at),
                {
                    "id": user_id,
                    "email": email,
                    "hash": hash_password("correct-horse-battery"),
                    "active": True,
                    "at": stamp,
                    "key": f"{email}\nold",
                },
            )
        connection.execute(
            text(
                "INSERT INTO community_profiles (user_id, handle, bio, is_public, "
                "moderation_status, created_at, updated_at) VALUES (:user, 'old_timer', "
                "'Totals.', :public, 'visible', :at, :at)"
            ).bindparams(at),
            {"user": "u" * 32, "public": True, "at": stamp},
        )
        connection.execute(
            text(
                "INSERT INTO community_reports (id, reporter_id, target_type, target_id, "
                "target_user_id, reason, details, status, created_at) VALUES (:id, :reporter, "
                "'profile', 'old_timer', :author, 'spam', 'old report', 'open', :at)"
            ).bindparams(at),
            {"id": "r" * 32, "reporter": "v" * 32, "author": "u" * 32, "at": stamp},
        )

    command.upgrade(config, "head")
    engine = make_engine(url)
    columns = {c["name"]: c for c in inspect(engine).get_columns("community_reports")}
    assert all(columns[name]["nullable"] is True for name in SNAPSHOT_COLUMNS)
    assert "community_reserved_handles" in inspect(engine).get_table_names()
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
        assert diff == [], diff
        # The old report is kept as it was: nothing was copied then, nothing is invented.
        row = connection.execute(
            text(
                "SELECT id, details, status, target_text_snapshot, target_summary_snapshot "
                "FROM community_reports"
            )
        ).one()
        assert tuple(row) == ("r" * 32, "old report", "open", None, None)
        assert (
            connection.execute(text("SELECT count(*) FROM community_reserved_handles")).scalar()
            == 0
        )
    command.check(config)  # `alembic check`: models and migrations agree
    engine.dispose()

    # The current app on the upgraded data: the old report shows no copy, and the new
    # features work for the old accounts.
    app = make_app(
        database_url=url,
        env="production",
        jwt_secret="k" * 48,
        admin_emails="boss@example.test",
        community_grade_min_seconds=0,
    )
    with TestClient(app) as client:
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
        mark_email_verified(client, "boss@example.test")  # the admin role needs it
        turned_on = client.put(
            "/v1/admin/flags/community", json={"enabled": True}, headers=admin_headers
        )
        assert turned_on.status_code == 200, turned_on.text
        (old,) = client.get("/v1/admin/community/reports", headers=admin_headers).json()["items"]
        assert (old["id"], old["target_text"], old["reported_text"]) == ("r" * 32, "Totals.", None)
        assert old["target_changed_since_report"] is False and old["author_edit"] is False

        def login(email: str) -> dict[str, str]:
            response = client.post(
                "/v1/auth/login", json={"email": email, "password": "correct-horse-battery"}
            )
            assert response.status_code == 200, response.text
            return {"Authorization": f"Bearer {response.json()['access_token']}"}

        old_headers, other_headers = login("old@example.test"), login("other@example.test")
        profile = client.put(
            "/v1/community/profile",
            json={"handle": "other_one", "bio": "Spreads.", "is_public": True},
            headers=other_headers,
        )
        assert profile.status_code == 201, profile.text
        reported = client.post(
            "/v1/community/reports",
            json={"target_type": "profile", "target_id": "other_one", "reason": "other"},
            headers=old_headers,
        )
        assert reported.status_code == 201, reported.text
        items = client.get("/v1/admin/community/reports", headers=admin_headers).json()["items"]
        assert [i["reported_text"] for i in items] == [None, "Spreads."]

        # Suspended, then deleted: the handle is kept and nobody can take it.
        suspended = client.post(
            f"/v1/admin/users/{'u' * 32}/suspend", json={"reason": "abusive"}, headers=admin_headers
        )
        assert suspended.status_code == 200, suspended.text
        assert client.delete("/v1/me", headers=old_headers).status_code == 204
        taken = client.put(
            "/v1/community/profile",
            json={"handle": "old_timer", "is_public": True},
            headers=other_headers,
        )
        assert taken.status_code == 409 and taken.json()["error"]["code"] == "handle_taken"
        assert client.get("/health").json()["database"] == "ok"
    app.state.engine.dispose()

    # Downgrade removes only what 0007 added; the reports and profiles are kept.
    command.downgrade(config, "0006")
    engine = make_engine(url)
    assert "community_reserved_handles" not in inspect(engine).get_table_names()
    columns = {c["name"] for c in inspect(engine).get_columns("community_reports")}
    assert not SNAPSHOT_COLUMNS & columns
    with engine.connect() as connection:
        # The old account's report went with it; the other member's profile is still there.
        handles = connection.execute(text("SELECT handle FROM community_profiles")).scalars()
        assert list(handles) == ["other_one"]
        assert connection.execute(text("SELECT count(*) FROM community_reports")).scalar() == 0
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0006"
        )
    engine.dispose()

    # Up again: an empty table and empty columns, and the models and migrations agree.
    command.upgrade(config, "head")
    engine = make_engine(url)
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT count(*) FROM community_reserved_handles")).scalar()
            == 0
        )
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
        assert diff == [], diff
    command.check(config)
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


def test_seed_adds_no_community_data_while_the_flag_is_off(session_factory) -> None:  # type: ignore[no-untyped-def]
    provider = SyntheticProvider(seed=20260101, clock=lambda: NOW)
    with session_factory() as db:
        seed_demo(db, "demo-password-123", NOW, provider=provider)
        assert db.scalar(select(func.count()).select_from(CommunityProfile)) == 0
        assert db.scalar(select(func.count()).select_from(CommunityPick)) == 0
        assert db.scalar(select(func.count()).select_from(FeatureFlag)) == 0
        assert [u.email for u in db.scalars(select(User))] == [DEMO_EMAIL]


def test_seed_with_community_creates_fictional_profiles_and_is_idempotent(
    session_factory,  # type: ignore[no-untyped-def]
    make_settings,  # type: ignore[no-untyped-def]
) -> None:
    provider = SyntheticProvider(seed=20260101, clock=lambda: NOW)
    settings = make_settings()

    def snapshot() -> dict[str, Any]:
        with session_factory() as db:
            return {
                "users": db.scalar(select(func.count()).select_from(User)),
                "profiles": db.scalar(select(func.count()).select_from(CommunityProfile)),
                "picks": db.scalar(select(func.count()).select_from(CommunityPick)),
                "comments": db.scalar(select(func.count()).select_from(CommunityComment)),
                "follows": db.scalar(select(func.count()).select_from(CommunityFollow)),
                "likes": db.scalar(select(func.count()).select_from(CommunityLike)),
                "notifications": db.scalar(select(func.count()).select_from(Notification)),
            }

    with session_factory() as db:
        seed_demo(
            db, "demo-password-123", NOW, provider=provider, settings=settings, with_community=True
        )
        # --with-community turns both flags on in this database.
        assert flags_service.flag_states(db, settings)["community"] is True
        assert flags_service.flag_states(db, settings)["community_leaderboard"] is True
    first = snapshot()
    assert first["profiles"] == len(FICTIONAL_PROFILES) + 1 == 7
    assert first["users"] == 7 and first["comments"] >= 3
    assert first["follows"] >= 12 and first["likes"] >= 10

    with session_factory() as db:
        profiles = {p.handle: p for p in db.scalars(select(CommunityProfile))}
        assert set(profiles) == {handle for handle, _, _ in FICTIONAL_PROFILES} | {"demo_bettor"}
        demo = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        assert profiles["demo_bettor"].user_id == demo.id and profiles["demo_bettor"].is_public
        # Obviously fictional: the handle says so and so does the bio.
        for handle, profile in profiles.items():
            assert profile.is_public and profile.moderation_status == "visible"
            if handle == "demo_bettor":
                assert "Demo account" in profile.bio and "Fictional" in profile.bio
                continue
            assert handle.split("_")[0] in {
                "fictional",
                "sample",
                "madeup",
                "placeholder",
                "notreal",
                "example",
            }
            assert "Fictional demo profile" in profile.bio and "Not a real person" in profile.bio
        emails = [u.email for u in db.scalars(select(User)) if u.email != DEMO_EMAIL]
        assert all(email.endswith("@community.oddvex.test") for email in emails)
        picks = list(db.scalars(select(CommunityPick)))
        by_user: dict[str, list[CommunityPick]] = {}
        for pick in picks:
            by_user.setdefault(pick.user_id, []).append(pick)
        assert len(by_user) == 7
        for owned in by_user.values():
            # A spread of graded and upcoming picks for every profile.
            assert any(p.status == "graded" for p in owned)
            assert any(p.status == "pending" and p.event_start_time > NOW for p in owned)
        graded = [p for p in picks if p.status == "graded"]
        assert {p.result for p in graded} == {"won", "lost", "push"} or {
            p.result for p in graded
        } == {"won", "lost"}
        assert {p.market for p in picks} == {"moneyline", "spread", "total"}
        for pick in graded:
            # Posted before the event, priced, and graded by the grading function from the
            # event's real (synthetic) final score.
            assert pick.posted_at < pick.event_start_time and pick.price_decimal > 1
            event = provider.get_event(pick.event_id)
            assert event is not None and event.status == "final" and event.score is not None
            assert (pick.home_score, pick.away_score) == (event.score.home, event.score.away)
            assert pick.result == grade_leg(
                pick.market,
                pick.outcome_key,
                pick.line,
                event.score.home,
                event.score.away,
                three_way=event.league == "soccer",
            )
        assert not [p for p in picks if p.status == "pending" and p.event_start_time <= NOW]
        # Two profiles have enough graded picks for the leaderboard to rank them.
        ranked = [
            owned for owned in by_user.values() if sum(p.status == "graded" for p in owned) >= 30
        ]
        assert len(ranked) == 2
        # Every text in the seed passes the content rules a user's text would have to pass.
        texts = [p.analysis for p in picks] + [p.bio for p in profiles.values()]
        texts += [c.body for c in db.scalars(select(CommunityComment))]
        assert all(check_text(text) is None for text in texts)
        names = " ".join(p.event_label + p.selection for p in picks)
        assert not any(name in names for name in REAL_NAMES)

    # Running it again creates nothing new, with or without the option.
    with session_factory() as db:
        seed_demo(
            db, "demo-password-123", NOW, provider=provider, settings=settings, with_community=True
        )
    assert snapshot() == first
    with session_factory() as db:
        seed_demo(db, "demo-password-123", NOW, provider=provider, settings=settings)
    assert snapshot() == first


def test_seeded_community_is_served_by_the_api(
    make_app: AppFactory, provider: SyntheticProvider
) -> None:
    app = make_app(community_grade_min_seconds=0)
    Base.metadata.create_all(app.state.engine)
    with app.state.session_factory() as db:
        seed_demo(
            db,
            app.state.settings.demo_password,
            provider.now(),
            provider=provider,
            settings=app.state.settings,
            with_community=True,
        )
    with TestClient(app) as client:
        login = client.post(
            "/v1/auth/login",
            json={"email": DEMO_EMAIL, "password": app.state.settings.demo_password},
        )
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        profile = client.get("/v1/community/profile", headers=headers).json()
        assert (profile["handle"], profile["is_public"], profile["can_post"]) == (
            "demo_bettor",
            True,
            True,
        )
        assert profile["following_count"] == 3 and profile["record"]["picks"] >= 4
        assert profile["record"]["sample_note"]  # a handful of picks: the note says so
        following = client.get("/v1/community/feed", headers=headers).json()["items"]
        everyone = client.get(
            "/v1/community/feed", params={"scope": "everyone", "limit": 100}, headers=headers
        ).json()["items"]
        assert following and len(everyone) == 100
        assert {p["status"] for p in everyone} >= {"pending", "graded"}
        board = client.get("/v1/community/leaderboard", headers=headers).json()
        assert [row["handle"] for row in board["items"]] and len(board["items"]) == 2
        assert {row["handle"] for row in board["items"]} == {"fictional_fox", "sample_sam"}
        assert all(row["record"]["picks"] >= 30 for row in board["items"])
        assert "example.test" not in str(everyone) and "oddvex.test" not in str(everyone)
    app.state.engine.dispose()


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
        assert db.scalar(select(func.count()).select_from(CommunityProfile)) == 0
    assert "Community flag is off" in third.stdout

    # --with-community turns the flags on in that database and adds the fictional profiles.
    for _ in range(2):  # idempotent
        fourth = subprocess.run(
            [sys.executable, script, "--with-community"],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert fourth.returncode == 0, fourth.stderr
        assert "Community: 7 profile(s)" in fourth.stdout and "demo_bettor" in fourth.stdout
    with make_session_factory(engine)() as db:
        assert db.scalar(select(func.count()).select_from(CommunityProfile)) == 7
        picks = db.scalar(select(func.count()).select_from(CommunityPick))
        enabled = {f.key for f in db.scalars(select(FeatureFlag)) if f.enabled}
        assert enabled == {"community", "community_leaderboard"}
    # From then on the plain script keeps the community data up to date as well.
    fifth = subprocess.run(
        [sys.executable, script], cwd=tmp_path, env=env, capture_output=True, text=True, check=False
    )
    assert fifth.returncode == 0 and "Community: 7 profile(s)" in fifth.stdout
    with make_session_factory(engine)() as db:
        assert db.scalar(select(func.count()).select_from(CommunityPick)) == picks
    # The grading script runs against the same database and finds nothing left to grade.
    graded = subprocess.run(
        [sys.executable, str(API_ROOT / "scripts" / "grade_picks.py")],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert graded.returncode == 0, graded.stderr
    assert "0 graded, 0 voided" in graded.stdout
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


def test_seed_admin_and_an_account_that_already_exists(
    session_factory,
    make_settings,  # type: ignore[no-untyped-def]
) -> None:
    """The seed keeps an existing account's password. In a demo database it still makes
    that account the demo administrator; in production the account may be anybody's, so
    an unverified one is left exactly as it is."""
    listed = make_settings(admin_emails="admin@oddvex.test")
    production = make_settings(
        admin_emails="admin@oddvex.test", env="production", jwt_secret="k" * 48
    )
    with session_factory() as db:
        squatter = User(
            email=DEMO_ADMIN_EMAIL,
            password_hash=hash_password("somebody-elses-password"),
            display_name="Somebody",
            age_confirmed_at=NOW,
        )
        db.add(squatter)
        db.commit()
        first_hash = squatter.password_hash

        seed_demo(db, "pw-one-1234", NOW, settings=production)
        db.refresh(squatter)
        assert (squatter.role, squatter.email_verified_at) == ("user", None)
        assert squatter.password_hash == first_hash

        # Outside production it is the demo administrator, verified by the seed.
        seed_demo(db, "pw-one-1234", NOW, settings=listed)
        db.refresh(squatter)
        assert (squatter.role, squatter.email_verified_at) == ("admin", NOW)
        assert squatter.password_hash == first_hash
        # Verified once, production keeps it as it is.
        seed_demo(db, "pw-one-1234", NOW, settings=production)
        db.refresh(squatter)
        assert squatter.role == "admin"


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
    ("POST", "/v1/admin/users/{user_id}/export"): "admin_export_user",
    ("POST", "/v1/admin/users/{user_id}/delete"): "admin_delete_user",
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
    ("POST", "/v1/admin/community/restore"): "admin_restore_content",
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
