from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import AppFactory, admin_headers, auth_headers, verify_email


def test_admin_overview_requires_the_admin_role(make_app: AppFactory) -> None:
    with TestClient(make_app(admin_emails="boss@example.test")) as client:
        assert client.get("/v1/admin/overview").status_code == 401
        user = auth_headers(client, "ada@example.test")
        forbidden = client.get("/v1/admin/overview", headers=user)
        assert forbidden.status_code == 403
        assert forbidden.json()["error"]["code"] == "forbidden"

        admin = admin_headers(client, "boss@example.test")
        bet = client.post(
            "/v1/bets",
            json={
                "bet_type": "straight",
                "stake": 10,
                "sportsbook": "Northline",
                "legs": [{"selection": "x", "market": "moneyline", "odds": -110}],
            },
            headers=user,
        ).json()
        client.post(f"/v1/bets/{bet['id']}/settle", json={"result": "won"}, headers=user)
        client.post("/v1/sync/connections", json={"provider": "mock"}, headers=user)

        response = client.get("/v1/admin/overview", headers=admin)
        assert response.status_code == 200
        overview = response.json()
        assert overview["user_count"] == 2
        assert overview["bet_count"] == 1
        assert overview["sync_connection_count"] == 1
        assert overview["environment"] == "test"
        health = overview["provider_health"]
        assert (health["provider"], health["data_mode"], health["status"]) == (
            "synthetic",
            "synthetic",
            "ok",
        )
        actions = [entry["action"] for entry in overview["recent_audit"]]
        assert actions[0] == "sync.connect"  # newest first
        assert {"auth.register", "bet.create", "bet.settle", "sync.connect"} <= set(actions)
        entry = overview["recent_audit"][0]
        assert set(entry) == {
            "id",
            "created_at",
            "action",
            "user_id",
            "entity_type",
            "entity_id",
            "request_id",
            "details",
        }
        assert "example.test" not in str(overview["recent_audit"])  # no emails in the audit trail


def test_role_claim_in_a_token_is_not_trusted(make_app: AppFactory) -> None:
    """The role is read from the database, not from the JWT."""
    from oddvex_api.auth.security import create_access_token
    from oddvex_api.config import DEV_JWT_SECRET

    with TestClient(make_app()) as client:
        user_id = client.post(
            "/v1/auth/register",
            json={
                "email": "ada@example.test",
                "password": "correct-horse-battery",
                "display_name": "Ada",
                "age_confirmed": True,
            },
        ).json()["user"]["id"]
        token, _ = create_access_token(user_id, "admin", DEV_JWT_SECRET, 5)
        response = client.get("/v1/admin/overview", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403


def test_existing_user_is_promoted_on_login_when_listed(make_app: AppFactory, tmp_path) -> None:  # type: ignore[no-untyped-def]
    with TestClient(make_app()) as client:
        auth_headers(client, "boss@example.test")
        # The role is only granted to a confirmed address while ``email_flows`` is on.
        verify_email(client, "boss@example.test")
    with TestClient(make_app(admin_emails="boss@example.test")) as client:
        login = client.post(
            "/v1/auth/login",
            json={"email": "boss@example.test", "password": "correct-horse-battery"},
        )
        assert login.json()["user"]["role"] == "admin"
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert client.get("/v1/admin/overview", headers=headers).status_code == 200
