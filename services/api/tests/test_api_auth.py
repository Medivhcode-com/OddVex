from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from oddvex_api.auth.security import create_access_token, hash_password, verify_password
from oddvex_api.config import DEV_JWT_SECRET
from oddvex_api.db import AuditLog, Bet, SyncConnection, SyncImportRun, User

from .conftest import PASSWORD, AppFactory, register, verify_email

VALID = {
    "email": "ada@example.test",
    "password": PASSWORD,
    "display_name": "Ada",
    "age_confirmed": True,
}


def test_register_returns_a_token_and_user(client: TestClient) -> None:
    response = client.post("/v1/auth/register", json={**VALID, "email": "  Ada@Example.TEST "})
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"access_token", "token_type", "expires_in", "user"}
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600
    assert body["user"]["email"] == "ada@example.test"
    assert body["user"]["display_name"] == "Ada"
    assert body["user"]["role"] == "user"
    assert "password" not in str(body).lower()
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"age_confirmed": False}, "age_confirmed"),
        ({"password": "short-pw9"}, "password"),  # 9 characters
        ({"email": "not-an-email"}, "email"),
        ({"email": "a@b"}, "email"),
        ({"display_name": "   "}, "display_name"),
        ({"display_name": ""}, "display_name"),
    ],
)
def test_register_validation(client: TestClient, change: dict, field: str) -> None:
    response = client.post("/v1/auth/register", json={**VALID, **change})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert any(field in detail["loc"] for detail in error["details"])


@pytest.mark.parametrize("missing", ["email", "password", "display_name", "age_confirmed"])
def test_register_requires_every_field(client: TestClient, missing: str) -> None:
    body = {k: v for k, v in VALID.items() if k != missing}
    assert client.post("/v1/auth/register", json=body).status_code == 422


def test_ten_character_password_is_accepted(client: TestClient) -> None:
    assert (
        client.post("/v1/auth/register", json={**VALID, "password": "abcdefghij"}).status_code
        == 201
    )


