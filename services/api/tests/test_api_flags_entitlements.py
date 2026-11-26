"""Feature flags, the require_flag dependency, plans and entitlements."""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from oddvex_api.alerts.schemas import MAX_ACTIVE_ALERTS
from oddvex_api.db import FeatureFlag, User
from oddvex_api.entitlements import catalog
from oddvex_api.entitlements.catalog import Entitlement
from oddvex_api.entitlements.service import check_entitlement, entitlement, require_entitlement
from oddvex_api.flags import service as flags
from oddvex_api.flags.catalog import KNOWN_FLAGS
from oddvex_api.flags.service import require_flag

from .conftest import admin_headers, auth_headers, set_flag

DEFAULTS = {
    "community": False,
    "community_leaderboard": False,
    "value_screen": True,
    "tracker_analytics": True,
    "email_flows": True,
    "premium_gating": False,
    "snapshot_archive": False,
}


# ---------------------------------------------------------------------- flags
def test_known_flags_and_their_safe_defaults() -> None:
    assert {key: spec.default for key, spec in KNOWN_FLAGS.items()} == DEFAULTS
    assert all(spec.description for spec in KNOWN_FLAGS.values())


def test_list_flags_is_public_and_returns_the_defaults(client: TestClient) -> None:
    response = client.get("/v1/flags")
    assert response.status_code == 200
    assert response.json() == {"flags": DEFAULTS}


def test_a_database_row_overrides_the_default(app: FastAPI, client: TestClient) -> None:
    with app.state.session_factory() as db:
        flags.set_flag(db, "community", True)
        flags.set_flag(db, "value_screen", False)
        # A row for a key the code does not know is ignored.
        db.add(FeatureFlag(key="mystery", description="", enabled=True))
        db.commit()
        assert flags.is_enabled(db, "community") is True
        assert flags.is_enabled(db, "email_flows") is True
    assert client.get("/v1/flags").json() == {
        "flags": {**DEFAULTS, "community": True, "value_screen": False}
    }


def test_set_flag_reports_the_previous_effective_state(app: FastAPI, client: TestClient) -> None:
    with app.state.session_factory() as db:
        before, row = flags.set_flag(db, "community", True)
        assert before is False and row.enabled is True
        db.commit()
        before, row = flags.set_flag(db, "community", False)
        assert before is True and row.enabled is False
        with pytest.raises(KeyError):
            flags.set_flag(db, "nope", True)


def test_require_flag_returns_404_feature_disabled_when_off(app: FastAPI) -> None:
    @app.get("/v1/_test/community", dependencies=[Depends(require_flag("community"))])
    def community() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(app) as client:
        off = client.get("/v1/_test/community")
        assert off.status_code == 404
        assert off.json() == {
            "error": {
                "code": "feature_disabled",
                "message": "This feature is not available",
                "details": {"flag": "community"},
            }
        }
        with app.state.session_factory() as db:
            flags.set_flag(db, "community", True)
            db.commit()
        assert client.get("/v1/_test/community").json() == {"ok": True}


def test_require_flag_rejects_an_unknown_key() -> None:
    with pytest.raises(KeyError):
        require_flag("not_a_flag")


def test_flagged_routes_are_gone_while_their_flag_is_off(admin_client: TestClient) -> None:
    admin = admin_headers(admin_client)
    user = auth_headers(admin_client)
    assert admin_client.get("/v1/value").status_code == 200
    assert admin_client.get("/v1/bets/analytics", headers=user).status_code == 200
    for key in ("value_screen", "tracker_analytics", "email_flows"):
        set_flag(admin_client, admin, key, False)
    calls = [
        ("GET", "/v1/value", None, None),
        ("GET", "/v1/bets/analytics", None, user),
        ("POST", "/v1/auth/verify-email/request", None, user),
        ("POST", "/v1/auth/verify-email/confirm", {"token": "x" * 43}, None),
        ("POST", "/v1/auth/password-reset/request", {"email": "ada@example.test"}, None),
        (
            "POST",
            "/v1/auth/password-reset/confirm",
            {"token": "x" * 43, "new_password": "another-password-1"},
            None,
        ),
    ]
    for method, path, body, headers in calls:
        response = admin_client.request(method, path, json=body, headers=headers)
        assert response.status_code == 404, (path, response.text)
        assert response.json()["error"]["code"] == "feature_disabled", path
    # Everything else keeps working, and switching a flag back on restores the route.
    assert admin_client.get("/v1/bets/summary", headers=user).status_code == 200
    set_flag(admin_client, admin, "value_screen", True)
    assert admin_client.get("/v1/value").status_code == 200


