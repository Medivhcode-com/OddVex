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
from sqlalchemy import inspect, select

from oddvex_api.db import Base, Bet, User, make_engine, make_session_factory
from oddvex_api.seed import DEMO_BET_COUNT, DEMO_EMAIL, seed_demo

from .conftest import AppFactory
from .test_provider_synthetic import REAL_NAMES

API_ROOT = Path(__file__).resolve().parents[1]
TABLES = {"users", "bets", "bet_legs", "sync_connections", "sync_import_runs", "audit_log"}
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


def test_demo_user_can_log_in_and_see_a_summary(make_app: AppFactory) -> None:
    app = make_app(auto_seed_demo=True, demo_password="demo-password-123")
    with TestClient(app) as client:
        login = client.post(
            "/v1/auth/login", json={"email": DEMO_EMAIL, "password": "demo-password-123"}
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert len(client.get("/v1/bets", headers=headers).json()) == 40
        summary = client.get("/v1/bets/summary", headers=headers).json()
        assert summary["totals"]["settled_count"] >= 28
        assert summary["totals"]["pending_count"] >= 7
        assert summary["totals"]["avg_clv"] is not None
        assert len(summary["timeline"]) >= 15
        assert len(summary["by_sport"]) >= 4


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
    assert "40 bet(s) created" in first.stdout
    second = subprocess.run(
        [sys.executable, script], cwd=tmp_path, env=env, capture_output=True, text=True, check=False
    )
    assert "0 bet(s) created" in second.stdout


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