def test_duplicate_email_is_a_conflict(client: TestClient) -> None:
    register(client)
    response = client.post("/v1/auth/register", json={**VALID, "email": "ADA@example.test"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


def test_login(client: TestClient) -> None:
    register(client)
    response = client.post(
        "/v1/auth/login", json={"email": "ADA@example.test", "password": PASSWORD}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    me = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "ada@example.test"


def test_login_failures_do_not_reveal_which_part_was_wrong(client: TestClient) -> None:
    register(client)
    wrong_password = client.post(
        "/v1/auth/login", json={"email": "ada@example.test", "password": "nope-nope-nope"}
    )
    unknown_user = client.post(
        "/v1/auth/login", json={"email": "nobody@example.test", "password": PASSWORD}
    )
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()
    assert wrong_password.json()["error"]["code"] == "invalid_credentials"


def test_me_requires_a_valid_token(client: TestClient, app) -> None:  # type: ignore[no-untyped-def]
    assert client.get("/v1/me").status_code == 401
    assert client.get("/v1/me").json()["error"]["code"] == "not_authenticated"
    assert client.get("/v1/me").headers["www-authenticate"] == "Bearer"
    for bad in ("garbage", "a.b.c"):
        response = client.get("/v1/me", headers={"Authorization": f"Bearer {bad}"})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_token"
    user_id = register(client)["user"]["id"]
    expired, _ = create_access_token(
        user_id, "user", DEV_JWT_SECRET, 60, now=datetime.now(UTC) - timedelta(hours=2)
    )
    assert client.get("/v1/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    forged, _ = create_access_token(user_id, "admin", "some-other-secret-some-other-secret", 60)
    assert client.get("/v1/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    unsigned = jwt.encode({"sub": user_id, "exp": 9999999999, "iat": 1}, "", algorithm="none")
    assert client.get("/v1/me", headers={"Authorization": f"Bearer {unsigned}"}).status_code == 401
    ghost, _ = create_access_token("no-such-user", "user", DEV_JWT_SECRET, 60)
    assert client.get("/v1/me", headers={"Authorization": f"Bearer {ghost}"}).status_code == 401


def test_passwords_are_hashed_with_argon2(client: TestClient, app) -> None:  # type: ignore[no-untyped-def]
    register(client)
    with app.state.session_factory() as db:
        stored = db.scalar(select(User.password_hash))
    assert stored.startswith("$argon2id$")
    assert PASSWORD not in stored
    assert verify_password(PASSWORD, stored)
    assert not verify_password("wrong", stored)
    assert not verify_password(PASSWORD, None)
    assert not verify_password(PASSWORD, "not-a-hash")
    assert hash_password(PASSWORD) != hash_password(PASSWORD)  # salted


def test_delete_account_removes_bets_and_sync_data(
    client: TestClient, app, headers, other_headers
) -> None:  # type: ignore[no-untyped-def]
    bet = {
        "bet_type": "straight",
        "stake": 10,
        "sportsbook": "Northline",
        "legs": [{"selection": "Tides ML", "market": "moneyline", "odds": -110}],
    }
    assert client.post("/v1/bets", json=bet, headers=headers).status_code == 201
    assert client.post("/v1/bets", json=bet, headers=other_headers).status_code == 201
    connection = client.post(
        "/v1/sync/connections", json={"provider": "mock"}, headers=headers
    ).json()
    assert (
        client.post(f"/v1/sync/connections/{connection['id']}/sync", headers=headers).status_code
        == 200
    )
    user_id = client.get("/v1/me", headers=headers).json()["id"]

    response = client.delete("/v1/me", headers=headers)
    assert response.status_code == 204
    assert response.content == b""

    assert client.get("/v1/me", headers=headers).status_code == 401
    login = client.post("/v1/auth/login", json={"email": "ada@example.test", "password": PASSWORD})
    assert login.status_code == 401
    with app.state.session_factory() as db:
        assert db.scalar(select(User).where(User.id == user_id)) is None
        assert list(db.scalars(select(Bet).where(Bet.user_id == user_id))) == []
        assert (
            list(db.scalars(select(SyncConnection).where(SyncConnection.user_id == user_id))) == []
        )
        assert list(db.scalars(select(SyncImportRun))) == []
        assert len(list(db.scalars(select(Bet)))) == 1  # the other user's bet is untouched
        audit = db.scalar(select(AuditLog).where(AuditLog.action == "account.deleted"))
        assert audit is not None and audit.user_id == user_id
        assert "example.test" not in str(audit.details)
    assert len(client.get("/v1/bets", headers=other_headers).json()) == 1
    # The email can be registered again.
    assert client.post("/v1/auth/register", json=VALID).status_code == 201


def test_auth_events_are_audited(client: TestClient, app) -> None:  # type: ignore[no-untyped-def]
    register(client)
    client.post("/v1/auth/login", json={"email": "ada@example.test", "password": PASSWORD})
    client.post(
        "/v1/auth/login", json={"email": "ada@example.test", "password": "wrong-wrong-wrong"}
    )
    with app.state.session_factory() as db:
        actions = [row.action for row in db.scalars(select(AuditLog).order_by(AuditLog.created_at))]
        rows = list(db.scalars(select(AuditLog)))
    assert actions == ["auth.register", "auth.login", "auth.login_failed"]
    assert all(row.request_id for row in rows)
    assert all(PASSWORD not in str(row.details) for row in rows)


def test_admin_role_comes_from_configuration(make_app: AppFactory) -> None:
    app = make_app(admin_emails="boss@example.test, other@example.test")
    with TestClient(app) as client:
        # ``email_flows`` is on outside production, so a listed address is an ordinary
        # user until it is confirmed: registering it first proves nothing.
        boss = register(client, "boss@example.test")
        assert boss["user"]["role"] == "user"
        headers = {"Authorization": f"Bearer {boss['access_token']}"}
        assert client.get("/v1/admin/overview", headers=headers).status_code == 403
        verify_email(client, "boss@example.test")
        assert client.get("/v1/me", headers=headers).json()["role"] == "admin"
        assert client.get("/v1/admin/overview", headers=headers).status_code == 200
        assert register(client, "ada@example.test")["user"]["role"] == "user"