# --------------------------------------------------------------- entitlements
def test_entitlements_require_authentication(client: TestClient) -> None:
    response = client.get("/v1/me/entitlements")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_entitlements_are_a_preview_while_gating_is_off(
    client: TestClient, headers: dict[str, str]
) -> None:
    me = client.get("/v1/me", headers=headers).json()
    assert me["plan"] == "free"
    body = client.get("/v1/me/entitlements", headers=headers).json()
    assert body == {
        "plan": "free",
        "preview": True,
        "features": {
            "alerts.max_active": {"enabled": True, "limit": MAX_ACTIVE_ALERTS},
            "value_screen": {"enabled": True, "limit": None},
            "tracker_analytics": {"enabled": True, "limit": None},
            "odds_history_hours": {"enabled": True, "limit": 48},
        },
    }


def test_the_shipped_catalog_gates_nothing(admin_client: TestClient) -> None:
    """No packaging decision has been made: both plans get the same thing, so even
    with the flag on every feature stays enabled for a free user."""
    for feature, plans in catalog.CATALOG.items():
        assert set(plans) == set(catalog.PLANS), feature
        assert plans["free"] == plans["premium"] and plans["free"].enabled, feature
    admin = admin_headers(admin_client)
    user = auth_headers(admin_client)
    set_flag(admin_client, admin, "premium_gating", True)
    body = admin_client.get("/v1/me/entitlements", headers=user).json()
    assert body["preview"] is False and body["plan"] == "free"
    assert all(feature["enabled"] for feature in body["features"].values())
    assert admin_client.get("/v1/value").status_code == 200
    assert admin_client.get("/v1/bets/analytics", headers=user).status_code == 200


def test_there_is_no_purchase_or_billing_route(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    for path in paths:
        for word in ("purchase", "checkout", "billing", "subscribe", "payment", "upgrade"):
            assert word not in path, path
    plan_writers = [
        (method, path)
        for path, item in paths.items()
        for method in item
        if "plan" in path and method != "get"
    ]
    assert plan_writers == [("put", "/v1/admin/users/{user_id}/plan")]


@pytest.fixture
def premium_only(monkeypatch: pytest.MonkeyPatch) -> str:
    """A premium-only feature that exists for these tests only."""
    monkeypatch.setitem(
        catalog.CATALOG,
        "test.premium_only",
        {"free": Entitlement(False), "premium": Entitlement(True, 7)},
    )
    return "test.premium_only"


def test_entitlement_resolution(premium_only: str) -> None:
    assert entitlement("free", premium_only, gating=False) == Entitlement(True, 7)
    assert entitlement("free", premium_only, gating=True) == Entitlement(False)
    assert entitlement("premium", premium_only, gating=True) == Entitlement(True, 7)
    # An unknown plan value is treated as free, never as more.
    assert entitlement("gold", premium_only, gating=True) == Entitlement(False)


def test_require_entitlement_with_gating_on(
    make_app,
    premium_only: str,  # type: ignore[no-untyped-def]
) -> None:
    app = make_app(admin_emails="boss@example.test")

    @app.get("/v1/_test/premium")
    def premium(
        granted: Entitlement = Depends(require_entitlement(premium_only)),
    ) -> dict[str, int | None]:
        return {"limit": granted.limit}

    with TestClient(app) as client:
        admin = admin_headers(client)
        user = auth_headers(client)
        user_id = client.get("/v1/me", headers=user).json()["id"]
        assert client.get("/v1/_test/premium").status_code == 401

        # Gating off (the default): a free user is let through.
        assert client.get("/v1/_test/premium", headers=user).json() == {"limit": 7}
        preview = client.get("/v1/me/entitlements", headers=user).json()
        assert preview["preview"] is True
        assert preview["features"][premium_only] == {"enabled": True, "limit": 7}

        set_flag(client, admin, "premium_gating", True)
        denied = client.get("/v1/_test/premium", headers=user)
        assert denied.status_code == 403  # not 402: nothing can be paid for
        assert denied.json() == {
            "error": {
                "code": "plan_required",
                "message": "Your plan does not include this feature",
                "details": {
                    "feature": premium_only,
                    "plan": "free",
                    "required_plan": "premium",
                },
            }
        }
        gated = client.get("/v1/me/entitlements", headers=user).json()
        assert gated["preview"] is False
        assert gated["features"][premium_only] == {"enabled": False, "limit": None}

        # Only an administrator can grant the plan.
        granted = client.put(
            f"/v1/admin/users/{user_id}/plan", json={"plan": "premium"}, headers=admin
        )
        assert granted.status_code == 200 and granted.json()["plan"] == "premium"
        assert client.get("/v1/_test/premium", headers=user).json() == {"limit": 7}
        after = client.get("/v1/me/entitlements", headers=user).json()
        assert after["plan"] == "premium"
        assert after["features"][premium_only] == {"enabled": True, "limit": 7}
        assert client.get("/v1/me", headers=user).json()["plan"] == "premium"

        set_flag(client, admin, "premium_gating", False)
        assert client.get("/v1/me/entitlements", headers=user).json()["preview"] is True


def test_check_entitlement_rejects_an_unknown_feature(app: FastAPI) -> None:
    with TestClient(app), app.state.session_factory() as db, pytest.raises(KeyError):
        check_entitlement(db, User(plan="free"), "not.a.feature")
