from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from oddvex_api.db import AuditLog, Bet, SyncConnection
from oddvex_api.sync import (
    Authorization,
    ExternalBet,
    ExternalLeg,
    FetchResult,
    MockSyncProvider,
    SyncProvider,
    SyncProviderError,
    SyncProviderInfo,
    SyncRegistry,
)

from .conftest import AppFactory, auth_headers

Headers = dict[str, str]


def connect(client: TestClient, headers: Headers, **body: Any) -> dict[str, Any]:
    response = client.post(
        "/v1/sync/connections", json={"provider": "mock", **body}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def sync(
    client: TestClient, headers: Headers, connection_id: str, status: int = 200
) -> dict[str, Any]:
    response = client.post(f"/v1/sync/connections/{connection_id}/sync", headers=headers)
    assert response.status_code == status, response.text
    return response.json()


def test_mock_provider_satisfies_the_protocol() -> None:
    provider = MockSyncProvider()
    assert isinstance(provider, SyncProvider)
    assert provider.info.is_mock is True
    assert provider.info.requires_credentials is False
    now = datetime(2026, 3, 14, tzinfo=UTC)
    authorization = provider.authorize({}, now)
    assert "password" not in str(authorization.state).lower()
    first = provider.fetch_bets(dict(authorization.state), now)
    again = provider.fetch_bets(dict(authorization.state), now)
    assert first == again  # deterministic
    assert len({bet.external_bet_id for bet in first.bets}) == len(first.bets) == 10
    assert all(bet.placed_at <= now for bet in first.bets)


def test_providers_list(client: TestClient, headers: Headers) -> None:
    providers = client.get("/v1/sync/providers", headers=headers).json()
    assert [p["key"] for p in providers] == ["mock"]
    assert providers[0]["is_mock"] is True
    assert providers[0]["requires_credentials"] is False
    assert "no credentials" in providers[0]["description"].lower()


def test_connect_and_list(client: TestClient, headers: Headers) -> None:
    assert client.get("/v1/sync/connections", headers=headers).json() == []
    connection = connect(client, headers, label="My mock book")
    assert connection["provider"] == "mock"
    assert connection["status"] == "active"
    assert connection["label"] == "My mock book"
    assert connection["last_synced_at"] is None
    assert connection["bet_count"] == 0 and connection["last_run"] is None
    assert client.get("/v1/sync/connections", headers=headers).json() == [connection]
    duplicate = client.post("/v1/sync/connections", json={"provider": "mock"}, headers=headers)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "already_connected"
    unknown = client.post("/v1/sync/connections", json={"provider": "realbook"}, headers=headers)
    assert unknown.status_code == 422
    assert unknown.json()["error"]["code"] == "unknown_sync_provider"


def test_import_is_idempotent(client: TestClient, headers: Headers) -> None:
    connection = connect(client, headers)
    first = sync(client, headers, connection["id"])
    assert first["status"] == "succeeded"
    assert (first["fetched_count"], first["imported_count"], first["duplicate_count"]) == (
        10,
        10,
        0,
    )
    assert first["attempts"] == 1 and first["error_message"] is None

    second = sync(client, headers, connection["id"])  # the account has two newer bets now
    assert (second["fetched_count"], second["imported_count"], second["duplicate_count"]) == (
        12,
        2,
        10,
    )
    third = sync(client, headers, connection["id"])
    assert (third["fetched_count"], third["imported_count"], third["duplicate_count"]) == (
        12,
        0,
        12,
    )

    bets = client.get("/v1/bets", headers=headers).json()
    assert len(bets) == 12
    external_ids = [b["external_bet_id"] for b in bets]
    assert len(set(external_ids)) == 12
    assert {b["source"] for b in bets} == {"sync"}
    assert {b["sync_connection_id"] for b in bets} == {connection["id"]}
    assert sum(1 for b in bets if b["status"] == "pending") == 2
    listed = client.get("/v1/sync/connections", headers=headers).json()[0]
    assert listed["bet_count"] == 12
    assert listed["last_synced_at"] is not None
    assert listed["last_run"]["id"] == third["id"]


def test_imported_bets_are_settled_with_quant_math(client: TestClient, headers: Headers) -> None:
    connection = connect(client, headers)
    sync(client, headers, connection["id"])
    bets = {b["external_bet_id"]: b for b in client.get("/v1/bets", headers=headers).json()}
    won = bets["mock-0001"]  # 25.00 at -135
    assert (won["result"], won["stake"]) == ("won", 25.0)
    assert won["payout"] == pytest.approx(25 * (1 + 100 / 135), abs=0.005)
    assert won["profit"] == pytest.approx(won["payout"] - 25, abs=0.001)
    assert won["legs"][0]["closing_price"]["american"] == -150
    assert won["clv"] is not None
    lost_parlay = bets["mock-0004"]
    assert lost_parlay["bet_type"] == "parlay" and lost_parlay["result"] == "lost"
    assert (lost_parlay["payout"], lost_parlay["profit"]) == (0.0, -10.0)
    assert lost_parlay["sport"] == "mlb"
    push = bets["mock-0005"]
    assert (push["result"], push["profit"]) == ("push", 0.0)
    summary = client.get("/v1/bets/summary", headers=headers).json()["totals"]
    assert summary["settled_count"] == 10
    assert summary["profit"] == pytest.approx(sum(b["profit"] for b in bets.values()), abs=0.001)


def test_runs_history(client: TestClient, headers: Headers) -> None:
    connection = connect(client, headers)
    first = sync(client, headers, connection["id"])
    second = sync(client, headers, connection["id"])
    runs = client.get(f"/v1/sync/connections/{connection['id']}/runs", headers=headers).json()
    assert {run["id"] for run in runs} == {first["id"], second["id"]}
    assert all(run["connection_id"] == connection["id"] for run in runs)
    assert all(run["finished_at"] is not None for run in runs)


def test_transient_failure_is_retried_within_one_run(client: TestClient, headers: Headers) -> None:
    connection = connect(client, headers, simulate_failures=2)
    run = sync(client, headers, connection["id"])  # default: up to 3 attempts
    assert run["status"] == "succeeded"
    assert run["attempts"] == 3
    assert run["imported_count"] == 10
    assert len(client.get("/v1/bets", headers=headers).json()) == 10


def test_persistent_failure_is_recorded_and_retryable(
    client: TestClient, headers: Headers, app
) -> None:  # type: ignore[no-untyped-def]
    connection = connect(client, headers, simulate_failures=4)
    failure = sync(client, headers, connection["id"], status=502)["error"]
    assert failure["code"] == "sync_failed"
    assert "temporarily unavailable" in failure["message"]
    assert failure["details"]["retryable"] is True
    assert failure["details"]["attempts"] == 3

    # Nothing was imported, and the failed run is on record.
    assert client.get("/v1/bets", headers=headers).json() == []
    runs = client.get(f"/v1/sync/connections/{connection['id']}/runs", headers=headers).json()
    assert len(runs) == 1
    failed = runs[0]
    assert failed["id"] == failure["details"]["run_id"]
    assert (failed["status"], failed["retryable"], failed["attempts"]) == ("failed", True, 3)
    assert (failed["fetched_count"], failed["imported_count"]) == (0, 0)
    assert failed["error_message"] == failure["message"]
    listed = client.get("/v1/sync/connections", headers=headers).json()[0]
    assert listed["last_synced_at"] is None and listed["last_run"]["status"] == "failed"

    # Retrying later succeeds (one failure was left) and imports exactly once.
    retry = sync(client, headers, connection["id"])
    assert (retry["status"], retry["attempts"], retry["imported_count"]) == ("succeeded", 2, 10)
    assert len(client.get("/v1/bets", headers=headers).json()) == 10
    with app.state.session_factory() as db:
        actions = [
            r.action
            for r in db.scalars(
                select(AuditLog).where(AuditLog.action.like("sync.%")).order_by(AuditLog.created_at)
            )
        ]
    assert actions == ["sync.connect", "sync.import_failed", "sync.import"]


class BrokenProvider:
    """A provider whose failure is not retryable."""

    info = SyncProviderInfo(
        "broken", "Broken", "Always fails", is_mock=True, requires_credentials=False
    )

    def __init__(self) -> None:
        self.calls = 0

    def authorize(self, options: dict[str, Any], now: datetime) -> Authorization:
        return Authorization(label="Broken")

    def fetch_bets(self, state: dict[str, Any], now: datetime) -> FetchResult:
        self.calls += 1
        raise SyncProviderError("Authorization was revoked", retryable=False)


class DuplicatingProvider:
    """Returns the same external id twice in one page."""

    info = SyncProviderInfo(
        "dupes", "Dupes", "Repeats itself", is_mock=True, requires_credentials=False
    )

    def authorize(self, options: dict[str, Any], now: datetime) -> Authorization:
        return Authorization(label="Dupes")

    def fetch_bets(self, state: dict[str, Any], now: datetime) -> FetchResult:
        bet = ExternalBet(
            external_bet_id="same-id",
            bet_type="straight",
            sportsbook="Dupes",
            stake=Decimal("10"),
            placed_at=now,
            legs=(
                ExternalLeg(selection="Tides ML", market="moneyline", odds_decimal=Decimal("2.0")),
            ),
        )
        return FetchResult(bets=(bet, bet), state=state)


def test_non_retryable_failure_is_not_retried(make_app: AppFactory) -> None:
    broken = BrokenProvider()
    app = make_app()
    app.state.sync_registry = SyncRegistry([broken])
    with TestClient(app) as client:
        headers = auth_headers(client)
        connection = connect(client, headers, provider="broken")
        failure = sync(client, headers, connection["id"], status=502)["error"]
        assert failure["details"] == {
            "run_id": failure["details"]["run_id"],
            "retryable": False,
            "attempts": 1,
        }
        assert broken.calls == 1


def test_duplicates_inside_one_page_are_imported_once(make_app: AppFactory) -> None:
    app = make_app()
    app.state.sync_registry = SyncRegistry([DuplicatingProvider()])
    with TestClient(app) as client:
        headers = auth_headers(client)
        connection = connect(client, headers, provider="dupes")
        run = sync(client, headers, connection["id"])
        assert (run["fetched_count"], run["imported_count"], run["duplicate_count"]) == (2, 1, 1)
        assert len(client.get("/v1/bets", headers=headers).json()) == 1


def test_max_attempts_is_configurable(make_app: AppFactory) -> None:
    with TestClient(make_app(sync_max_attempts=1)) as client:
        headers = auth_headers(client)
        connection = connect(client, headers, simulate_failures=1)
        assert (
            sync(client, headers, connection["id"], status=502)["error"]["details"]["attempts"] == 1
        )
        assert sync(client, headers, connection["id"])["attempts"] == 1


def test_disconnect_and_delete_data(client: TestClient, headers: Headers, app) -> None:  # type: ignore[no-untyped-def]
    manual = client.post(
        "/v1/bets",
        json={
            "bet_type": "straight",
            "stake": 10,
            "sportsbook": "Northline",
            "legs": [{"selection": "x", "market": "moneyline", "odds": -110}],
        },
        headers=headers,
    ).json()
    connection = connect(client, headers)
    sync(client, headers, connection["id"])
    response = client.delete(
        f"/v1/sync/connections/{connection['id']}", params={"delete_data": "true"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json() == {"deleted": True, "bets_deleted": 10, "bets_kept": 0}
    assert [b["id"] for b in client.get("/v1/bets", headers=headers).json()] == [manual["id"]]
    assert client.get("/v1/sync/connections", headers=headers).json() == []
    assert (
        client.get(f"/v1/sync/connections/{connection['id']}/runs", headers=headers).status_code
        == 404
    )
    with app.state.session_factory() as db:
        assert list(db.scalars(select(SyncConnection))) == []
        audit = db.scalar(select(AuditLog).where(AuditLog.action == "sync.disconnect"))
        assert audit.details == {"delete_data": True, "bets": 10}


def test_disconnect_keeping_data_then_reconnect_does_not_duplicate(
    client: TestClient, headers: Headers
) -> None:
    connection = connect(client, headers)
    sync(client, headers, connection["id"])
    response = client.delete(
        f"/v1/sync/connections/{connection['id']}", headers=headers
    )  # default keeps data
    assert response.json() == {"deleted": True, "bets_deleted": 0, "bets_kept": 10}
    kept = client.get("/v1/bets", headers=headers).json()
    assert len(kept) == 10
    assert {b["sync_connection_id"] for b in kept} == {None}
    assert {b["source"] for b in kept} == {"sync"}

    again = connect(client, headers)
    assert again["id"] != connection["id"]
    run = sync(client, headers, again["id"])
    assert (run["imported_count"], run["duplicate_count"]) == (0, 10)
    assert len(client.get("/v1/bets", headers=headers).json()) == 10


def test_sync_requires_authentication_and_is_owner_scoped(
    client: TestClient, headers: Headers, other_headers: Headers, app
) -> None:  # type: ignore[no-untyped-def]
    for method, path in (
        ("GET", "/v1/sync/providers"),
        ("GET", "/v1/sync/connections"),
        ("POST", "/v1/sync/connections"),
        ("POST", "/v1/sync/connections/x/sync"),
        ("GET", "/v1/sync/connections/x/runs"),
        ("DELETE", "/v1/sync/connections/x"),
    ):
        assert client.request(method, path, json={}).status_code == 401, path

    connection = connect(client, headers)
    sync(client, headers, connection["id"])
    base = f"/v1/sync/connections/{connection['id']}"
    assert client.get("/v1/sync/connections", headers=other_headers).json() == []
    assert client.post(f"{base}/sync", headers=other_headers).status_code == 404
    assert client.get(f"{base}/runs", headers=other_headers).status_code == 404
    assert (
        client.delete(base, params={"delete_data": "true"}, headers=other_headers).status_code
        == 404
    )
    assert client.get("/v1/bets", headers=other_headers).json() == []
    assert len(client.get("/v1/bets", headers=headers).json()) == 10

    # The same external ids can be imported by a different user without clashing.
    theirs = connect(client, other_headers)
    assert sync(client, other_headers, theirs["id"])["imported_count"] == 10
    with app.state.session_factory() as db:
        assert len(list(db.scalars(select(Bet)))) == 20


# ---------------------------------------------------------- concurrent import
def test_a_colliding_concurrent_import_is_a_clean_409(
    client: TestClient, headers: Headers, app, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    """Two imports of one account race: the loser hits the unique constraint.

    The first import's duplicate check runs, then a second import commits the same
    external bets before the first one writes. The first one must answer 409
    ``sync_conflict``, not 500, and leave nothing half-written.
    """
    from oddvex_api.sync import router as sync_router
    from oddvex_api.sync import service as sync_service

    connection = connect(client, headers)
    real_run_import = sync_service.run_import
    raced: list[str] = []

    def run_import_then_lose_the_race(db, conn, provider, max_attempts, now=None):  # type: ignore[no-untyped-def]
        run = real_run_import(db, conn, provider, max_attempts, now)
        if not raced:
            # The "other request": same account, its own transaction, commits first.
            with app.state.session_factory() as other:
                other_connection = other.get(SyncConnection, conn.id)
                real_run_import(other, other_connection, provider, max_attempts, now)
                other.commit()
                raced.append(conn.id)
        return run

    monkeypatch.setattr(sync_router.service, "run_import", run_import_then_lose_the_race)
    response = client.post(f"/v1/sync/connections/{connection['id']}/sync", headers=headers)
    assert raced == [connection["id"]]
    assert response.status_code == 409, response.text
    body = response.json()
    assert set(body) == {"error"} and body["error"]["code"] == "sync_conflict"
    assert body["error"]["details"] == {"retryable": True}
    assert "IntegrityError" not in response.text and "UNIQUE" not in response.text.upper()

    # Exactly one copy of each bet exists (the winner's), and one recorded run.
    with app.state.session_factory() as db:
        external_ids = list(db.scalars(select(Bet.external_bet_id)))
    assert external_ids and len(external_ids) == len(set(external_ids))
    runs = client.get(f"/v1/sync/connections/{connection['id']}/runs", headers=headers).json()
    assert len(runs) == 1 and runs[0]["status"] == "succeeded"
    assert runs[0]["imported_count"] == len(external_ids)

    # Trying again, as the error suggests, works and imports nothing twice. (The mock
    # account has two newer bets on its second fetch; the first ten are duplicates.)
    retry = sync(client, headers, connection["id"])
    assert retry["status"] == "succeeded"
    assert retry["duplicate_count"] == len(external_ids) == 10
    assert retry["imported_count"] == 2
    bets = client.get("/v1/bets", headers=headers).json()
    assert len(bets) == 12 and len({b["external_bet_id"] for b in bets}) == 12
