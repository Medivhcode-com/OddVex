"""Follow-ups from the documentation and threat review: logout, the ``email_flows``
default per environment, the health check, audited admin reads and role changes,
case-insensitive filters for any script, data rights of a suspended account and the
streak note."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from oddvex_api.bets import analytics
from oddvex_api.db import AuditLog, Bet, User
from oddvex_api.flags import service as flags
from oddvex_api.flags.catalog import KNOWN_FLAGS
from oddvex_api.providers import SyntheticProvider
from oddvex_api.textnorm import fold, user_search_key

from .conftest import (
    ADMIN_EMAIL,
    FROZEN_NOW,
    PASSWORD,
    AppFactory,
    admin_headers,
    auth_headers,
    register,
    set_flag,
    verify_email,
)

Headers = dict[str, str]
BET = {
    "bet_type": "straight",
    "stake": 10,
    "sportsbook": "Northline",
    "legs": [{"selection": "Tides ML", "market": "moneyline", "odds": -110}],
}
#: Review item 7: nothing congratulatory or encouraging next to results.
BANNED_STREAK_COPY = ("hot streak", "on fire", "keep it going", "you're due", "can't lose")


def audit(client: TestClient, action: str | None = None) -> list[AuditLog]:
    app: FastAPI = client.app  # type: ignore[assignment]
    with app.state.session_factory() as db:
        query = select(AuditLog).order_by(AuditLog.created_at, AuditLog.id)
        if action:
            query = query.where(AuditLog.action == action)
        return list(db.scalars(query))


def login(client: TestClient, email: str) -> Any:
    return client.post("/v1/auth/login", json={"email": email, "password": PASSWORD})


def bearer(token: str) -> Headers:
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------- logout
def test_logout_revokes_every_token_of_the_account_and_is_audited(client: TestClient) -> None:
    account = register(client)
    first = bearer(account["access_token"])
    second = bearer(login(client, "ada@example.test").json()["access_token"])
    other = auth_headers(client, "grace@example.test")
    assert client.get("/v1/me", headers=first).status_code == 200
    assert client.get("/v1/me", headers=second).status_code == 200

    response = client.post("/v1/auth/logout", headers=first)
    assert response.status_code == 204 and response.content == b""

    # Log out everywhere: the token used and the one from the other session.
    for headers in (first, second):
        rejected = client.get("/v1/me", headers=headers)
        assert rejected.status_code == 401
        assert rejected.json()["error"]["code"] == "invalid_token"
    assert client.post("/v1/auth/logout", headers=first).status_code == 401
    # Nobody else is affected, and signing in again works.
    assert client.get("/v1/me", headers=other).status_code == 200
    again = bearer(login(client, "ada@example.test").json()["access_token"])
    assert client.get("/v1/me", headers=again).status_code == 200

    (entry,) = audit(client, "auth.logout")
    assert (entry.user_id, entry.entity_type, entry.entity_id) == (
        account["user"]["id"],
        "user",
        account["user"]["id"],
    )
    assert entry.request_id


def test_logout_needs_a_token(client: TestClient) -> None:
    response = client.post("/v1/auth/logout")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
    assert not audit(client, "auth.logout")


# ---------------------------------------------------- email_flows per environment
def test_email_flows_defaults_on_outside_production_and_off_in_production(
    make_app: AppFactory,
) -> None:
    spec = KNOWN_FLAGS["email_flows"]
    assert (spec.default, spec.default_in_production) == (True, False)
    assert spec.default_for(production=False) is True
    assert spec.default_for(production=True) is False
    # No other flag depends on the environment.
    assert [k for k, s in KNOWN_FLAGS.items() if s.default_in_production is not None] == [
        "email_flows"
    ]

    for env in ("test", "development"):
        with TestClient(make_app(env=env)) as client:
            assert client.get("/v1/flags").json()["flags"]["email_flows"] is True
            register(client, f"{env}@example.test")
            reset = client.post(
                "/v1/auth/password-reset/request", json={"email": f"{env}@example.test"}
            )
            assert reset.status_code == 202
            client.app.state.engine.dispose()  # type: ignore[attr-defined]


def test_in_production_email_flows_is_off_until_a_database_override(
    make_app: AppFactory,
) -> None:
    app = make_app(env="production", jwt_secret="k" * 48, admin_emails=ADMIN_EMAIL)
    from oddvex_api.db import Base

    Base.metadata.create_all(app.state.engine)  # production never creates tables itself
    with TestClient(app) as client:
        assert client.get("/v1/flags").json()["flags"]["email_flows"] is False
        account = register(client)
        headers = bearer(account["access_token"])
        # A reset request would go nowhere, so the route says the feature is off.
        for method, path, body in (
            ("POST", "/v1/auth/password-reset/request", {"email": "ada@example.test"}),
            (
                "POST",
                "/v1/auth/password-reset/confirm",
                {"token": "t" * 20, "new_password": "p" * 12},
            ),
            ("POST", "/v1/auth/verify-email/request", None),
            ("POST", "/v1/auth/verify-email/confirm", {"token": "t" * 20}),
        ):
            response = client.request(method, path, json=body, headers=headers)
            assert response.status_code == 404, path
            assert response.json()["error"] == {
                "code": "feature_disabled",
                "message": "This feature is not available",
                "details": {"flag": "email_flows"},
            }
        # No verification email was queued at registration either.
        with app.state.session_factory() as db:
            assert db.execute(text("SELECT count(*) FROM email_outbox")).scalar() == 0
            assert flags.is_enabled(db, "email_flows", app.state.settings) is False

        # The stored override wins, in both directions.
        admin = admin_headers(client)
        listed = client.get("/v1/admin/flags", headers=admin).json()["items"]
        row = next(f for f in listed if f["key"] == "email_flows")
        assert (row["enabled"], row["default"], row["overridden"]) == (False, False, False)
        set_flag(client, admin, "email_flows", True)
        assert client.get("/v1/flags").json()["flags"]["email_flows"] is True
        assert client.post("/v1/auth/verify-email/request", headers=headers).status_code == 202
        (entry,) = audit(client, "admin.flag_set")
        assert entry.details == {"before": {"enabled": False}, "after": {"enabled": True}}
        set_flag(client, admin, "email_flows", False)
        assert client.post("/v1/auth/verify-email/request", headers=headers).status_code == 404


def test_a_database_override_turns_email_flows_off_outside_production(
    admin_client: TestClient,
) -> None:
    admin = admin_headers(admin_client)
    set_flag(admin_client, admin, "email_flows", False)
    assert admin_client.get("/v1/flags").json()["flags"]["email_flows"] is False
    reset = admin_client.post("/v1/auth/password-reset/request", json={"email": "ada@example.test"})
    assert reset.status_code == 404


# --------------------------------------------------------------------- health
def test_health_reports_the_database_and_the_providers_data_mode(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["database"] == "ok"
    assert body["data_mode"] == "synthetic"


def test_health_is_degraded_but_still_200_when_the_database_fails(
    app: FastAPI, client: TestClient
) -> None:
    class Broken:
        def __call__(self) -> Any:
            raise RuntimeError("database is down")

    working = app.state.session_factory
    app.state.session_factory = Broken()
    try:
        response = client.get("/health")
    finally:
        app.state.session_factory = working
    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["database"]) == ("degraded", "error")
    assert "database is down" not in response.text
    assert client.get("/health").json()["status"] == "ok"


def test_health_is_degraded_when_the_query_itself_fails(app: FastAPI, client: TestClient) -> None:
    app.state.engine.dispose()
    working = app.state.session_factory

    class FailingSession:
        def __enter__(self) -> FailingSession:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def execute(self, *_: object) -> None:
            raise OSError("connection refused")

    app.state.session_factory = FailingSession
    try:
        body = client.get("/health").json()
    finally:
        app.state.session_factory = working
    assert (body["status"], body["database"]) == ("degraded", "error")


def test_data_mode_comes_from_the_active_provider(make_app: AppFactory) -> None:
    class Relabelled(SyntheticProvider):
        """Reports a data mode of its own, to show nothing is hard-coded in the routes."""

        data_mode = "relabelled"

    provider = Relabelled(seed=20260101, clock=lambda: FROZEN_NOW)
    with TestClient(make_app(provider=provider), raise_server_exceptions=False) as client:
        # The response model only knows ``synthetic``: a provider reporting anything else
        # is refused by response validation instead of being mislabelled as synthetic.
        assert client.get("/health").status_code == 500
        assert client.get("/v1/meta").status_code == 500
    with TestClient(make_app()) as client:
        assert client.get("/v1/meta").json()["data_mode"] == SyntheticProvider.data_mode
        assert client.get("/health").json()["data_mode"] == SyntheticProvider.data_mode


# ---------------------------------------------------------- admin: audited reads
def test_admin_reads_are_audited_once_per_request_without_payload(
    admin_client: TestClient,
) -> None:
    admin = admin_headers(admin_client)
    admin_id = admin_client.get("/v1/me", headers=admin).json()["id"]
    auth_headers(admin_client)
    assert not audit(admin_client, "admin.read")

    overview = admin_client.get("/v1/admin/overview", headers=admin).json()
    # The read is recorded, but a request never shows up in its own answer.
    assert "admin.read" not in [e["action"] for e in overview["recent_audit"]]
    admin_client.get("/v1/admin/users", params={"q": "ada", "limit": 5}, headers=admin)
    admin_client.get("/v1/admin/users", headers=admin)
    admin_client.get("/v1/admin/email-outbox", headers=admin)

    rows = audit(admin_client, "admin.read")
    assert [r.entity_type for r in rows] == [
        "admin_overview",
        "admin_users",
        "admin_users",
        "admin_email_outbox",
    ]
    for row in rows:
        assert row.user_id == admin_id and row.request_id
        # Coarse on purpose: no filters, no search term, no returned rows.
        assert row.details is None and row.entity_id is None
    assert len({r.request_id for r in rows}) == 4
    again = admin_client.get("/v1/admin/overview", headers=admin).json()
    assert "admin.read" in [e["action"] for e in again["recent_audit"]]


def test_a_refused_admin_read_is_not_audited_as_a_read(admin_client: TestClient) -> None:
    user = auth_headers(admin_client)
    assert admin_client.get("/v1/admin/users", headers=user).status_code == 403
    assert admin_client.get("/v1/admin/overview").status_code == 401
    assert not audit(admin_client, "admin.read")


# ------------------------------------------------------- admin: role changes
def test_role_is_granted_only_after_the_email_is_confirmed_and_is_audited(
    admin_client: TestClient,
) -> None:
    account = register(admin_client, ADMIN_EMAIL)
    headers = bearer(account["access_token"])
    # Registering a listed address first proves nothing while ``email_flows`` is on.
    assert account["user"]["role"] == "user"
    assert admin_client.get("/v1/admin/overview", headers=headers).status_code == 403
    assert login(admin_client, ADMIN_EMAIL).json()["user"]["role"] == "user"
    assert not audit(admin_client, "role.granted")

    verify_email(admin_client, ADMIN_EMAIL)
    (granted,) = audit(admin_client, "role.granted")
    assert (granted.user_id, granted.entity_type, granted.entity_id) == (
        account["user"]["id"],
        "user",
        account["user"]["id"],
    )
    assert granted.details == {"role": "admin", "source": "admin_emails"}
    assert admin_client.get("/v1/admin/overview", headers=headers).status_code == 200
    assert login(admin_client, ADMIN_EMAIL).json()["user"]["role"] == "admin"
    assert len(audit(admin_client, "role.granted")) == 1  # once, not on every request


def test_an_unlisted_address_never_gets_the_role(admin_client: TestClient) -> None:
    headers = auth_headers(admin_client)
    verify_email(admin_client, "ada@example.test")
    assert admin_client.get("/v1/me", headers=headers).json()["role"] == "user"
    assert admin_client.get("/v1/admin/overview", headers=headers).status_code == 403
    assert not audit(admin_client, "role.granted")


def test_with_email_flows_off_a_listed_address_is_admin_from_registration(
    make_app: AppFactory,
) -> None:
    app = make_app(admin_emails=ADMIN_EMAIL)
    with TestClient(app) as client:
        with app.state.session_factory() as db:
            flags.set_flag(db, "email_flows", False, app.state.settings)
            db.commit()
        account = register(client, ADMIN_EMAIL)
        assert account["user"]["role"] == "admin" and account["user"]["email_verified"] is False
        assert (
            client.get("/v1/admin/overview", headers=bearer(account["access_token"])).status_code
            == 200
        )
        (granted,) = audit(client, "role.granted")
        assert granted.user_id == account["user"]["id"]


@pytest.mark.parametrize("via", ["token", "login"])
def test_removing_an_address_from_the_allowlist_demotes_at_next_use(
    make_app: AppFactory, via: str
) -> None:
    with TestClient(make_app(admin_emails=ADMIN_EMAIL)) as client:
        headers = admin_headers(client)
        user_id = client.get("/v1/me", headers=headers).json()["id"]
        assert client.get("/v1/admin/overview", headers=headers).status_code == 200
        client.app.state.engine.dispose()  # type: ignore[attr-defined]

    # The same database, restarted with the address no longer listed.
    with TestClient(make_app(admin_emails="someone-else@example.test")) as client:
        if via == "token":
            refused = client.get("/v1/admin/users", headers=headers)
            assert refused.status_code == 403
            assert client.get("/v1/me", headers=headers).json()["role"] == "user"
        else:
            assert login(client, ADMIN_EMAIL).json()["user"]["role"] == "user"
        (removed,) = audit(client, "role.removed")
        assert (removed.user_id, removed.entity_id) == (user_id, user_id)
        assert removed.details == {"role": "admin", "reason": "not_in_admin_emails"}
        with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
            assert db.get(User, user_id).role == "user"
        # Demoted once; the row is not written again on later requests.
        reads = len(audit(client, "admin.read"))
        client.get("/v1/me", headers=headers)
        assert client.get("/v1/admin/overview", headers=headers).status_code == 403
        assert len(audit(client, "role.removed")) == 1
        assert len(audit(client, "admin.read")) == reads


# ------------------------------------------------- case-insensitive filters
NAMES = ("Éclair Sports", "STRASSE Wetten", "Ünïcode Book", "İstanbul Lines", "Northline")


def test_fold_is_a_stable_caseless_key() -> None:
    assert fold("ÉCLAIR  Sports ") == fold("éclair sports") == "éclair sports"
    assert fold("STRASSE") == fold("Straße") == "strasse"
    fullwidth = "".join(chr(ord(c) + 0xFEE0) if c != " " else chr(0x3000) for c in "FULL width")
    assert fold(fullwidth) == "full width"
    for name in NAMES:
        assert fold(fold(name)) == fold(name)
    assert fold(None) == "" and fold("   ") == ""
    assert user_search_key("Ada@Example.test", "Ada  L") == "ada@example.test\nada l"


def test_sportsbook_filter_matches_any_script_whatever_the_case(
    client: TestClient, headers: Headers, other_headers: Headers
) -> None:
    for name in NAMES:
        created = client.post("/v1/bets", json={**BET, "sportsbook": name}, headers=headers)
        assert created.status_code == 201, created.text
    client.post("/v1/bets", json={**BET, "sportsbook": "éclair sports"}, headers=other_headers)

    def books(term: str, who: Headers = headers) -> list[str]:
        response = client.get("/v1/bets", params={"sportsbook": term}, headers=who)
        assert response.status_code == 200, response.text
        return sorted(b["sportsbook"] for b in response.json())

    # These are the cases SQL ``lower()`` gets wrong on SQLite and C-locale PostgreSQL.
    assert books("éclair sports") == ["Éclair Sports"]
    assert books("ÉCLAIR SPORTS") == ["Éclair Sports"]
    assert books("  éclair   sports ") == ["Éclair Sports"]
    assert books("strasse wetten") == books("Straße Wetten") == ["STRASSE Wetten"]
    assert books("ÜNÏCODE BOOK") == ["Ünïcode Book"]
    assert books("northLINE") == ["Northline"]
    # Exact, not partial; and owner-scoped as before.
    assert books("éclair") == [] and books("eclair sports") == []
    assert books("ÉCLAIR SPORTS", other_headers) == ["éclair sports"]
    # The name is stored and returned as typed; only the key is folded.
    with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
        keys = {b.sportsbook: b.sportsbook_key for b in db.scalars(select(Bet))}
    assert keys["Éclair Sports"] == "éclair sports" and keys["STRASSE Wetten"] == "strasse wetten"


def test_sportsbook_key_follows_an_edit(client: TestClient, headers: Headers) -> None:
    bet = client.post("/v1/bets", json=BET, headers=headers).json()
    patched = client.patch(f"/v1/bets/{bet['id']}", json={"sportsbook": "ÇA VA"}, headers=headers)
    assert patched.status_code == 200, patched.text
    assert len(client.get("/v1/bets", params={"sportsbook": "ça va"}, headers=headers).json()) == 1
    assert client.get("/v1/bets", params={"sportsbook": "northline"}, headers=headers).json() == []


def test_admin_search_matches_any_script_whatever_the_case(admin_client: TestClient) -> None:
    admin = admin_headers(admin_client)
    register(admin_client, "zoe@example.test", display_name="Zoë Ünsal")
    register(admin_client, "jose@example.test", display_name="JOSÉ Straße")
    register(admin_client, "plain@example.test", display_name="Plain")

    def found(term: str) -> list[str]:
        response = admin_client.get("/v1/admin/users", params={"q": term}, headers=admin)
        assert response.status_code == 200, response.text
        assert response.json()["total"] == len(response.json()["items"])
        return sorted(u["email"] for u in response.json()["items"])

    assert found("zoë") == found("ZOË") == found("ë ün") == ["zoe@example.test"]
    assert found("josé") == found("JOSÉ") == ["jose@example.test"]
    assert found("STRASSE") == found("straße") == ["jose@example.test"]
    assert found("PLAIN@EXAMPLE") == ["plain@example.test"]
    assert len(found("example.test")) == 4
    # A term never matches across the email and the display name, and LIKE wildcards
    # are literal.
    assert found("test zoë") == [] and found("test\nzoë") == []
    assert found("%") == [] and found("_") == []
    assert found("zoe unsal") == []  # accents are significant, only case is not


# ------------------------------------------------- suspended: data rights only
def suspend(client: TestClient, admin: Headers, user_id: str) -> None:
    response = client.post(
        f"/v1/admin/users/{user_id}/suspend", json={"reason": "review"}, headers=admin
    )
    assert response.status_code == 200, response.text


def test_a_suspended_account_can_export_and_delete_and_nothing_else(
    admin_client: TestClient,
) -> None:
    client = admin_client
    admin = admin_headers(client)
    account = register(client)
    headers = bearer(account["access_token"])
    user_id = account["user"]["id"]
    bet = client.post("/v1/bets", json=BET, headers=headers).json()
    suspend(client, admin, user_id)

    # Every other route that takes a token refuses it, whatever the method.
    schema = client.get("/openapi.json").json()
    allowed = {("get", "/v1/me/export"), ("delete", "/v1/me")}
    public = ("/health", "/v1/meta", "/v1/leagues", "/v1/sportsbooks", "/v1/events")
    public += ("/v1/players", "/v1/props", "/v1/quant", "/v1/value", "/v1/flags", "/v1/dev")
    public += ("/v1/auth/register", "/v1/auth/login", "/v1/auth/verify-email/confirm")
    public += ("/v1/auth/password-reset", "/v1/community", "/v1/admin/community")
    refused = 0
    for path, item in schema["paths"].items():
        if path.startswith(public):
            continue
        for method in item:
            if (method, path) in allowed:
                continue
            url = path.replace("{", "").replace("}", "")
            response = client.request(method.upper(), url, json={}, headers=headers)
            assert response.status_code == 401, (method, path, response.status_code)
            assert response.json()["error"]["code"] == "account_suspended", path
            refused += 1
    assert refused >= 45
    assert client.post("/v1/auth/logout", headers=headers).status_code == 401
    assert client.get(f"/v1/bets/{bet['id']}", headers=headers).status_code == 401

    # Data rights still work, and each use is audited as made by a suspended account.
    export = client.get("/v1/me/export", headers=headers)
    assert export.status_code == 200, export.text
    assert export.json()["user"]["id"] == user_id and len(export.json()["bets"]) == 1
    (exported,) = audit(client, "account.export")
    assert exported.user_id == user_id and exported.details == {"account_status": "suspended"}

    deleted = client.delete("/v1/me", headers=headers)
    assert deleted.status_code == 204
    (entry,) = audit(client, "account.deleted")
    assert entry.user_id == user_id and entry.details == {"account_status": "suspended"}
    with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
        assert db.get(User, user_id) is None
        assert db.scalar(select(Bet.id).where(Bet.user_id == user_id)) is None
    assert client.get("/v1/me/export", headers=headers).status_code == 401


def test_export_and_delete_audit_rows_of_an_active_account_carry_no_status(
    client: TestClient, headers: Headers
) -> None:
    assert client.get("/v1/me/export", headers=headers).status_code == 200
    assert client.delete("/v1/me", headers=headers).status_code == 204
    assert [r.details for r in audit(client, "account.export")] == [None]
    assert [r.details for r in audit(client, "account.deleted")] == [None]


def test_the_data_rights_exception_does_not_weaken_token_checks(
    admin_client: TestClient,
) -> None:
    client = admin_client
    admin = admin_headers(client)
    account = register(client)
    headers = bearer(account["access_token"])
    suspend(client, admin, account["user"]["id"])
    for path, method in (("/v1/me/export", "GET"), ("/v1/me", "DELETE")):
        assert client.request(method, path).status_code == 401
        garbage = client.request(method, path, headers=bearer("not-a-token"))
        assert garbage.status_code == 401
        assert garbage.json()["error"]["code"] == "invalid_token"
    # A suspended account still cannot sign in, so it cannot get a new token.
    assert login(client, "ada@example.test").status_code == 403
    # A token from before a password change stays dead for a suspended account too.
    with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
        user = db.get(User, account["user"]["id"])
        user.token_version += 1
        db.commit()
    stale = client.get("/v1/me/export", headers=headers)
    assert stale.status_code == 401 and stale.json()["error"]["code"] == "invalid_token"


# ---------------------------------------------------------------- streak note
def test_analytics_carry_a_neutral_streak_note(client: TestClient, headers: Headers) -> None:
    for result in ("won", "won", "lost"):
        bet = client.post("/v1/bets", json=BET, headers=headers).json()
        client.post(f"/v1/bets/{bet['id']}/settle", json={"result": result}, headers=headers)
    body = client.get("/v1/bets/analytics", headers=headers).json()
    # The numbers are still there...
    assert (body["longest_win_streak"], body["longest_loss_streak"]) == (2, 1)
    assert body["current_streak"] == {"kind": "loss", "length": 1}
    # ...next to a statement of what they do and do not mean.
    note = body["streak_note"]
    assert note == analytics.STREAK_NOTE
    assert "past results" in note and "says nothing about what happens next" in note
    # An account with no bets gets the same note: it does not depend on the results.
    empty = client.get("/v1/bets/analytics", headers=auth_headers(client, "new@example.test"))
    assert empty.json()["streak_note"] == note


def test_no_congratulatory_or_encouraging_copy_in_the_tracker_analytics(
    client: TestClient, headers: Headers
) -> None:
    for result in ("won",) * 6:
        bet = client.post("/v1/bets", json=BET, headers=headers).json()
        client.post(f"/v1/bets/{bet['id']}/settle", json={"result": result}, headers=headers)
    body = client.get("/v1/bets/analytics", headers=headers).json()
    assert body["current_streak"] == {"kind": "win", "length": 6}

    def strings(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            return [s for item in value.values() for s in strings(item)]
        if isinstance(value, list):
            return [s for item in value for s in strings(item)]
        return []

    texts = [*strings(body), analytics.STREAK_NOTE, analytics.ANALYTICS_NOTE]
    texts += [analytics.sample_note(n) or "" for n in (0, 1, 29)]
    assert len(texts) > 30
    for copy in texts:
        lowered = copy.lower().replace(chr(0x2019), "'")
        for phrase in BANNED_STREAK_COPY:
            assert phrase not in lowered, (phrase, copy)
        assert "!" not in copy, copy
