from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from oddvex_api.config import Settings
from oddvex_api.db import Base, make_engine
from oddvex_api.main import create_app
from oddvex_api.providers import SyntheticProvider

#: Chosen so the synthetic schedule has live NBA + NFL games and finals earlier in the day.
FROZEN_NOW = datetime(2026, 3, 14, 19, 30, tzinfo=UTC)
PASSWORD = "correct-horse-battery"

SettingsFactory = Callable[..., Settings]
AppFactory = Callable[..., FastAPI]


#: Optional: run the API tests against another database (e.g. PostgreSQL). The database is
#: wiped before each test, so point this at a throwaway database only.
EXTERNAL_DATABASE_URL = os.environ.get("ODDVEX_TEST_DATABASE_URL")


def _reset_external_database(url: str) -> None:
    engine = make_engine(url)
    with engine.begin() as connection:
        Base.metadata.drop_all(connection)
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    engine.dispose()


@pytest.fixture
def make_settings(tmp_path: Path) -> SettingsFactory:
    if EXTERNAL_DATABASE_URL:
        _reset_external_database(EXTERNAL_DATABASE_URL)

    def factory(**overrides: Any) -> Settings:
        values: dict[str, Any] = {
            "env": "test",
            "database_url": EXTERNAL_DATABASE_URL or f"sqlite:///{tmp_path / 'test.db'}",
            "rate_limit_enabled": False,
            "log_level": "WARNING",
        }
        values.update(overrides)
        return Settings(_env_file=None, **values)

    return factory


@pytest.fixture
def provider() -> SyntheticProvider:
    return SyntheticProvider(seed=20260101, clock=lambda: FROZEN_NOW)


@pytest.fixture
def make_app(make_settings: SettingsFactory, provider: SyntheticProvider) -> AppFactory:
    def factory(**overrides: Any) -> FastAPI:
        custom_provider = overrides.pop("provider", provider)
        return create_app(make_settings(**overrides), provider=custom_provider)

    return factory


@pytest.fixture
def app(make_app: AppFactory) -> FastAPI:
    return make_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def register(client: TestClient, email: str = "ada@example.test", **extra: Any) -> dict[str, Any]:
    body = {
        "email": email,
        "password": PASSWORD,
        "display_name": "Ada",
        "age_confirmed": True,
        **extra,
    }
    response = client.post("/v1/auth/register", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def auth_headers(client: TestClient, email: str = "ada@example.test") -> dict[str, str]:
    return {"Authorization": f"Bearer {register(client, email)['access_token']}"}


@pytest.fixture
def headers(client: TestClient) -> dict[str, str]:
    return auth_headers(client)


@pytest.fixture
def other_headers(client: TestClient) -> dict[str, str]:
    return auth_headers(client, "grace@example.test")


ADMIN_EMAIL = "boss@example.test"


@pytest.fixture
def admin_client(make_app: AppFactory) -> Iterator[TestClient]:
    """A client on an app where ``ADMIN_EMAIL`` registers as an administrator."""
    with TestClient(make_app(admin_emails=ADMIN_EMAIL)) as test_client:
        yield test_client


def admin_headers(client: TestClient) -> dict[str, str]:
    return auth_headers(client, ADMIN_EMAIL)


def set_flag(client: TestClient, admin: dict[str, str], key: str, enabled: bool) -> None:
    response = client.put(f"/v1/admin/flags/{key}", json={"enabled": enabled}, headers=admin)
    assert response.status_code == 200, response.text
