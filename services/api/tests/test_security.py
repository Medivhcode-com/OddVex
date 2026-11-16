"""Security regression tests: tokens, roles, object ownership, mass assignment, input
handling, CORS and the per-account login throttle. One file on purpose, so a regression in
any of these is easy to find."""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from oddvex_api.auth.security import JWT_ISSUER, create_access_token
from oddvex_api.config import DEV_JWT_SECRET
from oddvex_api.db import Bet, CommunityReport, User
from oddvex_api.ratelimit import SlidingWindowRateLimiter

from .conftest import PASSWORD, AppFactory, admin_headers, auth_headers, register, set_flag

Headers = dict[str, str]
BET = {
    "bet_type": "straight",
    "stake": 10,
    "sportsbook": "Northline",
    "legs": [{"selection": "Tides ML", "market": "moneyline", "odds": -110}],
}


def bearer(token: str) -> Headers:
    return {"Authorization": f"Bearer {token}"}


def b64(data: dict[str, Any]) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


def claims(user_id: str, **overrides: Any) -> dict[str, Any]:
    now = int(time.time())
    return {
        "sub": user_id,
        "role": "user",
        "iss": JWT_ISSUER,
        "iat": now,
        "exp": now + 600,
        **overrides,
    }


def assert_invalid_token(client: TestClient, token: str, path: str = "/v1/me") -> None:
    response = client.get(path, headers=bearer(token))
    assert response.status_code == 401, token
    assert response.json()["error"]["code"] == "invalid_token"
    assert response.headers["www-authenticate"] == "Bearer"


# ------------------------------------------------------------------------ JWT
def test_a_valid_token_works_so_the_rejections_below_mean_something(client: TestClient) -> None:
    user = register(client)["user"]
    token = jwt.encode(claims(user["id"]), DEV_JWT_SECRET, algorithm="HS256")
    assert client.get("/v1/me", headers=bearer(token)).status_code == 200


def test_token_with_a_wrong_signature_is_rejected(client: TestClient) -> None:
    account = register(client)
    user_id = account["user"]["id"]
    forged = jwt.encode(claims(user_id), "some-other-secret-of-decent-length-123", "HS256")
    assert_invalid_token(client, forged)
    # A real token whose signature or payload was altered.
    header, payload, signature = account["access_token"].split(".")
    flipped = signature[:-2] + ("AA" if not signature.endswith("AA") else "BB")
    assert_invalid_token(client, f"{header}.{payload}.{flipped}")
    assert_invalid_token(client, f"{header}.{b64(claims(user_id, role='admin'))}.{signature}")
    assert_invalid_token(client, f"{header}.{payload}.")
    assert_invalid_token(client, f"{header}.{payload}")
    assert_invalid_token(client, "not-a-jwt")


@pytest.mark.filterwarnings("ignore:The HMAC key is")
def test_token_with_alg_none_is_rejected(client: TestClient) -> None:
    user_id = register(client)["user"]["id"]
    for alg in ("none", "None", "NONE"):
        unsigned = f"{b64({'alg': alg, 'typ': 'JWT'})}.{b64(claims(user_id))}."
        assert_invalid_token(client, unsigned)
    assert_invalid_token(client, jwt.encode(claims(user_id), None, algorithm="none"))  # type: ignore[arg-type]
    # Another HMAC algorithm with the right secret is not accepted either.
    assert_invalid_token(client, jwt.encode(claims(user_id), DEV_JWT_SECRET, algorithm="HS512"))


def test_expired_token_is_rejected(client: TestClient) -> None:
    user_id = register(client)["user"]["id"]
    long_ago = datetime.now(UTC) - timedelta(hours=2)
    expired, _ = create_access_token(user_id, "user", DEV_JWT_SECRET, 60, now=long_ago)
    assert_invalid_token(client, expired)
    now = int(time.time())
    just_expired = jwt.encode(
        claims(user_id, iat=now - 120, exp=now - 1), DEV_JWT_SECRET, algorithm="HS256"
    )
    assert_invalid_token(client, just_expired)
    for missing in ("exp", "sub", "iat"):
        partial = claims(user_id)
        del partial[missing]
        assert_invalid_token(client, jwt.encode(partial, DEV_JWT_SECRET, algorithm="HS256"))
    wrong_issuer = jwt.encode(claims(user_id, iss="someone-else"), DEV_JWT_SECRET, "HS256")
    assert_invalid_token(client, wrong_issuer)


def test_token_with_a_wrong_version_is_rejected(client: TestClient) -> None:
    account = register(client)
    user_id = account["user"]["id"]
    for version in (1, 7, -1):
        stale = jwt.encode(claims(user_id, ver=version), DEV_JWT_SECRET, algorithm="HS256")
        assert_invalid_token(client, stale)
    # After a password change the version moves on and the old token is the wrong one.
    changed = client.post(
        "/v1/me/password",
        json={"current_password": PASSWORD, "new_password": "a-different-password-9"},
        headers=bearer(account["access_token"]),
    )
    assert changed.status_code == 200
    assert_invalid_token(client, account["access_token"])
    assert_invalid_token(
        client, jwt.encode(claims(user_id, ver=0), DEV_JWT_SECRET, algorithm="HS256")
    )
    assert client.get("/v1/me", headers=bearer(changed.json()["access_token"])).status_code == 200


def test_token_for_a_user_that_does_not_exist_is_rejected(client: TestClient) -> None:
    register(client)
    assert_invalid_token(client, jwt.encode(claims("f" * 32), DEV_JWT_SECRET, algorithm="HS256"))


