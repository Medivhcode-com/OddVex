from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from oddvex_api.auth import security
from oddvex_api.config import Settings
from oddvex_api.db import Base, User, make_engine, utcnow
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


@pytest.fixture(autouse=True)
def _default_password_hash_limits() -> Iterator[None]:
    """The hashing limiter belongs to the process (``auth/security.py``). An app built with
    other limits would leave them in force for the tests that follow, so put the defaults back."""
    yield
    security.configure_password_hashing()


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
    """A client on an app where ``ADMIN_EMAIL`` is listed as an administrator address."""
    with TestClient(make_app(admin_emails=ADMIN_EMAIL)) as test_client:
        yield test_client


def verify_email(client: TestClient, email: str) -> None:
    """Confirm ``email`` with the link from the development outbox."""
    latest = client.get(
        "/v1/dev/email-outbox/latest", params={"to": email, "template": "verify_email"}
    )
    assert latest.status_code == 200, latest.text
    confirmed = client.post("/v1/auth/verify-email/confirm", json={"token": latest.json()["token"]})
    assert confirmed.status_code == 200, confirmed.text


def mark_email_verified(client: TestClient, email: str) -> None:
    """Mark ``email`` as verified directly in the database: what an operator step does
    where no confirmation link can be followed (production, or ``email_flows`` off)."""
    with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
        user = db.scalars(select(User).where(User.email == email)).one()
        if user.email_verified_at is None:
            user.email_verified_at = utcnow()
        db.commit()


def admin_headers(client: TestClient, email: str = ADMIN_EMAIL) -> dict[str, str]:
    """Register a listed address and verify it: the admin role is only ever given to a
    verified address. The confirmation link from the development outbox is used where
    there is one; otherwise the address is marked verified in the database."""
    account = register(client, email)
    latest = client.get(
        "/v1/dev/email-outbox/latest", params={"to": email, "template": "verify_email"}
    )
    if latest.status_code == 200:
        verify_email(client, email)
    else:
        mark_email_verified(client, email)
    return {"Authorization": f"Bearer {account['access_token']}"}


def set_flag(client: TestClient, admin: dict[str, str], key: str, enabled: bool) -> None:
    response = client.put(f"/v1/admin/flags/{key}", json={"enabled": enabled}, headers=admin)
    assert response.status_code == 200, response.text
