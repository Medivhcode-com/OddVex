"""Account data export and password change."""

from __future__ import annotations

import json
from typing import Any

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select

from oddvex_api.config import DEV_JWT_SECRET
from oddvex_api.db import AuditLog, User

from .conftest import PASSWORD, AppFactory, auth_headers, register
from .test_platform import assert_envelope

Headers = dict[str, str]
NEW_PASSWORD = "an-entirely-new-passphrase"


def _bet(**overrides: Any) -> dict[str, Any]:
    return {
        "bet_type": "straight",
        "stake": 25,
        "sportsbook": "Northline",
        "legs": [{"selection": "Harbor City Tides ML", "market": "moneyline", "odds": -110}],
        **overrides,
    }


def _populate(client: TestClient, headers: Headers, note: str) -> dict[str, Any]:
    """Give a user one of everything. Returns the ids created."""
    bet = client.post("/v1/bets", json=_bet(notes=note), headers=headers).json()
    settled = client.post("/v1/bets", json=_bet(stake=10), headers=headers).json()
    client.post(f"/v1/bets/{settled['id']}/settle", json={"result": "won"}, headers=headers)
    team_id = client.get("/v1/events").json()[0]["home_team"]["id"]
    item = client.post(
        "/v1/watchlist", json={"kind": "team", "ref_id": team_id}, headers=headers
    ).json()
    connection = client.post(
        "/v1/sync/connections", json={"provider": "mock"}, headers=headers
    ).json()
    run = client.post(f"/v1/sync/connections/{connection['id']}/sync", headers=headers).json()
    return {
        "bet": bet["id"],
        "settled": settled["id"],
        "item": item["id"],
        "connection": connection["id"],
        "run": run["id"],
    }


