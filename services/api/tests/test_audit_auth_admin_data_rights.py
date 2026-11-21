"""Administrator export and delete of a user's account.

Staff must be able to meet a data request for an account whose owner cannot sign in: a
suspended account, an account closed because its owner is under 21, a lost password.
Before, the only tools were the owner's own two routes, which need the owner's token.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from oddvex_api.account import service as account_service
from oddvex_api.db import AuditLog, Base, User

from .conftest import ADMIN_EMAIL, PASSWORD, AppFactory, admin_headers, auth_headers, register

Headers = dict[str, str]
EMAIL = "grace@example.test"
REASON = "Request DSR-2026-014, received by post"
NOTE = "a-private-note-of-the-owner"


def me(client: TestClient, headers: Headers) -> dict[str, Any]:
    return client.get("/v1/me", headers=headers).json()  # type: ignore[no-any-return]


def audit_rows(client: TestClient, action: str | None = None) -> list[AuditLog]:
    app: FastAPI = client.app  # type: ignore[assignment]
    query = select(AuditLog).order_by(AuditLog.created_at, AuditLog.id)
    if action is not None:
        query = query.where(AuditLog.action == action)
    with app.state.session_factory() as db:
        return list(db.scalars(query))


def populate(client: TestClient, headers: Headers) -> None:
    """One of everything an account can own outside the community."""
    bet = {
        "bet_type": "straight",
        "stake": 25,
        "sportsbook": "Northline",
        "notes": NOTE,
        "legs": [{"selection": "Harbor City Tides ML", "market": "moneyline", "odds": -110}],
    }
    assert client.post("/v1/bets", json=bet, headers=headers).status_code == 201
    team_id = client.get("/v1/events").json()[0]["home_team"]["id"]
    watched = client.post(
        "/v1/watchlist", json={"kind": "team", "ref_id": team_id}, headers=headers
    )
    assert watched.status_code == 201
    connection = client.post("/v1/sync/connections", json={"provider": "mock"}, headers=headers)
    assert connection.status_code == 201
    synced = client.post(f"/v1/sync/connections/{connection.json()['id']}/sync", headers=headers)
    assert synced.status_code in (200, 201), synced.text
    alert = client.post(
        "/v1/alerts",
        json={"kind": "game_start", "team_id": team_id, "minutes_before": 60},
        headers=headers,
    )
    assert alert.status_code == 201, alert.text
    assert (
        client.put(
            "/v1/me/stake-reminder", json={"weekly_stake_threshold": 100}, headers=headers
        ).status_code
        == 200
    )
    assert client.post("/v1/auth/password-reset/request", json={"email": EMAIL}).status_code == 202


def rows_of_user(client: TestClient, user_id: str) -> dict[str, int]:
    """How many rows each table holds for the user, the audit log left out."""
    app: FastAPI = client.app  # type: ignore[assignment]
    counts: dict[str, int] = {}
    with app.state.session_factory() as db:
        for table in Base.metadata.sorted_tables:
            if table.name == "audit_log":
                continue
            columns = [
                column
                for column in table.columns
                if any(key.column.table.name == "users" for key in column.foreign_keys)
                or (table.name == "users" and column.name == "id")
            ]
            for column in columns:
                found = db.scalar(select(func.count()).select_from(table).where(column == user_id))
                if found:
                    counts[f"{table.name}.{column.name}"] = int(found)
    return counts


def suspend(client: TestClient, admin: Headers, user_id: str) -> None:
    response = client.post(
        f"/v1/admin/users/{user_id}/suspend", json={"reason": "under 21"}, headers=admin
    )
    assert response.status_code == 200, response.text


@pytest.fixture
def world(admin_client: TestClient) -> tuple[TestClient, Headers, Headers, str]:
    """An administrator, and a user with data: ``(client, admin, user, user id)``."""
    admin = admin_headers(admin_client)
    user = auth_headers(admin_client, EMAIL)
    populate(admin_client, user)
    return admin_client, admin, user, me(admin_client, user)["id"]


# --------------------------------------------------------------------- export
@pytest.mark.parametrize("suspended", [False, True])
def test_admin_export_is_the_owners_export(
    world: tuple[TestClient, Headers, Headers, str], suspended: bool
) -> None:
    client, admin, user, user_id = world
    if suspended:
        suspend(client, admin, user_id)
    # The owner's own export first (a suspended account can still make it).
    own = client.get("/v1/me/export", headers=user)
    assert own.status_code == 200
    before = len(audit_rows(client))

    response = client.post(
        f"/v1/admin/users/{user_id}/export", json={"reason": f"  {REASON} "}, headers=admin
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert "content-length" not in response.headers  # streamed, like the owner's
    assert response.headers["cache-control"] == "no-store"
    document = response.json()
    mine = own.json()
    assert list(document) == list(mine)
    assert document.pop("exported_at") >= mine.pop("exported_at")
    # Same code, same document: every part, the owner's audit entries included. The
    # administrator's export is recorded under the administrator, not in the owner's log.
    assert document == mine
    assert document["user"]["email"] == EMAIL
    assert [bet["notes"] for bet in document["bets"] if bet["notes"]] == [NOTE]
    assert len(document["watchlist"]) == 1 and len(document["sync_connections"]) == 1
    assert "password_hash" not in response.text and "$argon2" not in response.text

    (entry,) = audit_rows(client)[before:]
    assert entry.action == "admin.user_exported"
    assert (entry.user_id, entry.entity_type, entry.entity_id) == (
        me(client, admin)["id"],
        "user",
        user_id,
    )
    assert entry.details == {
        "reason": REASON,
        "account_status": "suspended" if suspended else "active",
    }
    # Nothing of the exported data is in the entry.
    assert NOTE not in json.dumps(entry.details) and EMAIL not in json.dumps(entry.details)
    # The account is as it was.
    with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
        assert db.get(User, user_id).status == ("suspended" if suspended else "active")


def test_admin_export_gives_its_stream_slot_back(
    make_app: AppFactory,
) -> None:
    app = make_app(admin_emails=ADMIN_EMAIL, rate_limit_enabled=True, rate_limit_auth_per_minute=99)
    with TestClient(app) as client:
        admin = admin_headers(client)
        user_id = me(client, auth_headers(client, EMAIL))["id"]
        admin_id = me(client, admin)["id"]
        # More exports than one account may make of its own data in an hour, and more
        # than the streams one account may have in progress: each one ends first.
        for _ in range(12):
            response = client.post(
                f"/v1/admin/users/{user_id}/export", json={"reason": REASON}, headers=admin
            )
            assert response.status_code == 200
            assert response.json()["user"]["id"] == user_id
        assert app.state.user_in_progress["streams"].active(admin_id) == 0
        # A refused request holds no slot either.
        for _ in range(12):
            missing = client.post(
                "/v1/admin/users/nobody/export", json={"reason": REASON}, headers=admin
            )
            assert missing.status_code == 404
        assert app.state.user_in_progress["streams"].active(admin_id) == 0
        assert len(audit_rows(client, "admin.user_exported")) == 12


# --------------------------------------------------------------------- delete
@pytest.mark.parametrize("suspended", [False, True])
def test_admin_delete_removes_what_the_owners_own_delete_removes(
    world: tuple[TestClient, Headers, Headers, str], suspended: bool
) -> None:
    client, admin, user, user_id = world
    # A second account with the same data, deleted by its owner, to compare with.
    other = auth_headers(client, "twin@example.test")
    populate(client, other)
    other_id = me(client, other)["id"]
    if suspended:
        suspend(client, admin, user_id)
        suspend(client, admin, other_id)
    held = rows_of_user(client, user_id)
    assert held["users.id"] == 1 and held["bets.user_id"] >= 1
    assert {"watchlist_items.user_id", "sync_connections.user_id", "alert_rules.user_id"} <= set(
        held
    )

    assert client.delete("/v1/me", headers=other).status_code == 204
    before = len(audit_rows(client))
    response = client.post(
        f"/v1/admin/users/{user_id}/delete",
        json={"reason": REASON, "confirm_email": EMAIL},
        headers=admin,
    )
    assert response.status_code == 204, response.text
    assert response.content == b""
    # Nothing is left of either account, in any table.
    assert rows_of_user(client, user_id) == {} == rows_of_user(client, other_id)

    # The retained entry is the one the owner's own delete leaves.
    (own_entry,) = [row for row in audit_rows(client, "account.deleted") if row.user_id == other_id]
    retained, by_admin = audit_rows(client)[before:]
    assert retained.action == "account.deleted"
    assert (retained.user_id, retained.entity_type, retained.entity_id, retained.details) == (
        user_id,
        own_entry.entity_type,
        user_id,
        own_entry.details,
    )
    assert own_entry.details == ({"account_status": "suspended"} if suspended else None)
    # And one more names the administrator, the opaque id and the reason.
    assert by_admin.action == "admin.user_deleted"
    assert (by_admin.user_id, by_admin.entity_type, by_admin.entity_id) == (
        me(client, admin)["id"],
        "user",
        user_id,
    )
    assert by_admin.details == {
        "reason": REASON,
        "account_status": "suspended" if suspended else "active",
    }
    for entry in (retained, by_admin):
        assert EMAIL not in json.dumps(entry.details) and "grace" not in json.dumps(entry.details)

    # The owner's token and password are gone with the account; the address is free.
    assert client.get("/v1/me", headers=user).status_code == 401
    assert client.get("/v1/me/export", headers=user).status_code == 401
    signed_in = client.post("/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert signed_in.status_code == 401
    listed = client.get("/v1/admin/users", params={"q": EMAIL}, headers=admin).json()
    assert listed["total"] == 0
    assert register(client, EMAIL)["user"]["id"] != user_id


@pytest.mark.parametrize("typed", [EMAIL, "  GRACE@Example.Test ", "Grace@example.test"])
def test_confirm_email_is_compared_the_way_sign_in_compares(
    world: tuple[TestClient, Headers, Headers, str], typed: str
) -> None:
    client, admin, _, user_id = world
    response = client.post(
        f"/v1/admin/users/{user_id}/delete",
        json={"reason": REASON, "confirm_email": typed},
        headers=admin,
    )
    assert response.status_code == 204, response.text
    assert rows_of_user(client, user_id) == {}


@pytest.mark.parametrize(
    "typed",
    ["grace@example.tes", "ada@example.test", ADMIN_EMAIL, "grace", "x", "grace@example.test."],
)
def test_a_wrong_confirm_email_deletes_nothing(
    world: tuple[TestClient, Headers, Headers, str], typed: str
) -> None:
    client, admin, user, user_id = world
    held = rows_of_user(client, user_id)
    before = len(audit_rows(client))
    response = client.post(
        f"/v1/admin/users/{user_id}/delete",
        json={"reason": REASON, "confirm_email": typed},
        headers=admin,
    )
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "confirm_email_mismatch"
    assert EMAIL not in error["message"] and "details" not in error
    assert rows_of_user(client, user_id) == held
    assert len(audit_rows(client)) == before
    assert client.get("/v1/me", headers=user).status_code == 200


def test_both_routes_refuse_an_administrator_and_the_callers_own_account(
    make_app: AppFactory,
) -> None:
    app = make_app(admin_emails=f"{ADMIN_EMAIL}, chief@example.test")
    with TestClient(app) as client:
        boss = admin_headers(client, ADMIN_EMAIL)
        chief = admin_headers(client, "chief@example.test")
        boss_id, chief_id = me(client, boss)["id"], me(client, chief)["id"]
        before = len(audit_rows(client))
        cases = (
            (boss_id, ADMIN_EMAIL, "self", "your own account"),
            (chief_id, "chief@example.test", "admin", "An administrator"),
        )
        for target, email, suffix, words in cases:
            exported = client.post(
                f"/v1/admin/users/{target}/export", json={"reason": REASON}, headers=boss
            )
            assert exported.status_code == 409
            assert exported.json()["error"]["code"] == f"cannot_export_{suffix}"
            assert words in exported.json()["error"]["message"]
            deleted = client.post(
                f"/v1/admin/users/{target}/delete",
                json={"reason": REASON, "confirm_email": email},
                headers=boss,
            )
            assert deleted.status_code == 409
            assert deleted.json()["error"]["code"] == f"cannot_delete_{suffix}"
            assert words in deleted.json()["error"]["message"]
        assert len(audit_rows(client)) == before
        for headers in (boss, chief):
            assert client.get("/v1/admin/overview", headers=headers).status_code == 200


def test_validation_and_unknown_user(world: tuple[TestClient, Headers, Headers, str]) -> None:
    client, admin, user, user_id = world
    before = len(audit_rows(client))
    bad_reasons: tuple[Any, ...] = (None, "", "  ", "no", "x" * 501, 7)
    for reason in bad_reasons:
        body = {} if reason is None else {"reason": reason}
        exported = client.post(f"/v1/admin/users/{user_id}/export", json=body, headers=admin)
        assert exported.status_code == 422, reason
        assert exported.json()["error"]["code"] == "validation_error"
        deleted = client.post(
            f"/v1/admin/users/{user_id}/delete",
            json={**body, "confirm_email": EMAIL},
            headers=admin,
        )
        assert deleted.status_code == 422, reason
        assert deleted.json()["error"]["code"] == "validation_error"
    for body in ({"reason": REASON}, {"reason": REASON, "confirm_email": ""}):
        missing = client.post(f"/v1/admin/users/{user_id}/delete", json=body, headers=admin)
        assert missing.status_code == 422 and missing.json()["error"]["code"] == "validation_error"
    # A reason of the longest allowed length is fine for the export.
    assert (
        client.post(
            f"/v1/admin/users/{user_id}/export", json={"reason": "y" * 500}, headers=admin
        ).status_code
        == 200
    )
    for path, body in (
        ("/v1/admin/users/nobody/export", {"reason": REASON}),
        ("/v1/admin/users/nobody/delete", {"reason": REASON, "confirm_email": EMAIL}),
    ):
        unknown = client.post(path, json=body, headers=admin)
        assert unknown.status_code == 404 and unknown.json()["error"]["code"] == "not_found"
    assert len(audit_rows(client)) == before + 1  # the one export that was allowed
    assert client.get("/v1/me", headers=user).status_code == 200


def test_the_reason_cannot_carry_the_accounts_email_address(
    world: tuple[TestClient, Headers, Headers, str],
) -> None:
    """The reason is kept in the audit log after the account is gone."""
    client, admin, user, user_id = world
    before = len(audit_rows(client))
    for reason in (f"asked from {EMAIL} by email", "Asked from GRACE@EXAMPLE.TEST"):
        for path, extra in (("export", {}), ("delete", {"confirm_email": EMAIL})):
            refused = client.post(
                f"/v1/admin/users/{user_id}/{path}", json={"reason": reason, **extra}, headers=admin
            )
            assert refused.status_code == 422, (reason, path)
            error = refused.json()["error"]
            assert error["code"] == "reason_contains_email"
            assert EMAIL not in error["message"]
    assert len(audit_rows(client)) == before
    assert client.get("/v1/me", headers=user).status_code == 200


def test_the_owners_delete_and_the_administrators_are_one_code_path(
    world: tuple[TestClient, Headers, Headers, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, admin, _, user_id = world
    calls: list[str] = []
    real = account_service.delete_account

    def recording(db: Any, request: Any, account: User) -> str:
        calls.append(account.id)
        return real(db, request, account)

    monkeypatch.setattr(account_service, "delete_account", recording)
    other = auth_headers(client, "twin@example.test")
    other_id = me(client, other)["id"]
    assert client.delete("/v1/me", headers=other).status_code == 204
    deleted = client.post(
        f"/v1/admin/users/{user_id}/delete",
        json={"reason": REASON, "confirm_email": EMAIL},
        headers=admin,
    )
    assert deleted.status_code == 204
    assert calls == [other_id, user_id]


def test_a_user_cannot_use_either_route(world: tuple[TestClient, Headers, Headers, str]) -> None:
    client, _, user, user_id = world
    other = auth_headers(client, "twin@example.test")
    for headers, status in ((other, 403), (user, 403), ({}, 401)):
        exported = client.post(
            f"/v1/admin/users/{user_id}/export", json={"reason": REASON}, headers=headers
        )
        deleted = client.post(
            f"/v1/admin/users/{user_id}/delete",
            json={"reason": REASON, "confirm_email": EMAIL},
            headers=headers,
        )
        assert (exported.status_code, deleted.status_code) == (status, status)
    assert rows_of_user(client, user_id)["users.id"] == 1
    assert not audit_rows(client, "admin.user_exported")
    assert not audit_rows(client, "admin.user_deleted")


def test_the_two_routes_are_published_with_their_operation_ids(admin_client: TestClient) -> None:
    paths = admin_client.get("/openapi.json").json()["paths"]
    export = paths["/v1/admin/users/{user_id}/export"]["post"]
    delete = paths["/v1/admin/users/{user_id}/delete"]["post"]
    assert (export["operationId"], delete["operationId"]) == (
        "admin_export_user",
        "admin_delete_user",
    )
    assert set(export["responses"]) == {"200", "401", "403", "404", "409", "422", "429"}
    assert set(delete["responses"]) == {"204", "401", "403", "404", "409", "422"}
    own = paths["/v1/me/export"]["get"]["responses"]["200"]["content"]["application/json"]
    assert export["responses"]["200"]["content"]["application/json"] == own
    assert "admin" in export["tags"] and "admin" in delete["tags"]