def test_role_claim_in_the_token_is_not_trusted(client: TestClient) -> None:
    user_id = register(client)["user"]["id"]
    token, _ = create_access_token(user_id, "admin", DEV_JWT_SECRET, 5)
    assert client.get("/v1/me", headers=bearer(token)).json()["role"] == "user"
    for method, path, body in (
        ("GET", "/v1/admin/overview", None),
        ("GET", "/v1/admin/users", None),
        ("GET", "/v1/admin/audit", None),
        ("GET", "/v1/admin/flags", None),
        ("GET", "/v1/admin/email-outbox", None),
        ("PUT", "/v1/admin/flags/premium_gating", {"enabled": True}),
        ("PUT", f"/v1/admin/users/{user_id}/plan", {"plan": "premium"}),
    ):
        response = client.request(method, path, json=body, headers=bearer(token))
        assert response.status_code == 403, path
        assert response.json()["error"]["code"] == "forbidden"
    # Other claims are not trusted either.
    extra = jwt.encode(
        claims(user_id, role="admin", plan="premium", status="active", email_verified=True),
        DEV_JWT_SECRET,
        algorithm="HS256",
    )
    me = client.get("/v1/me", headers=bearer(extra)).json()
    assert (me["role"], me["plan"], me["email_verified"]) == ("user", "free", False)


# ----------------------------------------------------------------------- IDOR
@pytest.fixture
def world(make_app: AppFactory) -> Iterator[tuple[TestClient, Headers, Headers, dict[str, str]]]:
    """User A with one of every owner-scoped resource, and user B with nothing."""
    with TestClient(make_app(alert_eval_min_seconds=0)) as client:
        a = auth_headers(client, "ada@example.test")
        b = auth_headers(client, "grace@example.test")
        ids: dict[str, str] = {}

        client.put("/v1/me/stake-reminder", json={"weekly_stake_threshold": 5}, headers=a)
        bet = client.post("/v1/bets", json=BET, headers=a)
        assert bet.status_code == 201, bet.text
        ids["bet"] = bet.json()["id"]
        ids["leg"] = bet.json()["legs"][0]["id"]

        team = client.get("/v1/events").json()[0]["home_team"]["id"]
        watch = client.post("/v1/watchlist", json={"kind": "team", "ref_id": team}, headers=a)
        assert watch.status_code == 201, watch.text
        ids["watchlist"] = watch.json()["id"]

        event = client.get("/v1/events", params={"status": "upcoming"}).json()[0]["id"]
        alert = client.post("/v1/alerts", json={"kind": "game_final", "event_id": event}, headers=a)
        assert alert.status_code == 201, alert.text
        ids["alert"] = alert.json()["id"]

        connection = client.post("/v1/sync/connections", json={"provider": "mock"}, headers=a)
        assert connection.status_code == 201, connection.text
        ids["connection"] = connection.json()["id"]
        run = client.post(f"/v1/sync/connections/{ids['connection']}/sync", headers=a)
        assert run.status_code == 200, run.text

        client.put(
            "/v1/me/notification-preferences", json={"in_app": {"game_final": False}}, headers=a
        )
        notifications = client.get("/v1/notifications", headers=a).json()["items"]
        assert notifications, "the stake reminder and the import produced notifications"
        ids["notification"] = notifications[0]["id"]
        yield client, a, b, ids


def test_idor_sweep_user_b_cannot_reach_any_of_user_a_objects(
    world: tuple[TestClient, Headers, Headers, dict[str, str]],
) -> None:
    client, a, b, ids = world
    connection = f"/v1/sync/connections/{ids['connection']}"
    attempts: list[tuple[str, str, dict[str, Any] | None]] = [
        # bets
        ("GET", f"/v1/bets/{ids['bet']}", None),
        ("PATCH", f"/v1/bets/{ids['bet']}", {"notes": "mine now", "stake": 1}),
        ("POST", f"/v1/bets/{ids['bet']}/settle", {"result": "lost"}),
        ("DELETE", f"/v1/bets/{ids['bet']}", None),
        # watchlist
        ("DELETE", f"/v1/watchlist/{ids['watchlist']}", None),
        # alerts
        ("PATCH", f"/v1/alerts/{ids['alert']}", {"state": "paused"}),
        ("DELETE", f"/v1/alerts/{ids['alert']}", None),
        # notifications
        ("POST", f"/v1/notifications/{ids['notification']}/read", None),
        ("DELETE", f"/v1/notifications/{ids['notification']}", None),
        # sync connections and runs
        ("POST", f"{connection}/sync", None),
        ("GET", f"{connection}/runs", None),
        ("DELETE", connection, None),
        ("DELETE", f"{connection}?delete_data=true", None),
    ]
    for method, path, body in attempts:
        response = client.request(method, path, json=body, headers=b)
        assert response.status_code in (403, 404), (method, path, response.status_code)
        assert response.json()["error"]["code"] in ("not_found", "forbidden"), path
        # Same answer as for an id that does not exist: no existence oracle.
        missing_path = path
        for value in ids.values():
            missing_path = missing_path.replace(value, "0" * 32)
        missing = client.request(method, missing_path, json=body, headers=b)
        assert missing.status_code == response.status_code, (method, path)

    # A's leg id cannot be used through one of B's own bets.
    own = client.post("/v1/bets", json=BET, headers=b).json()
    cross = client.post(
        f"/v1/bets/{own['id']}/settle",
        json={"leg_results": [{"leg_id": ids["leg"], "result": "won"}]},
        headers=b,
    )
    assert cross.status_code == 422 and cross.json()["error"]["code"] == "unknown_leg"
    client.delete(f"/v1/bets/{own['id']}", headers=b)

    # B's collections contain nothing of A's.
    assert client.get("/v1/bets", headers=b).json() == []
    assert client.get("/v1/bets/summary", headers=b).json()["totals"]["pending_count"] == 0
    assert client.get("/v1/bets/analytics", headers=b).json()["settled_count"] == 0
    assert client.get("/v1/watchlist", headers=b).json()["items"] == []
    assert client.get("/v1/watchlist/events", headers=b).json() == []
    assert client.get("/v1/alerts", headers=b).json()["items"] == []
    assert client.get("/v1/notifications", headers=b).json()["items"] == []
    assert client.get("/v1/notifications/unread-count", headers=b).json()["unread_count"] == 0
    assert client.post("/v1/notifications/read-all", headers=b).status_code == 200
    assert client.get("/v1/sync/connections", headers=b).json() == []
    # Per-user settings: B sees and changes only their own.
    assert client.get("/v1/me/notification-preferences", headers=b).json()["in_app"]["game_final"]
    reminder = client.get("/v1/me/stake-reminder", headers=b).json()
    assert reminder["weekly_stake_threshold"] is None and reminder["staked_this_week"] == 0
    client.put("/v1/me/stake-reminder", json={"weekly_stake_threshold": 999}, headers=b)
    client.put(
        "/v1/me/notification-preferences", json={"in_app": {"bet_settled": False}}, headers=b
    )
    # Export: only B's data, none of A's ids anywhere in it.
    export = client.get("/v1/me/export", headers=b)
    assert export.status_code == 200
    assert export.json()["user"]["email"] == "grace@example.test"
    for name, value in ids.items():
        assert value not in export.text, name
    assert "ada@example.test" not in export.text
    assert client.get("/v1/me/entitlements", headers=b).json()["plan"] == "free"

    # And everything of A's is exactly as A left it.
    bet = client.get(f"/v1/bets/{ids['bet']}", headers=a).json()
    assert (bet["status"], bet["stake"], bet["notes"]) == ("pending", 10.0, None)
    assert [i["id"] for i in client.get("/v1/watchlist", headers=a).json()["items"]] == [
        ids["watchlist"]
    ]
    (alert,) = client.get("/v1/alerts", headers=a).json()["items"]
    assert (alert["id"], alert["state"]) == (ids["alert"], "active")
    items = client.get("/v1/notifications", headers=a).json()["items"]
    assert ids["notification"] in [n["id"] for n in items]
    assert all(n["read_at"] is None for n in items)
    (connection_out,) = client.get("/v1/sync/connections", headers=a).json()
    assert connection_out["id"] == ids["connection"] and connection_out["status"] == "active"
    assert len(client.get(f"{connection}/runs", headers=a).json()) == 1
    assert client.get("/v1/me/stake-reminder", headers=a).json()["weekly_stake_threshold"] == 5
    preferences = client.get("/v1/me/notification-preferences", headers=a).json()["in_app"]
    assert preferences["game_final"] is False and preferences["bet_settled"] is True
    a_export = client.get("/v1/me/export", headers=a).json()
    assert a_export["user"]["email"] == "ada@example.test"
    assert len(a_export["bets"]) > 1 and len(a_export["sync_connections"]) == 1