# --------------------------------------------------------------------- export
def test_export_contains_everything_of_mine_and_nothing_else(client: TestClient, app) -> None:  # type: ignore[no-untyped-def]
    ada = register(client, "ada@example.test")
    grace = register(client, "grace@example.test")
    ada_headers = {"Authorization": f"Bearer {ada['access_token']}"}
    grace_headers = {"Authorization": f"Bearer {grace['access_token']}"}
    mine = _populate(client, ada_headers, "ada-private-note")
    theirs = _populate(client, grace_headers, "grace-private-note")

    response = client.get("/v1/me/export", headers=ada_headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert set(body) == {
        "exported_at",
        "format_version",
        "user",
        "bets",
        "watchlist",
        "sync_connections",
        "sync_runs",
        "audit_log",
        # Added with the alerts milestone; older clients ignore them.
        "alerts",
        "notifications",
        "notification_preferences",
        "stake_reminder",
    }
    assert body["format_version"] == 1
    assert body["user"] == ada["user"]
    assert set(body["user"]) == {
        "id",
        "email",
        "display_name",
        "role",
        "age_confirmed_at",
        "created_at",
        "plan",
        "email_verified",
    }
    assert body["user"]["plan"] == "free" and body["user"]["email_verified"] is False

    # Bets: the two manual ones plus what the mock import brought in, in full BetOut form.
    listed = client.get("/v1/bets", headers=ada_headers).json()
    assert {b["id"] for b in body["bets"]} == {b["id"] for b in listed}
    assert {mine["bet"], mine["settled"]} <= {b["id"] for b in body["bets"]}
    by_id = {b["id"]: b for b in body["bets"]}
    assert by_id[mine["bet"]] == client.get(f"/v1/bets/{mine['bet']}", headers=ada_headers).json()
    assert by_id[mine["bet"]]["notes"] == "ada-private-note"
    assert by_id[mine["settled"]]["result"] == "won" and by_id[mine["settled"]]["legs"]
    assert any(b["source"] == "sync" for b in body["bets"])

    assert [i["id"] for i in body["watchlist"]] == [mine["item"]]
    assert body["watchlist"][0]["team"] is not None
    assert [c["id"] for c in body["sync_connections"]] == [mine["connection"]]
    assert [r["id"] for r in body["sync_runs"]] == [mine["run"]]
    assert body["sync_runs"][0]["connection_id"] == mine["connection"]

    actions = [entry["action"] for entry in body["audit_log"]]
    assert actions[0] == "auth.register" and actions[-1] == "account.export"
    assert {"bet.create", "bet.settle", "watchlist.add", "sync.connect", "sync.import"} <= set(
        actions
    )
    assert set(body["audit_log"][0]) == {
        "id",
        "created_at",
        "action",
        "entity_type",
        "entity_id",
        "ip",
        "request_id",
        "details",
    }

    # Nothing secret and nothing that belongs to the other user.
    text = json.dumps(body).lower()
    assert "password" not in text and "argon2" not in text and "hash" not in text
    with app.state.session_factory() as db:
        hashes = list(db.scalars(select(User.password_hash)))
        other_audit_ids = set(
            db.scalars(select(AuditLog.id).where(AuditLog.user_id == grace["user"]["id"]))
        )
        own_audit_ids = set(
            db.scalars(select(AuditLog.id).where(AuditLog.user_id == ada["user"]["id"]))
        )
    assert len(hashes) == 2 and all(h.lower() not in text for h in hashes)
    assert "grace" not in text
    for foreign in (grace["user"]["id"], *theirs.values()):
        assert foreign not in text
    exported_audit_ids = {entry["id"] for entry in body["audit_log"]}
    assert exported_audit_ids == own_audit_ids
    assert not exported_audit_ids & other_audit_ids

    # The other user's export is just as separate.
    other = client.get("/v1/me/export", headers=grace_headers).json()
    assert other["user"]["email"] == "grace@example.test"
    assert not {b["id"] for b in other["bets"]} & {b["id"] for b in body["bets"]}
    assert "ada@example.test" not in json.dumps(other).lower()


def test_export_of_a_new_account_is_empty_but_well_formed(
    client: TestClient, headers: Headers
) -> None:
    body = client.get("/v1/me/export", headers=headers).json()
    assert body["bets"] == [] and body["watchlist"] == []
    assert body["sync_connections"] == [] and body["sync_runs"] == []
    assert [e["action"] for e in body["audit_log"]] == ["auth.register", "account.export"]
    # Every export is audited.
    again = client.get("/v1/me/export", headers=headers).json()
    assert [e["action"] for e in again["audit_log"]].count("account.export") == 2


def test_export_requires_authentication(client: TestClient) -> None:
    response = client.get("/v1/me/export")
    assert response.status_code == 401
    assert_envelope(response.json(), "not_authenticated")
    forged = client.get("/v1/me/export", headers={"Authorization": "Bearer not-a-token"})
    assert forged.status_code == 401
    assert_envelope(forged.json(), "invalid_token")


# ------------------------------------------------------------ change password
def _change(
    client: TestClient, headers: Headers, current: str = PASSWORD, new: str = NEW_PASSWORD
) -> Any:
    return client.post(
        "/v1/me/password",
        json={"current_password": current, "new_password": new},
        headers=headers,
    )


def test_change_password_returns_a_fresh_token_and_revokes_old_ones(
    client: TestClient, app
) -> None:  # type: ignore[no-untyped-def]
    registered = register(client)
    old = {"Authorization": f"Bearer {registered['access_token']}"}
    second_session = client.post(
        "/v1/auth/login", json={"email": "ada@example.test", "password": PASSWORD}
    ).json()
    also_old = {"Authorization": f"Bearer {second_session['access_token']}"}
    assert client.get("/v1/me", headers=also_old).status_code == 200

    response = _change(client, old)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert set(body) == {"access_token", "token_type", "expires_in", "user"}
    assert body["token_type"] == "bearer" and body["expires_in"] == 3600
    assert body["user"] == registered["user"]
    assert body["access_token"] != registered["access_token"]
    assert "password" not in str(body).lower()

    # Every token from before the change is dead, on every route.
    for stale in (old, also_old):
        for call in (
            lambda h: client.get("/v1/me", headers=h),
            lambda h: client.get("/v1/bets", headers=h),
            lambda h: client.get("/v1/me/export", headers=h),
            lambda h: _change(client, h, NEW_PASSWORD, "yet-another-passphrase"),
        ):
            rejected = call(stale)
            assert rejected.status_code == 401
            assert_envelope(rejected.json(), "invalid_token")

    fresh = {"Authorization": f"Bearer {body['access_token']}"}
    assert client.get("/v1/me", headers=fresh).json() == registered["user"]

    # The old password no longer logs in; the new one does and its token works.
    stale_login = client.post(
        "/v1/auth/login", json={"email": "ada@example.test", "password": PASSWORD}
    )
    assert stale_login.status_code == 401
    login = client.post(
        "/v1/auth/login", json={"email": "ada@example.test", "password": NEW_PASSWORD}
    )
    assert login.status_code == 200
    relogged = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/v1/me", headers=relogged).status_code == 200

    with app.state.session_factory() as db:
        user = db.scalar(select(User))
        assert user is not None
        assert user.token_version == 1 and user.password_changed_at is not None
        assert user.password_hash.startswith("$argon2") and NEW_PASSWORD not in user.password_hash
        audit = [row for row in db.scalars(select(AuditLog)) if row.action.startswith("auth.pass")]
    assert [row.action for row in audit] == ["auth.password_changed"]
    assert audit[0].user_id == registered["user"]["id"] and audit[0].details is None
    claims = jwt.decode(body["access_token"], DEV_JWT_SECRET, algorithms=["HS256"])
    assert claims["ver"] == 1


def test_changing_twice_revokes_the_token_from_the_first_change(client: TestClient) -> None:
    headers = auth_headers(client)
    first = _change(client, headers).json()["access_token"]
    second = _change(
        client, {"Authorization": f"Bearer {first}"}, NEW_PASSWORD, "third-passphrase-here"
    )
    assert second.status_code == 200
    assert client.get("/v1/me", headers={"Authorization": f"Bearer {first}"}).status_code == 401
    newest = {"Authorization": f"Bearer {second.json()['access_token']}"}
    assert client.get("/v1/me", headers=newest).status_code == 200


def test_wrong_current_password_is_a_neutral_400(client: TestClient, headers: Headers, app) -> None:  # type: ignore[no-untyped-def]
    response = _change(client, headers, current="not-my-password")
    assert response.status_code == 400
    assert_envelope(response.json(), "invalid_credentials")
    message = response.json()["error"]["message"].lower()
    assert "current" not in message and "incorrect" not in message and "wrong" not in message
    # Nothing changed: the token and the password still work.
    assert client.get("/v1/me", headers=headers).status_code == 200
    assert (
        client.post(
            "/v1/auth/login", json={"email": "ada@example.test", "password": PASSWORD}
        ).status_code
        == 200
    )
    with app.state.session_factory() as db:
        user = db.scalar(select(User))
        assert user is not None and user.token_version == 0 and user.password_changed_at is None
        actions = [row.action for row in db.scalars(select(AuditLog))]
    assert "auth.password_change_failed" in actions and "auth.password_changed" not in actions


def test_new_password_rules(client: TestClient, headers: Headers) -> None:
    for body in (
        {"current_password": PASSWORD, "new_password": "short"},  # under 10 characters
        {"current_password": PASSWORD, "new_password": "x" * 129},
        {"current_password": PASSWORD, "new_password": PASSWORD},  # must differ
        {"current_password": PASSWORD},
        {"new_password": NEW_PASSWORD},
        {"current_password": "", "new_password": NEW_PASSWORD},
    ):
        response = client.post("/v1/me/password", json=body, headers=headers)
        assert response.status_code == 422, body
        assert_envelope(response.json(), "validation_error")
        assert PASSWORD not in response.text and NEW_PASSWORD not in response.text
    assert client.get("/v1/me", headers=headers).status_code == 200


def test_change_password_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/v1/me/password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD}
    )
    assert response.status_code == 401
    assert_envelope(response.json(), "not_authenticated")


def test_change_password_does_not_affect_other_users(
    client: TestClient, headers: Headers, other_headers: Headers
) -> None:
    assert _change(client, headers).status_code == 200
    assert client.get("/v1/me", headers=other_headers).status_code == 200
    assert (
        client.post(
            "/v1/auth/login", json={"email": "grace@example.test", "password": PASSWORD}
        ).status_code
        == 200
    )


def test_change_password_shares_the_auth_rate_limit(make_app: AppFactory) -> None:
    app = make_app(rate_limit_enabled=True, rate_limit_auth_per_minute=3)
    with TestClient(app) as client:
        headers = auth_headers(client)  # 1 of 3
        assert _change(client, headers, current="wrong-password-1").status_code == 400  # 2
        assert _change(client, headers, current="wrong-password-2").status_code == 400  # 3
        limited = _change(client, headers)
        assert limited.status_code == 429
        assert_envelope(limited.json(), "rate_limited")
        assert int(limited.headers["retry-after"]) >= 1
        # The limiter is shared with login.
        login = client.post(
            "/v1/auth/login", json={"email": "ada@example.test", "password": PASSWORD}
        )
        assert login.status_code == 429
