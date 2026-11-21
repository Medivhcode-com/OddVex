"""Admin: users, suspension, plans, feature flags, audit log. Role ``admin`` only."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from oddvex_api.db import AuditLog, User

from .conftest import ADMIN_EMAIL, PASSWORD, admin_headers, auth_headers, register

Headers = dict[str, str]

ADMIN_CALLS: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", "/v1/admin/overview", None),
    ("GET", "/v1/admin/users", None),
    ("POST", "/v1/admin/users/{id}/suspend", {"reason": "testing"}),
    ("POST", "/v1/admin/users/{id}/unsuspend", None),
    ("PUT", "/v1/admin/users/{id}/plan", {"plan": "premium"}),
    ("POST", "/v1/admin/users/{id}/export", {"reason": "testing"}),
    (
        "POST",
        "/v1/admin/users/{id}/delete",
        {"reason": "testing", "confirm_email": "grace@example.test"},
    ),
    ("GET", "/v1/admin/flags", None),
    ("PUT", "/v1/admin/flags/community", {"enabled": True}),
    ("GET", "/v1/admin/audit", None),
    ("GET", "/v1/admin/email-outbox", None),
]
#: Behind the ``community`` flag: 404 for everyone while it is off (see
#: tests/test_api_community_moderation.py for the same checks with the flag on).
COMMUNITY_ADMIN_ROUTES = {
    ("GET", "/v1/admin/community/overview"),
    ("GET", "/v1/admin/community/reports"),
    ("POST", "/v1/admin/community/reports/{report_id}/resolve"),
    ("POST", "/v1/admin/community/restore"),
}


def me(client: TestClient, headers: Headers) -> dict[str, Any]:
    return client.get("/v1/me", headers=headers).json()  # type: ignore[no-any-return]


def login(client: TestClient, email: str, password: str = PASSWORD) -> Any:
    return client.post("/v1/auth/login", json={"email": email, "password": password})


def audit_rows(client: TestClient, action: str) -> list[AuditLog]:
    app: FastAPI = client.app  # type: ignore[assignment]
    with app.state.session_factory() as db:
        return list(
            db.scalars(
                select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.created_at)
            )
        )


# ---------------------------------------------------------------------- authz
def test_every_admin_route_is_403_for_a_user_and_401_without_a_token(
    admin_client: TestClient,
) -> None:
    admin_headers(admin_client)
    user = auth_headers(admin_client)
    victim = me(admin_client, auth_headers(admin_client, "grace@example.test"))
    schema = admin_client.get("/openapi.json").json()
    documented = {
        (method.upper(), path)
        for path, item in schema["paths"].items()
        for method in item
        if path.startswith("/v1/admin")
    }
    assert documented - COMMUNITY_ADMIN_ROUTES == {
        (method, path.replace("{id}", "{user_id}").replace("/flags/community", "/flags/{key}"))
        for method, path, _ in ADMIN_CALLS
    }, "every admin route is covered by this test"
    assert documented >= COMMUNITY_ADMIN_ROUTES
    for method, template, body in ADMIN_CALLS:
        path = template.replace("{id}", victim["id"])
        anonymous = admin_client.request(method, path, json=body)
        assert anonymous.status_code == 401, path
        assert anonymous.json()["error"]["code"] == "not_authenticated"
        forbidden = admin_client.request(method, path, json=body, headers=user)
        assert forbidden.status_code == 403, path
        assert forbidden.json() == {
            "error": {"code": "forbidden", "message": "Administrator role required"}
        }
    # Nothing a non-admin tried had any effect.
    with admin_client.app.state.session_factory() as db:  # type: ignore[attr-defined]
        grace = db.get(User, victim["id"])
        assert (grace.plan, grace.status) == ("free", "active")
    assert admin_client.get("/v1/flags").json()["flags"]["community"] is False
    assert not audit_rows(admin_client, "admin.user_suspended")
    assert not audit_rows(admin_client, "admin.user_exported")
    assert not audit_rows(admin_client, "admin.user_deleted")
    assert not audit_rows(admin_client, "account.deleted")


# ---------------------------------------------------------------------- users
def test_list_users_filters_and_never_leaks_secrets(admin_client: TestClient) -> None:
    admin = admin_headers(admin_client)
    ada = auth_headers(admin_client, "ada@example.test")
    grace = auth_headers(admin_client, "grace@example.test")
    bet = {
        "bet_type": "straight",
        "stake": 10,
        "sportsbook": "Northline",
        "legs": [{"selection": "x", "market": "moneyline", "odds": -110}],
    }
    for _ in range(2):
        assert admin_client.post("/v1/bets", json=bet, headers=ada).status_code == 201
    grace_id = me(admin_client, grace)["id"]
    admin_client.put(f"/v1/admin/users/{grace_id}/plan", json={"plan": "premium"}, headers=admin)
    admin_client.post(
        f"/v1/admin/users/{grace_id}/suspend", json={"reason": "testing"}, headers=admin
    )

    response = admin_client.get("/v1/admin/users", headers=admin)
    assert response.status_code == 200
    body = response.json()
    assert (body["total"], body["limit"], body["offset"]) == (3, 50, 0)
    assert [u["email"] for u in body["items"]] == [
        "grace@example.test",
        "ada@example.test",
        ADMIN_EMAIL,
    ]  # newest first
    by_email = {u["email"]: u for u in body["items"]}
    assert set(by_email["ada@example.test"]) == {
        "id",
        "email",
        "display_name",
        "role",
        "plan",
        "status",
        "email_verified",
        "created_at",
        "last_login_at",
        "bet_count",
    }
    assert by_email["ada@example.test"]["bet_count"] == 2
    assert by_email["ada@example.test"]["last_login_at"] is not None
    assert by_email["grace@example.test"]["bet_count"] == 0
    assert (by_email["grace@example.test"]["plan"], by_email["grace@example.test"]["status"]) == (
        "premium",
        "suspended",
    )
    assert by_email[ADMIN_EMAIL]["role"] == "admin"
    text = response.text
    for secret in ("password", "hash", "argon2", "token"):
        assert secret not in text.lower(), secret

    def emails(**params: Any) -> list[str]:
        result = admin_client.get("/v1/admin/users", params=params, headers=admin)
        assert result.status_code == 200, result.text
        return [u["email"] for u in result.json()["items"]]

    assert emails(q="GRACE") == ["grace@example.test"]
    assert emails(q="ada@") == ["ada@example.test"]
    assert len(emails(q="ADA")) == 3  # every test user's display name is "Ada"
    assert emails(q="example.test") == ["grace@example.test", "ada@example.test", ADMIN_EMAIL]
    assert emails(q="%") == [] and emails(q="_") == []  # LIKE wildcards are literals
    assert emails(status="suspended") == ["grace@example.test"]
    assert emails(status="active") == ["ada@example.test", ADMIN_EMAIL]
    assert emails(plan="premium") == ["grace@example.test"]
    assert emails(plan="free", status="active", q="boss") == [ADMIN_EMAIL]
    assert emails(limit=1) == ["grace@example.test"]
    assert emails(limit=1, offset=1) == ["ada@example.test"]
    assert emails(offset=5) == []
    paged = admin_client.get("/v1/admin/users", params={"limit": 1}, headers=admin).json()
    assert paged["total"] == 3 and paged["limit"] == 1
    for bad in ({"status": "deleted"}, {"plan": "gold"}, {"limit": 0}, {"offset": -1}):
        invalid = admin_client.get("/v1/admin/users", params=bad, headers=admin)
        assert invalid.status_code == 422, bad
        assert invalid.json()["error"]["code"] == "validation_error"


def test_display_name_search(admin_client: TestClient) -> None:
    admin = admin_headers(admin_client)
    register(admin_client, "one@example.test", display_name="Zebra Finch")
    found = admin_client.get("/v1/admin/users", params={"q": "zebra"}, headers=admin).json()
    assert [u["email"] for u in found["items"]] == ["one@example.test"]


def test_last_login_at_is_updated_on_login(admin_client: TestClient) -> None:
    admin = admin_headers(admin_client)
    auth_headers(admin_client)

    def last_login() -> str:
        items = admin_client.get("/v1/admin/users", params={"q": "ada@"}, headers=admin).json()
        return items["items"][0]["last_login_at"]  # type: ignore[no-any-return]

    first = last_login()
    assert login(admin_client, "ada@example.test", "wrong-password-1").status_code == 401
    assert last_login() == first  # a failed login does not count
    assert login(admin_client, "ada@example.test").status_code == 200
    assert last_login() > first


# ----------------------------------------------------------------- suspension
def test_suspend_rejects_tokens_and_login_then_unsuspend_restores(
    admin_client: TestClient,
) -> None:
    admin = admin_headers(admin_client)
    admin_id = me(admin_client, admin)["id"]
    victim = auth_headers(admin_client, "grace@example.test")
    victim_id = me(admin_client, victim)["id"]

    suspended = admin_client.post(
        f"/v1/admin/users/{victim_id}/suspend",
        json={"reason": "  Chargeback dispute  "},
        headers=admin,
    )
    assert suspended.status_code == 200, suspended.text
    assert suspended.json()["status"] == "suspended" and suspended.json()["id"] == victim_id

    # The token that worked a moment ago is rejected everywhere, except on the two
    # data-rights routes (tests/test_api_account.py covers those).
    for path in ("/v1/me", "/v1/bets", "/v1/notifications", "/v1/alerts"):
        rejected = admin_client.get(path, headers=victim)
        assert rejected.status_code == 401, path
        assert rejected.json()["error"]["code"] == "account_suspended"
        assert rejected.headers["www-authenticate"] == "Bearer"
    # Login: neutral message, no token, and only after the right password.
    blocked = login(admin_client, "grace@example.test")
    assert blocked.status_code == 403
    assert blocked.json() == {
        "error": {
            "code": "account_suspended",
            "message": "This account can't be used right now. Contact support.",
        }
    }
    assert "access_token" not in blocked.text and "Chargeback" not in blocked.text
    wrong = login(admin_client, "grace@example.test", "not-the-password")
    assert wrong.status_code == 401 and wrong.json()["error"]["code"] == "invalid_credentials"

    # Audited with actor, target, before/after and the reason.
    (entry,) = audit_rows(admin_client, "admin.user_suspended")
    assert (entry.user_id, entry.entity_type, entry.entity_id) == (admin_id, "user", victim_id)
    assert entry.details == {
        "before": {"status": "active"},
        "after": {"status": "suspended"},
        "reason": "Chargeback dispute",
    }
    assert entry.request_id
    # Suspending again changes nothing and adds no audit entry.
    again = admin_client.post(
        f"/v1/admin/users/{victim_id}/suspend", json={"reason": "again"}, headers=admin
    )
    assert again.status_code == 200 and again.json()["status"] == "suspended"
    assert len(audit_rows(admin_client, "admin.user_suspended")) == 1

    restored = admin_client.post(f"/v1/admin/users/{victim_id}/unsuspend", headers=admin)
    assert restored.status_code == 200 and restored.json()["status"] == "active"
    assert admin_client.get("/v1/me", headers=victim).status_code == 200  # same token
    assert login(admin_client, "grace@example.test").status_code == 200
    (lifted,) = audit_rows(admin_client, "admin.user_unsuspended")
    assert (lifted.user_id, lifted.entity_id) == (admin_id, victim_id)
    assert lifted.details == {"before": {"status": "suspended"}, "after": {"status": "active"}}
    admin_client.post(f"/v1/admin/users/{victim_id}/unsuspend", headers=admin)
    assert len(audit_rows(admin_client, "admin.user_unsuspended")) == 1


def test_an_admin_cannot_suspend_themselves_or_another_admin(make_app) -> None:  # type: ignore[no-untyped-def]
    app = make_app(admin_emails=f"{ADMIN_EMAIL}, chief@example.test")
    with TestClient(app) as client:
        boss = admin_headers(client, ADMIN_EMAIL)
        chief = admin_headers(client, "chief@example.test")
        boss_id, chief_id = me(client, boss)["id"], me(client, chief)["id"]

        own = client.post(
            f"/v1/admin/users/{boss_id}/suspend", json={"reason": "oops"}, headers=boss
        )
        assert own.status_code == 409 and own.json()["error"]["code"] == "cannot_suspend_self"
        other = client.post(
            f"/v1/admin/users/{chief_id}/suspend", json={"reason": "coup"}, headers=boss
        )
        assert other.status_code == 409
        assert other.json()["error"]["code"] == "cannot_suspend_admin"
        assert client.get("/v1/me", headers=boss).status_code == 200
        assert client.get("/v1/me", headers=chief).status_code == 200
        assert not audit_rows(client, "admin.user_suspended")


def test_suspend_validation_and_unknown_user(admin_client: TestClient) -> None:
    admin = admin_headers(admin_client)
    victim_id = me(admin_client, auth_headers(admin_client))["id"]
    for body in ({}, {"reason": ""}, {"reason": "  a "}, {"reason": "x" * 501}):
        invalid = admin_client.post(
            f"/v1/admin/users/{victim_id}/suspend", json=body, headers=admin
        )
        assert invalid.status_code == 422, body
        assert invalid.json()["error"]["code"] == "validation_error"
    for method, path, body in (
        ("POST", "/v1/admin/users/nope/suspend", {"reason": "testing"}),
        ("POST", "/v1/admin/users/nope/unsuspend", None),
        ("PUT", "/v1/admin/users/nope/plan", {"plan": "premium"}),
    ):
        missing = admin_client.request(method, path, json=body, headers=admin)
        assert missing.status_code == 404, path
        assert missing.json()["error"]["code"] == "not_found"


# ----------------------------------------------------------------------- plan
def test_set_plan_is_audited_with_before_and_after(admin_client: TestClient) -> None:
    admin = admin_headers(admin_client)
    admin_id = me(admin_client, admin)["id"]
    user = auth_headers(admin_client)
    user_id = me(admin_client, user)["id"]

    premium = admin_client.put(
        f"/v1/admin/users/{user_id}/plan", json={"plan": "premium"}, headers=admin
    )
    assert premium.status_code == 200 and premium.json()["plan"] == "premium"
    assert me(admin_client, user)["plan"] == "premium"
    assert admin_client.get("/v1/me/entitlements", headers=user).json()["plan"] == "premium"
    same = admin_client.put(
        f"/v1/admin/users/{user_id}/plan", json={"plan": "premium"}, headers=admin
    )
    assert same.status_code == 200
    free = admin_client.put(f"/v1/admin/users/{user_id}/plan", json={"plan": "free"}, headers=admin)
    assert free.json()["plan"] == "free"

    entries = audit_rows(admin_client, "admin.user_plan_set")
    assert [e.details for e in entries] == [
        {"before": {"plan": "free"}, "after": {"plan": "premium"}},
        {"before": {"plan": "premium"}, "after": {"plan": "free"}},
    ]
    assert {(e.user_id, e.entity_type, e.entity_id) for e in entries} == {
        (admin_id, "user", user_id)
    }
    for body in ({"plan": "gold"}, {}, {"plan": None}):
        invalid = admin_client.put(f"/v1/admin/users/{user_id}/plan", json=body, headers=admin)
        assert invalid.status_code == 422, body


def test_a_user_cannot_change_their_own_plan(client: TestClient, headers: Headers) -> None:
    user_id = me(client, headers)["id"]
    response = client.put(
        f"/v1/admin/users/{user_id}/plan", json={"plan": "premium"}, headers=headers
    )
    assert response.status_code == 403
    assert me(client, headers)["plan"] == "free"


# ---------------------------------------------------------------------- flags
def test_admin_flags_list_and_set(admin_client: TestClient) -> None:
    admin = admin_headers(admin_client)
    admin_id = me(admin_client, admin)["id"]
    listed = admin_client.get("/v1/admin/flags", headers=admin).json()["items"]
    assert [f["key"] for f in listed] == [
        "community",
        "community_leaderboard",
        "value_screen",
        "tracker_analytics",
        "email_flows",
        "premium_gating",
    ]
    community = listed[0]
    assert community == {
        "key": "community",
        "description": community["description"],
        "enabled": False,
        "default": False,
        "overridden": False,
        "updated_at": None,
    }
    assert all(f["description"] and not f["overridden"] for f in listed)
    by_key = {f["key"]: f for f in listed}
    assert "Founder approval" in by_key["premium_gating"]["description"]
    assert "responsible-gambling review" in by_key["community_leaderboard"]["description"]
    assert by_key["email_flows"]["default"] is True  # not production

    on = admin_client.put("/v1/admin/flags/community", json={"enabled": True}, headers=admin)
    assert on.status_code == 200
    assert (on.json()["enabled"], on.json()["default"], on.json()["overridden"]) == (
        True,
        False,
        True,
    )
    assert on.json()["updated_at"] is not None
    assert admin_client.get("/v1/flags").json()["flags"]["community"] is True
    listed = admin_client.get("/v1/admin/flags", headers=admin).json()["items"]
    assert listed[0]["enabled"] is True and listed[0]["overridden"] is True

    off = admin_client.put("/v1/admin/flags/community", json={"enabled": False}, headers=admin)
    assert off.json()["enabled"] is False and off.json()["overridden"] is True
    assert admin_client.get("/v1/flags").json()["flags"]["community"] is False

    entries = audit_rows(admin_client, "admin.flag_set")
    assert [(e.user_id, e.entity_type, e.entity_id) for e in entries] == [
        (admin_id, "feature_flag", "community")
    ] * 2
    assert [e.details for e in entries] == [
        {"before": {"enabled": False}, "after": {"enabled": True}},
        {"before": {"enabled": True}, "after": {"enabled": False}},
    ]


def test_set_flag_unknown_key_and_bad_body(admin_client: TestClient) -> None:
    admin = admin_headers(admin_client)
    unknown = admin_client.put("/v1/admin/flags/teleport", json={"enabled": True}, headers=admin)
    assert unknown.status_code == 404
    assert unknown.json() == {
        "error": {"code": "not_found", "message": "Feature flag 'teleport' was not found"}
    }
    assert "teleport" not in admin_client.get("/v1/flags").json()["flags"]
    for body in ({}, {"enabled": "maybe"}, {"enabled": None}):
        invalid = admin_client.put("/v1/admin/flags/community", json=body, headers=admin)
        assert invalid.status_code == 422, body
    assert not audit_rows(admin_client, "admin.flag_set")


# ---------------------------------------------------------------------- audit
def test_audit_log_filters_and_cursor(admin_client: TestClient) -> None:
    admin = admin_headers(admin_client)
    admin_id = me(admin_client, admin)["id"]
    ada = auth_headers(admin_client)
    ada_id = me(admin_client, ada)["id"]
    admin_client.put("/v1/admin/flags/community", json={"enabled": True}, headers=admin)
    admin_client.put(f"/v1/admin/users/{ada_id}/plan", json={"plan": "premium"}, headers=admin)
    admin_client.post(f"/v1/admin/users/{ada_id}/suspend", json={"reason": "why"}, headers=admin)
    admin_client.post(f"/v1/admin/users/{ada_id}/unsuspend", headers=admin)

    def page(**params: Any) -> dict[str, Any]:
        response = admin_client.get("/v1/admin/audit", params=params, headers=admin)
        assert response.status_code == 200, response.text
        return response.json()  # type: ignore[no-any-return]

    everything = page(limit=200)
    assert everything["next_before"] is None
    actions = [e["action"] for e in everything["items"]]
    assert actions == [
        "admin.user_unsuspended",
        "admin.user_suspended",
        "admin.user_plan_set",
        "admin.flag_set",
        "auth.register",
        # The administrator: registered, confirmed the address, and only then got the role.
        "role.granted",
        "auth.email_verified",
        "auth.register",
    ]  # newest first
    assert set(everything["items"][0]) == {
        "id",
        "created_at",
        "action",
        "user_id",
        "entity_type",
        "entity_id",
        "request_id",
        "details",
    }
    assert "example.test" not in str(everything)  # no email addresses in the trail

    assert [e["action"] for e in page(action="admin.flag_set")["items"]] == ["admin.flag_set"]
    assert page(action="nothing.like.this")["items"] == []
    # By user: what Ada did and what was done to Ada.
    assert [e["action"] for e in page(user_id=ada_id)["items"]] == [
        "admin.user_unsuspended",
        "admin.user_suspended",
        "admin.user_plan_set",
        "auth.register",
    ]
    # The administrator: register, email confirmed, role granted, then the four changes.
    assert len(page(user_id=admin_id)["items"]) == 7
    assert [e["action"] for e in page(user_id=ada_id, action="auth.register")["items"]] == [
        "auth.register"
    ]

    # Cursor: four pages of two, no overlap, no gap.
    seen: list[str] = []
    cursor: str | None = None
    for expected_more in (True, True, True, False):
        params: dict[str, Any] = {"limit": 2}
        if cursor:
            params["before"] = cursor
        chunk = page(**params)
        assert len(chunk["items"]) == 2
        seen += [e["id"] for e in chunk["items"]]
        cursor = chunk["next_before"]
        assert (cursor is not None) == expected_more
    assert seen == [e["id"] for e in everything["items"]]

    for bad in ("garbage", "12-", "-abc", "9" * 30 + "-x"):
        invalid = admin_client.get("/v1/admin/audit", params={"before": bad}, headers=admin)
        assert invalid.status_code == 422, bad
        assert invalid.json()["error"]["code"] == "invalid_cursor"
    assert (
        admin_client.get("/v1/admin/audit", params={"limit": 0}, headers=admin).status_code == 422
    )


@pytest.mark.parametrize("limit", [1, 3])
def test_email_outbox_for_admins_shows_no_bodies_links_or_tokens(
    admin_client: TestClient, limit: int
) -> None:
    admin = admin_headers(admin_client)
    auth_headers(admin_client, "ada@example.test")
    admin_client.post("/v1/auth/password-reset/request", json={"email": "ada@example.test"})
    response = admin_client.get("/v1/admin/email-outbox", params={"limit": limit}, headers=admin)
    assert response.status_code == 200
    body = response.json()
    assert body["delivery"] == "outbox"
    assert len(body["items"]) == limit
    newest = body["items"][0]
    assert set(newest) == {"id", "user_id", "to", "template", "subject", "created_at"}
    assert (newest["to"], newest["template"]) == ("ada@example.test", "password_reset")
    assert newest["subject"] == "Reset your OddVex password"
    if limit == 3:
        assert [i["template"] for i in body["items"]] == [
            "password_reset",
            "verify_email",
            "verify_email",
        ]
    for leak in ("token=", "http", "body", "link"):
        assert leak not in response.text, leak
    assert (
        admin_client.get("/v1/admin/email-outbox", params={"limit": 0}, headers=admin).status_code
        == 422
    )