def test_every_owner_scoped_route_requires_a_token(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    public_prefixes = (
        "/health",
        "/v1/meta",
        "/v1/leagues",
        "/v1/sportsbooks",
        "/v1/events",
        "/v1/players",
        "/v1/props",
        "/v1/quant",
        "/v1/value",
        "/v1/flags",
        "/v1/assistant",
        "/v1/dev",
        "/v1/auth/register",
        "/v1/auth/login",
        "/v1/auth/verify-email/confirm",
        "/v1/auth/password-reset",
    )
    #: Behind the ``community`` flag, which is off here: 404 for everyone, token or not.
    #: ``test_every_community_route_requires_a_token`` repeats this with the flag on.
    flagged_off = ("/v1/community", "/v1/admin/community")
    checked = 0
    for path, item in schema["paths"].items():
        if path.startswith(public_prefixes):
            continue
        for method in item:
            if path.startswith(flagged_off):
                url = path.replace("{", "").replace("}", "")
                response = client.request(method.upper(), url, json={})
                assert response.status_code == 404, (method, path, response.status_code)
                assert response.json()["error"]["code"] == "feature_disabled", path
                continue
            url = path.replace("{", "").replace("}", "")
            response = client.request(method.upper(), url, json={})
            assert response.status_code == 401, (method, path, response.status_code)
            assert response.json()["error"]["code"] == "not_authenticated", path
            checked += 1
    assert checked >= 45


# ------------------------------------------------------------ mass assignment
def test_register_ignores_role_plan_status_and_user_id(client: TestClient, app: FastAPI) -> None:
    response = client.post(
        "/v1/auth/register",
        json={
            "email": "mallory@example.test",
            "password": PASSWORD,
            "display_name": "Mallory",
            "age_confirmed": True,
            "role": "admin",
            "plan": "premium",
            "status": "suspended",
            "user_id": "a" * 32,
            "id": "b" * 32,
            "is_active": False,
            "email_verified": True,
            "email_verified_at": "2020-01-01T00:00:00Z",
            "token_version": 99,
        },
    )
    assert response.status_code in (201, 422)
    if response.status_code == 422:
        return
    user = response.json()["user"]
    assert (user["role"], user["plan"], user["email_verified"]) == ("user", "free", False)
    assert user["id"] not in ("a" * 32, "b" * 32)
    with app.state.session_factory() as db:
        stored = db.scalar(select(User).where(User.email == "mallory@example.test"))
        assert (stored.role, stored.plan, stored.status) == ("user", "free", "active")
        assert stored.is_active is True and stored.token_version == 0
        assert stored.email_verified_at is None
    headers = bearer(response.json()["access_token"])
    assert client.get("/v1/admin/overview", headers=headers).status_code == 403


def test_bet_bodies_cannot_set_the_owner_or_the_outcome(
    client: TestClient, app: FastAPI, headers: Headers, other_headers: Headers
) -> None:
    victim_id = client.get("/v1/me", headers=other_headers).json()["id"]
    my_id = client.get("/v1/me", headers=headers).json()["id"]
    injected = {
        "user_id": victim_id,
        "id": "c" * 32,
        "status": "settled",
        "result": "won",
        "profit": 100000,
        "payout": 100000,
        "source": "sync",
        "settled_by": "auto",
        "role": "admin",
        "plan": "premium",
    }
    created = client.post("/v1/bets", json={**BET, **injected}, headers=headers)
    assert created.status_code in (201, 422)
    if created.status_code == 201:
        bet = created.json()
        assert bet["id"] != "c" * 32
        assert (bet["status"], bet["result"], bet["profit"], bet["source"]) == (
            "pending",
            None,
            None,
            "manual",
        )
    else:
        bet = client.post("/v1/bets", json=BET, headers=headers).json()
    updated = client.patch(
        f"/v1/bets/{bet['id']}", json={"notes": "edited", **injected}, headers=headers
    )
    assert updated.status_code in (200, 422)
    after = client.get(f"/v1/bets/{bet['id']}", headers=headers).json()
    assert (after["status"], after["result"], after["profit"], after["payout"]) == (
        "pending",
        None,
        None,
        None,
    )
    assert after["settled_by"] is None and after["source"] == "manual"
    with app.state.session_factory() as db:
        assert db.get(Bet, bet["id"]).user_id == my_id
    assert client.get("/v1/bets", headers=other_headers).json() == []
    me = client.get("/v1/me", headers=headers).json()
    assert (me["role"], me["plan"]) == ("user", "free")


def test_other_update_bodies_cannot_change_role_plan_status_or_owner(
    world: tuple[TestClient, Headers, Headers, dict[str, str]],
) -> None:
    client, a, b, ids = world
    b_id = client.get("/v1/me", headers=b).json()["id"]
    injected = {"role": "admin", "plan": "premium", "status": "suspended", "user_id": b_id}
    calls = [
        ("PUT", "/v1/me/notification-preferences", {"in_app": {"line_move": False}}),
        ("PUT", "/v1/me/stake-reminder", {"weekly_stake_threshold": 50}),
        ("PATCH", f"/v1/alerts/{ids['alert']}", {"state": "paused"}),
        (
            "POST",
            "/v1/me/password",
            {"current_password": "wrong-password", "new_password": "x" * 12},
        ),
        ("POST", "/v1/auth/login", {"email": "ada@example.test", "password": PASSWORD}),
    ]
    for method, path, body in calls:
        response = client.request(method, path, json={**body, **injected}, headers=a)
        assert response.status_code in (200, 400, 422), (path, response.status_code)
    me = client.get("/v1/me", headers=a).json()
    assert (me["role"], me["plan"]) == ("user", "free")
    assert client.get("/v1/admin/overview", headers=a).status_code == 403
    # The alert is still A's, and B got nothing.
    assert [r["id"] for r in client.get("/v1/alerts", headers=a).json()["items"]] == [ids["alert"]]
    assert client.get("/v1/alerts", headers=b).json()["items"] == []
    assert client.get("/v1/me/stake-reminder", headers=b).json()["weekly_stake_threshold"] is None
    with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
        stored = db.scalar(select(User).where(User.email == "ada@example.test"))
        assert (stored.role, stored.plan, stored.status) == ("user", "free", "active")


# ------------------------------------------------------------ input handling
def test_oversized_body_is_413(client: TestClient, headers: Headers) -> None:
    huge = {**BET, "notes": "x" * 70_000}
    for path, extra in (("/v1/bets", headers), ("/v1/auth/login", {}), ("/v1/auth/register", {})):
        response = client.post(path, json=huge, headers=extra)
        assert response.status_code == 413, path
        assert response.json()["error"]["code"] == "payload_too_large"
        assert response.json()["error"]["details"] == {"max_body_bytes": 65536}
    assert client.get("/v1/bets", headers=headers).json() == []

    def chunks() -> Iterator[bytes]:  # no Content-Length: counted while it is read
        for _ in range(80):
            yield b"x" * 1024

    streamed = client.post(
        "/v1/bets", content=chunks(), headers={**headers, "Content-Type": "application/json"}
    )
    assert streamed.status_code == 413
    assert streamed.json()["error"]["code"] == "payload_too_large"


PAYLOADS = [
    "'; DROP TABLE users; --",
    "' OR '1'='1",
    '" OR ""="',
    "1; SELECT pg_sleep(10); --",
    "Robert'); DELETE FROM bets WHERE ('1'='1",
    "<script>alert(1)</script>",
    '<img src=x onerror="alert(1)">',
    "{{7*7}} ${7*7} #{7*7}",
    "%s %d %n \\x00 \\u0000",
    "../../etc/passwd",
    "Ünïcödé 🎲 ‮ reversed",
]


@pytest.mark.parametrize("payload", PAYLOADS)
def test_hostile_text_is_stored_and_returned_verbatim(
    client: TestClient, headers: Headers, payload: str
) -> None:
    created = client.post(
        "/v1/bets",
        json={
            "bet_type": "straight",
            "stake": 10,
            "sportsbook": payload,
            "notes": payload,
            "legs": [
                {
                    "selection": payload,
                    "market": "moneyline",
                    "event_label": payload,
                    "odds": -110,
                }
            ],
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    bet = client.get(f"/v1/bets/{created.json()['id']}", headers=headers).json()
    assert bet["sportsbook"] == payload.strip() and bet["notes"] == payload
    assert bet["legs"][0]["selection"] == payload.strip()
    assert bet["legs"][0]["event_label"] == payload
    assert created.headers["content-type"] == "application/json"
    assert created.headers["x-content-type-options"] == "nosniff"

    # In filters and search it is just a string to compare with.
    for params in ({"sportsbook": payload}, {"market": payload[:40]}, {"sport": payload[:32]}):
        listed = client.get("/v1/bets", params=params, headers=headers)
        assert listed.status_code == 200, params
    if payload.isascii():
        # (SQLite and C-locale PostgreSQL lower-case ASCII only, so the case-insensitive
        # sportsbook filter is only exact for ASCII names.)
        found = client.get("/v1/bets", params={"sportsbook": payload}, headers=headers).json()
        assert len(found) == 1
    assert client.get("/v1/players", params={"q": payload}).status_code == 200
    assert client.get(f"/v1/bets/{payload}", headers=headers).status_code in (404, 405)
    assistant = client.post("/v1/assistant/query", json={"query": payload})
    assert assistant.status_code in (200, 422)
    # Nothing was dropped or deleted, and the export carries the same text.
    export = client.get("/v1/me/export", headers=headers).json()
    assert export["bets"][0]["notes"] == payload
    assert client.get("/v1/me", headers=headers).status_code == 200


@pytest.mark.parametrize("payload", PAYLOADS[:7])
def test_hostile_text_in_account_fields(client: TestClient, payload: str) -> None:
    account = register(client, "eve@example.test", display_name=payload)
    assert account["user"]["display_name"] == payload.strip()
    for email in (payload, f"{payload}@example.test", "eve@example.test' OR '1'='1"):
        attempt = client.post("/v1/auth/login", json={"email": email, "password": payload})
        assert attempt.status_code in (401, 422), email
        reset = client.post("/v1/auth/password-reset/request", json={"email": email})
        assert reset.status_code in (202, 422), email
        outbox = client.get("/v1/dev/email-outbox/latest", params={"to": email})
        assert outbox.status_code in (404, 422), email
    confirm = client.post("/v1/auth/verify-email/confirm", json={"token": payload.ljust(16, "x")})
    assert confirm.status_code == 400
    # The account is intact.
    assert (
        client.post(
            "/v1/auth/login", json={"email": "eve@example.test", "password": PASSWORD}
        ).status_code
        == 200
    )


def test_hostile_text_in_admin_search(make_app: AppFactory) -> None:
    with TestClient(make_app(admin_emails="boss@example.test")) as client:
        admin = admin_headers(client, "boss@example.test")
        auth_headers(client)
        for payload in PAYLOADS:
            users = client.get("/v1/admin/users", params={"q": payload[:120]}, headers=admin)
            assert users.status_code == 200 and users.json()["items"] == [], payload
            audit = client.get(
                "/v1/admin/audit",
                params={"action": payload[:64], "user_id": payload[:64]},
                headers=admin,
            )
            assert audit.status_code == 200 and audit.json()["items"] == [], payload
            reason = client.post(
                "/v1/admin/users/" + payload.replace("/", "") + "/suspend",
                json={"reason": payload},
                headers=admin,
            )
            assert reason.status_code in (404, 405), payload
        assert client.get("/v1/admin/users", headers=admin).json()["total"] == 2


# ----------------------------------------------------------------------- CORS
def test_cors_denies_an_unlisted_origin(make_app: AppFactory) -> None:
    with TestClient(make_app(cors_origins="https://app.example.test")) as client:
        allowed = client.get("/v1/flags", headers={"Origin": "https://app.example.test"})
        assert allowed.headers["access-control-allow-origin"] == "https://app.example.test"
        for origin in (
            "https://evil.example.test",
            "https://app.example.test.evil.test",
            "http://app.example.test",  # scheme matters
            "https://APP.example.test:8443",
            "null",
        ):
            for path in (
                "/v1/flags",
                "/v1/value",
                "/v1/me",
                "/v1/dev/email-outbox/latest?to=a@b.co",
            ):
                response = client.get(path, headers={"Origin": origin})
                assert "access-control-allow-origin" not in response.headers, (origin, path)
            preflight = client.options(
                "/v1/auth/password-reset/request",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                },
            )
            assert preflight.status_code == 400, origin
            assert "access-control-allow-origin" not in preflight.headers, origin
        # Credentials are never allowed cross-origin, and there is no wildcard.
        assert "access-control-allow-credentials" not in allowed.headers
        assert allowed.headers["access-control-allow-origin"] != "*"


# ------------------------------------------------- per-account login throttle
class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def throttled(make_app: AppFactory) -> Iterator[tuple[TestClient, FakeClock]]:
    """Rate limits on, with a per-IP limit high enough to stay out of the way."""
    app = make_app(rate_limit_enabled=True, rate_limit_auth_per_minute=1000, trust_proxy=True)
    clock = FakeClock()
    app.state.account_limiter = SlidingWindowRateLimiter(
        app.state.settings.account_limit_window_seconds, clock=clock
    )
    with TestClient(app) as client:
        register(client)
        yield client, clock


def attempt(client: TestClient, email: str, password: str, ip: str = "10.0.0.1") -> Any:
    return client.post(
        "/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-Forwarded-For": ip},
    )


def test_login_is_throttled_per_account_regardless_of_ip(
    throttled: tuple[TestClient, FakeClock],
) -> None:
    client, clock = throttled
    assert client.app.state.settings.login_max_failures == 8  # type: ignore[attr-defined]
    assert client.app.state.settings.account_limit_window_seconds == 900  # type: ignore[attr-defined]
    for number in range(8):
        clock.now += 10
        failed = attempt(client, "ada@example.test", "wrong-password", ip=f"10.0.0.{number}")
        assert failed.status_code == 401, number
        assert failed.json()["error"]["code"] == "invalid_credentials"

    # The ninth attempt is refused even with the right password and from a new address.
    blocked = attempt(client, "ada@example.test", PASSWORD, ip="192.0.2.77")
    assert blocked.status_code == 429
    body = blocked.json()["error"]
    assert body["code"] == "rate_limited" and set(body) == {"code", "message", "details"}
    # The first failure was 70 seconds ago in a 900 second window.
    assert body["details"] == {"retry_after_seconds": 830}
    assert blocked.headers["retry-after"] == "830"
    assert "access_token" not in blocked.text
    # Another account is not affected.
    register(client, "grace@example.test")
    assert attempt(client, "grace@example.test", PASSWORD).status_code == 200

    # Still refused just before the window moves on, allowed again just after.
    clock.now += 829
    assert attempt(client, "ada@example.test", PASSWORD).status_code == 429
    clock.now += 2
    assert attempt(client, "ada@example.test", PASSWORD).status_code == 200


def test_login_throttle_does_not_reveal_whether_the_account_exists(
    throttled: tuple[TestClient, FakeClock],
) -> None:
    client, _ = throttled
    seen: dict[str, list[tuple[int, str, dict[str, Any]]]] = {}
    for email in ("ada@example.test", "nobody@example.test"):
        for number in range(10):
            response = attempt(client, email, "wrong-password", ip=f"10.0.1.{number}")
            error = response.json()["error"]
            seen.setdefault(email, []).append(
                (response.status_code, error["code"], error.get("details") or {})
            )
    assert seen["ada@example.test"] == seen["nobody@example.test"]
    assert [status for status, _, _ in seen["ada@example.test"]] == [401] * 8 + [429] * 2


def test_a_successful_login_clears_the_failure_count(
    throttled: tuple[TestClient, FakeClock],
) -> None:
    client, _ = throttled
    for _ in range(7):
        assert attempt(client, "ada@example.test", "wrong-password").status_code == 401
    assert attempt(client, "ada@example.test", PASSWORD).status_code == 200
    for _ in range(7):
        assert attempt(client, "ada@example.test", "wrong-password").status_code == 401
    assert attempt(client, "ada@example.test", PASSWORD).status_code == 200
    # Email matching is case-insensitive, so changing the case does not dodge the count.
    for _ in range(8):
        assert attempt(client, "ADA@Example.Test", "wrong-password").status_code == 401
    assert attempt(client, "ada@example.test", PASSWORD).status_code == 429


def test_a_password_reset_lifts_the_login_throttle(
    throttled: tuple[TestClient, FakeClock],
) -> None:
    client, _ = throttled
    for _ in range(8):
        attempt(client, "ada@example.test", "wrong-password")
    assert attempt(client, "ada@example.test", PASSWORD).status_code == 429
    client.post("/v1/auth/password-reset/request", json={"email": "ada@example.test"})
    token = client.get(
        "/v1/dev/email-outbox/latest",
        params={"to": "ada@example.test", "template": "password_reset"},
    ).json()["token"]
    done = client.post(
        "/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "the-new-password-1"},
    )
    assert done.status_code == 204
    assert attempt(client, "ada@example.test", "the-new-password-1").status_code == 200


def test_login_throttle_is_off_when_rate_limiting_is_disabled(client: TestClient) -> None:
    assert client.app.state.settings.rate_limit_enabled is False  # type: ignore[attr-defined]
    register(client)
    for _ in range(12):
        assert attempt(client, "ada@example.test", "wrong-password").status_code == 401
    assert attempt(client, "ada@example.test", PASSWORD).status_code == 200


def test_account_limiter_primitives() -> None:
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(100, clock=clock)
    assert limiter.blocked_for("k", 2) == 0.0
    limiter.hit("k")
    clock.now += 30
    assert limiter.blocked_for("k", 2) == 0.0  # checking records nothing
    limiter.hit("k")
    assert limiter.blocked_for("k", 2) == 70.0
    assert limiter.blocked_for("other", 2) == 0.0
    clock.now += 70
    assert limiter.blocked_for("k", 2) == 0.0
    limiter.hit("k")
    assert limiter.blocked_for("k", 2) == 30.0
    limiter.forget("k")
    assert limiter.blocked_for("k", 2) == 0.0
    limiter.forget("never-seen")


# ------------------------------------------------------------------ community
def community_app(make_app: AppFactory) -> FastAPI:
    return make_app(admin_emails="boss@example.test", community_grade_min_seconds=0)


def community_member(client: TestClient, handle: str) -> Headers:
    headers = auth_headers(client, f"{handle}@example.test")
    created = client.put(
        "/v1/community/profile", json={"handle": handle, "is_public": True}, headers=headers
    )
    assert created.status_code == 201, created.text
    return headers


def community_pick(client: TestClient, headers: Headers, index: int = 0) -> dict[str, Any]:
    event = client.get("/v1/events", params={"status": "upcoming"}).json()[index]
    created = client.post(
        "/v1/community/picks",
        json={"event_id": event["id"], "market": "moneyline", "outcome_key": "home"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    return created.json()  # type: ignore[no-any-return]


def test_every_community_route_requires_a_token(make_app: AppFactory) -> None:
    with TestClient(community_app(make_app)) as client:
        admin = admin_headers(client, "boss@example.test")
        set_flag(client, admin, "community", True)
        set_flag(client, admin, "community_leaderboard", True)
        schema = client.get("/openapi.json").json()
        checked = 0
        for path, item in schema["paths"].items():
            if not path.startswith(("/v1/community", "/v1/admin/community")):
                continue
            for method in item:
                if path == "/v1/community/guidelines":
                    assert client.get(path).status_code == 200  # the one public route
                    continue
                url = path.replace("{", "").replace("}", "")
                response = client.request(method.upper(), url, json={})
                assert response.status_code == 401, (method, path, response.status_code)
                assert response.json()["error"]["code"] == "not_authenticated", path
                assert response.headers["www-authenticate"] == "Bearer"
                forged = client.request(method.upper(), url, json={}, headers=bearer("x.y.z"))
                assert forged.status_code == 401, (method, path)
                checked += 1
        assert checked == 25


def test_community_idor_on_picks_and_comments(make_app: AppFactory) -> None:
    with TestClient(community_app(make_app)) as client:
        set_flag(client, admin_headers(client, "boss@example.test"), "community", True)
        a, b = community_member(client, "owner_a"), community_member(client, "other_b")
        pick = community_pick(client, a)
        comment = client.post(
            f"/v1/community/picks/{pick['id']}/comments", json={"body": "mine"}, headers=a
        ).json()

        # B cannot delete A's pick or A's comment, by id or by any other route.
        refused = client.delete(f"/v1/community/picks/{pick['id']}", headers=b)
        assert refused.status_code == 403 and refused.json()["error"]["code"] == "forbidden"
        refused = client.delete(f"/v1/community/comments/{comment['id']}", headers=b)
        assert refused.status_code == 403 and refused.json()["error"]["code"] == "forbidden"
        # There is no route to edit a pick or a comment at all.
        for method in ("PUT", "PATCH", "POST"):
            edited = client.request(
                method,
                f"/v1/community/picks/{pick['id']}",
                json={"result": "won", "price": 99},
                headers=a,
            )
            assert edited.status_code == 405, method
            edited = client.request(
                method, f"/v1/community/comments/{comment['id']}", json={"body": "x"}, headers=b
            )
            assert edited.status_code == 405, method
        # B cannot post in A's name, and ids in the body are refused, not ignored.
        a_id = client.get("/v1/me", headers=a).json()["id"]
        event = client.get("/v1/events", params={"status": "upcoming"}).json()[1]
        injected = client.post(
            "/v1/community/picks",
            json={
                "event_id": event["id"],
                "market": "moneyline",
                "outcome_key": "home",
                "user_id": a_id,
                "author": {"handle": "owner_a"},
            },
            headers=b,
        )
        assert injected.status_code == 422
        injected = client.post(
            f"/v1/community/picks/{pick['id']}/comments",
            json={"body": "hi", "user_id": a_id, "author": "owner_a"},
            headers=b,
        )
        assert injected.status_code == 422
        own = client.post(
            f"/v1/community/picks/{pick['id']}/comments", json={"body": "by b"}, headers=b
        ).json()
        assert own["author"] == {"handle": "other_b"}
        # Everything of A's is intact.
        assert client.get(f"/v1/community/picks/{pick['id']}", headers=a).status_code == 200
        bodies = [
            c["body"]
            for c in client.get(f"/v1/community/picks/{pick['id']}/comments", headers=a).json()[
                "items"
            ]
        ]
        assert sorted(bodies) == ["by b", "mine"]


def test_community_idor_on_blocks_follows_and_likes(make_app: AppFactory) -> None:
    with TestClient(community_app(make_app)) as client:
        set_flag(client, admin_headers(client, "boss@example.test"), "community", True)
        a, b, c = (community_member(client, handle) for handle in ("owner_a", "other_b", "third_c"))
        pick = community_pick(client, c)
        client.put("/v1/community/blocks/other_b", headers=a)
        client.post("/v1/community/follows/third_c", headers=a)
        client.put(f"/v1/community/picks/{pick['id']}/like", headers=a)

        # Each list is the caller's own; there is no way to ask for someone else's.
        assert client.get("/v1/community/blocks", headers=b).json() == {"items": []}
        assert client.get("/v1/community/blocks", headers=c).json() == {"items": []}
        assert client.get("/v1/community/following", headers=b).json() == {"items": []}
        for extra in ({"handle": "owner_a"}, {"user_id": "x"}, {"blocker": "owner_a"}):
            listed = client.get("/v1/community/blocks", params=extra, headers=b).json()
            assert listed == {"items": []}
        # B and C cannot lift A's block, undo A's follow or remove A's like.
        assert client.delete("/v1/community/blocks/other_b", headers=b).status_code == 204
        assert client.delete("/v1/community/blocks/other_b", headers=c).status_code == 204
        assert client.delete("/v1/community/blocks/owner_a", headers=b).status_code == 204
        assert client.delete("/v1/community/follows/third_c", headers=c).status_code == 204
        assert client.delete(f"/v1/community/picks/{pick['id']}/like", headers=c).status_code == 200
        blocks = client.get("/v1/community/blocks", headers=a).json()["items"]
        assert [entry["handle"] for entry in blocks] == ["other_b"]
        following = client.get("/v1/community/following", headers=a).json()["items"]
        assert [entry["handle"] for entry in following] == ["third_c"]
        liked = client.get(f"/v1/community/picks/{pick['id']}", headers=a).json()
        assert (liked["liked_by_me"], liked["like_count"]) == (True, 1)
        # The block still holds for B.
        assert client.get("/v1/community/profiles/owner_a", headers=b).status_code == 404


def test_community_reports_are_private_and_moderation_is_admin_only(
    make_app: AppFactory,
) -> None:
    with TestClient(community_app(make_app)) as client:
        admin = admin_headers(client, "boss@example.test")
        set_flag(client, admin, "community", True)
        a, b = community_member(client, "owner_a"), community_member(client, "other_b")
        pick = community_pick(client, a)
        report = client.post(
            "/v1/community/reports",
            json={"target_type": "pick", "target_id": pick["id"], "reason": "spam"},
            headers=b,
        )
        assert report.status_code == 201
        report_id = report.json()["id"]

        # A report cannot be read, listed, changed or deleted through the user routes.
        for method in ("GET", "PUT", "PATCH", "DELETE"):
            for who in (a, b):
                response = client.request(
                    method, f"/v1/community/reports/{report_id}", json={}, headers=who
                )
                assert response.status_code in (404, 405), method
        assert client.get("/v1/community/reports", headers=a).status_code == 405
        # The reported person learns nothing: not from their pick, not from notifications.
        assert "report" not in client.get(f"/v1/community/picks/{pick['id']}", headers=a).text
        assert client.get("/v1/notifications", headers=a).json()["items"] == []
        # A non-admin cannot reach moderation, whatever role the request claims.
        for who in (a, b):
            for method, path, body in (
                ("GET", "/v1/admin/community/reports", None),
                ("GET", "/v1/admin/community/overview", None),
                (
                    "POST",
                    f"/v1/admin/community/reports/{report_id}/resolve",
                    {"action": "dismiss", "note": "self-service", "role": "admin"},
                ),
            ):
                response = client.request(method, path, json=body, headers=who)
                assert response.status_code == 403, path
        b_id = client.get("/v1/me", headers=b).json()["id"]
        forged = jwt.encode(claims(b_id, role="admin"), DEV_JWT_SECRET, algorithm="HS256")
        assert client.get("/v1/admin/community/reports", headers=bearer(forged)).status_code == 403
        with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
            (stored,) = db.scalars(select(CommunityReport)).all()
            assert (stored.status, stored.reporter_id) == ("open", b_id)
        # A report cannot be filed in someone else's name.
        injected = client.post(
            "/v1/community/reports",
            json={
                "target_type": "pick",
                "target_id": pick["id"],
                "reason": "spam",
                "reporter_id": client.get("/v1/me", headers=a).json()["id"],
            },
            headers=b,
        )
        assert injected.status_code == 422


def test_handle_enumeration_does_not_leak_emails_or_account_data(make_app: AppFactory) -> None:
    with TestClient(community_app(make_app)) as client:
        set_flag(client, admin_headers(client, "boss@example.test"), "community", True)
        viewer = community_member(client, "viewer_v")
        target = register(client, "very.private.address@example.test", display_name="Real Name")
        target_headers = bearer(target["access_token"])
        client.put(
            "/v1/community/profile",
            json={"handle": "public_p", "bio": "Totals.", "is_public": True},
            headers=target_headers,
        )
        pick = community_pick(client, target_headers)
        client.post("/v1/community/follows/public_p", headers=viewer)
        hidden = auth_headers(client, "hidden@example.test")
        client.put(
            "/v1/community/profile",
            json={"handle": "hidden_h", "is_public": False},
            headers=hidden,
        )
        secrets = (
            "very.private.address",
            "example.test",
            "Real Name",
            target["user"]["id"],
            "password",
            "premium",
            '"plan"',
            '"email"',
            '"display_name"',
            '"user_id"',
            '"role"',
        )
        pages = [
            client.get("/v1/community/profiles/public_p", headers=viewer),
            client.get("/v1/community/picks", params={"handle": "public_p"}, headers=viewer),
            client.get(f"/v1/community/picks/{pick['id']}", headers=viewer),
            client.get("/v1/community/feed", params={"scope": "everyone"}, headers=viewer),
            client.get("/v1/community/following", headers=viewer),
            client.get("/v1/community/followers", headers=target_headers),
        ]
        for page in pages:
            assert page.status_code == 200
            for secret in secrets:
                assert secret not in page.text, (secret, page.request.url)
        # Trying an email address, a user id or a name as the handle finds nothing, and a
        # handle that exists but is private answers exactly like one that does not.
        probes = (
            "very.private.address@example.test",
            "very.private.address",
            target["user"]["id"],
            "Real Name",
            "hidden_h",
            "nobody_at_all",
            "admin",
            "%",
            "_",
            "public_p%",
            "public_p' OR '1'='1",
        )
        answers = set()
        for probe in probes:
            response = client.get(f"/v1/community/profiles/{probe}", headers=viewer)
            assert response.status_code == 404, probe
            body = response.json()["error"]
            assert body["code"] == "not_found"
            answers.add(body["message"].replace(probe[:20], "<handle>"))
            for secret in ("example.test", "Real Name", target["user"]["id"]):
                assert secret not in response.text.replace(probe, ""), probe
        assert answers == {"Profile '<handle>' was not found"}
        # The same goes for following, blocking and reporting by handle.
        for method, path in (
            ("POST", "/v1/community/follows/hidden_h"),
            ("PUT", "/v1/community/blocks/hidden_h"),
            ("POST", "/v1/community/follows/nobody_at_all"),
            ("PUT", "/v1/community/blocks/nobody_at_all"),
        ):
            assert client.request(method, path, headers=viewer).status_code == 404, path
        for handle in ("hidden_h", "nobody_at_all"):
            reported = client.post(
                "/v1/community/reports",
                json={"target_type": "profile", "target_id": handle, "reason": "spam"},
                headers=viewer,
            )
            assert reported.status_code == 404
        # Taking a handle is the only thing that tells you it exists, public or not.
        taken = client.put(
            "/v1/community/profile", json={"handle": "hidden_h", "is_public": True}, headers=viewer
        )
        assert taken.status_code == 409 and "example.test" not in taken.text


def test_hostile_text_in_community_fields(make_app: AppFactory) -> None:
    with TestClient(community_app(make_app)) as client:
        set_flag(client, admin_headers(client, "boss@example.test"), "community", True)
        a = community_member(client, "owner_a")
        pick = community_pick(client, a)
        for payload in PAYLOADS:
            handle = client.put(
                "/v1/community/profile", json={"handle": payload[:64], "is_public": True}, headers=a
            )
            assert handle.status_code == 422, payload
            for path in (
                f"/v1/community/profiles/{payload[:20]}",
                f"/v1/community/picks/{payload[:20]}",
            ):
                assert client.get(path, headers=a).status_code in (404, 422), payload
            listed = client.get(
                "/v1/community/picks",
                params={"event_id": payload[:64], "league": payload[:32]},
                headers=a,
            )
            assert listed.status_code == 200 and listed.json()["items"] == [], payload
            comment = client.post(
                f"/v1/community/picks/{pick['id']}/comments",
                json={"body": payload[:500]},
                headers=a,
            )
            # Stored verbatim or refused by a content rule: never an error, never executed.
            assert comment.status_code in (201, 422), payload
            if comment.status_code == 201:
                assert comment.json()["body"] == payload[:500]
        assert client.get("/v1/community/profile", headers=a).json()["handle"] == "owner_a"
        assert client.get(f"/v1/community/picks/{pick['id']}", headers=a).status_code == 200
