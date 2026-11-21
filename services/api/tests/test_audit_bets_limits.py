"""Limits on what one account can store and what one request can load (api-auth#2).

A stored cap on bets per user, shared by manual creates and imports; per-user limits on
bet writes and on the export, keyed on the user id; an export that is streamed in
batches; and summary, analytics and auto-settle that never load the whole account as
mapped rows.
"""

from __future__ import annotations

import contextlib
import json
import re
import threading
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, update

from oddvex_api.account import export as account_export
from oddvex_api.account.schemas import AccountExportOut
from oddvex_api.bets import service as bets_service
from oddvex_api.community import service as community_service
from oddvex_api.db import (
    AuditLog,
    Bet,
    BetLeg,
    CommunityBlock,
    CommunityComment,
    CommunityFollow,
    CommunityLike,
    CommunityPick,
    CommunityProfile,
    CommunityReport,
    SyncConnection,
    SyncImportRun,
)
from oddvex_api.ratelimit import CoarseWindowCounter
from oddvex_api.sync import (
    Authorization,
    ExternalBet,
    ExternalLeg,
    FetchResult,
    SyncProviderInfo,
    SyncRegistry,
)

from .conftest import EXTERNAL_DATABASE_URL, AppFactory, auth_headers, register
from .test_platform import assert_envelope

Headers = dict[str, str]


def bet(**overrides: Any) -> dict[str, Any]:
    return {
        "bet_type": "straight",
        "stake": 10,
        "sportsbook": "Northline",
        "legs": [{"selection": "Harbor City Tides ML", "market": "moneyline", "odds": -110}],
        **overrides,
    }


def create(client: TestClient, headers: Headers, **overrides: Any) -> dict[str, Any]:
    response = client.post("/v1/bets", json=bet(**overrides), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


_LIMIT = re.compile(r"LIMIT (\?|%\((\w+)\)s)")


def row_limit(statement: str, parameters: Any) -> int | None:
    """The value bound to a statement's LIMIT, or None when it has none.

    Read from the parameters actually sent, on SQLite (``LIMIT ?``) and PostgreSQL
    (``LIMIT %(name)s``): the compiled statement is cached and does not carry it.
    """
    match = _LIMIT.search(statement)
    if match is None:
        return None
    if match.group(2):
        return int(parameters[match.group(2)])
    return int(parameters[statement[: match.start()].count("?")])


def ids_bound(statement: str, parameters: Any) -> int:
    """How many ids a statement with ``bets.id IN (...)`` was sent."""
    if isinstance(parameters, dict):
        return sum(1 for name in parameters if name.startswith("id_"))
    inside = statement[statement.index("bets.id IN") :]
    return inside[: inside.index(")")].count("?")


def left_out(run: dict[str, Any]) -> int:
    """Bets a run fetched and neither imported nor skipped as already imported."""
    return int(run["fetched_count"] - run["imported_count"] - run["duplicate_count"])


def bet_count(app: FastAPI) -> int:
    with app.state.session_factory() as db:
        return int(db.scalar(select(func.count()).select_from(Bet)) or 0)


# ------------------------------------------------------------------ bet cap
def test_the_bet_cap_refuses_the_next_bet_like_the_watchlist_cap(make_app: AppFactory) -> None:
    app = make_app(max_bets_per_user=3)
    with TestClient(app) as client:
        headers = auth_headers(client)
        kept = [create(client, headers, stake=10 + i) for i in range(3)]
        full = client.post("/v1/bets", json=bet(), headers=headers)
        assert full.status_code == 409, full.text
        assert_envelope(full.json(), "bet_limit_reached")
        assert full.json()["error"]["details"] == {"max_bets": 3}
        assert "3" in full.json()["error"]["message"]
        assert bet_count(app) == 3
        with app.state.session_factory() as db:
            created = db.scalar(
                select(func.count()).select_from(AuditLog).where(AuditLog.action == "bet.create")
            )
        assert created == 3  # the refused create wrote nothing

        # Updating and settling never add a bet, so they still work at the cap ...
        patched = client.patch(f"/v1/bets/{kept[0]['id']}", json={"stake": 99}, headers=headers)
        assert patched.status_code == 200 and patched.json()["stake"] == 99.0
        settled = client.post(
            f"/v1/bets/{kept[1]['id']}/settle", json={"result": "won"}, headers=headers
        )
        assert settled.status_code == 200
        assert bet_count(app) == 3
        # ... and keep to the field limits a create has.
        too_many_legs = client.patch(
            f"/v1/bets/{kept[0]['id']}",
            json={"bet_type": "parlay", "legs": bet()["legs"] * 21},
            headers=headers,
        )
        long_notes = client.patch(
            f"/v1/bets/{kept[0]['id']}", json={"notes": "n" * 2001}, headers=headers
        )
        assert too_many_legs.status_code == 422 and long_notes.status_code == 422

        # Deleting one makes room for exactly one.
        assert client.delete(f"/v1/bets/{kept[2]['id']}", headers=headers).status_code == 204
        create(client, headers)
        assert client.post("/v1/bets", json=bet(), headers=headers).status_code == 409

        # The cap is per user.
        other = auth_headers(client, "grace@example.test")
        create(client, other)


def test_the_default_cap_and_its_environment_variable(
    make_settings, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    from oddvex_api.config import Settings

    assert make_settings().max_bets_per_user == 5000
    monkeypatch.setenv("ODDVEX_MAX_BETS_PER_USER", "7")
    assert Settings(_env_file=None).max_bets_per_user == 7


class ManyBetsProvider:
    """A provider with ``total`` settled bets, ids ``many-0000`` onwards."""

    info = SyncProviderInfo(
        "many", "Many", "A long history", is_mock=True, requires_credentials=False
    )

    def __init__(self, total: int) -> None:
        self.total = total

    def authorize(self, options: dict[str, Any], now: datetime) -> Authorization:
        return Authorization(label="Many", state={"imports": 0})

    def fetch_bets(self, state: dict[str, Any], now: datetime) -> FetchResult:
        bets = tuple(
            ExternalBet(
                external_bet_id=f"many-{index:04d}",
                bet_type="straight",
                sportsbook="Many",
                stake=Decimal("10"),
                placed_at=datetime(2026, 3, 1, 12, index % 60, tzinfo=UTC),
                legs=(
                    ExternalLeg(selection="Tides ML", market="moneyline", odds_decimal=Decimal(2)),
                ),
            )
            for index in range(self.total)
        )
        return FetchResult(bets=bets, state={**state, "imports": int(state["imports"]) + 1})


def test_an_import_stops_at_the_cap_and_says_how_many_bets_it_left_out(
    make_app: AppFactory,
) -> None:
    app = make_app(max_bets_per_user=5)
    app.state.sync_registry = SyncRegistry([ManyBetsProvider(8)])
    with TestClient(app) as client:
        headers = auth_headers(client)
        manual = [create(client, headers) for _ in range(2)]
        connection = client.post(
            "/v1/sync/connections", json={"provider": "many"}, headers=headers
        ).json()
        url = f"/v1/sync/connections/{connection['id']}/sync"

        first = client.post(url, headers=headers)
        assert first.status_code == 200, first.text
        run = first.json()
        assert run["status"] == "succeeded"
        assert (run["fetched_count"], run["imported_count"], run["duplicate_count"]) == (8, 3, 0)
        assert left_out(run) == 5
        assert "5 bets were not imported" in run["error_message"]
        assert "at most 5 bets" in run["error_message"]
        assert bet_count(app) == 5
        imported = sorted(
            b["external_bet_id"]
            for b in client.get("/v1/bets", headers=headers).json()
            if b["source"] == "sync"
        )
        assert imported == ["many-0000", "many-0001", "many-0002"]  # the provider's order
        # A manual create is refused too: imports and creates share the one cap.
        assert client.post("/v1/bets", json=bet(), headers=headers).status_code == 409
        with app.state.session_factory() as db:
            details = db.scalars(
                select(AuditLog.details).where(AuditLog.action == "sync.import")
            ).one()
            state = db.scalars(select(SyncConnection.provider_state)).one()
        assert details["imported"] == 3 and details["not_imported"] == 5
        assert details["over_limit"] == 5 and details["rejected"] == 0
        # The provider's position is not moved past bets that were left out for room.
        assert state == {"imports": 0}

        # At the cap an import brings in nothing and says so.
        second = client.post(url, headers=headers).json()
        assert (second["imported_count"], second["duplicate_count"]) == (0, 3)
        assert left_out(second) == 5 and bet_count(app) == 5

        # Room made by deleting is filled by the next import, in order.
        for made in manual:
            assert client.delete(f"/v1/bets/{made['id']}", headers=headers).status_code == 204
        third = client.post(url, headers=headers).json()
        assert (third["imported_count"], third["duplicate_count"]) == (2, 3)
        assert left_out(third) == 3 and bet_count(app) == 5
        history = client.get(f"/v1/sync/connections/{connection['id']}/runs", headers=headers)
        assert [left_out(r) for r in history.json()] == [3, 5, 5]
        # The reason is kept with each run, so the history says it too.
        assert all("not imported" in r["error_message"] for r in history.json())


def sync_notices(client: TestClient, headers: Headers) -> list[dict[str, Any]]:
    """The account's import notifications, newest first."""
    response = client.get("/v1/notifications", headers=headers)
    assert response.status_code == 200, response.text
    return [n for n in response.json()["items"] if n["kind"] == "sync_finished"]


class UnstorableFirstProvider(ManyBetsProvider):
    """``ManyBetsProvider`` whose first ``unstorable`` bets have a price of 1.0, a value
    that cannot be stored, so the import leaves them out (counted as rejected)."""

    def __init__(self, total: int, unstorable: int) -> None:
        super().__init__(total)
        self.unstorable = unstorable

    def fetch_bets(self, state: dict[str, Any], now: datetime) -> FetchResult:
        result = super().fetch_bets(state, now)
        leg = ExternalLeg(selection="Tides ML", market="moneyline", odds_decimal=Decimal(1))
        bets = tuple(
            replace(item, legs=(leg,)) if index < self.unstorable else item
            for index, item in enumerate(result.bets)
        )
        return replace(result, bets=bets)


@pytest.mark.parametrize(
    ("cap", "fetched", "unstorable", "imported", "sentence"),
    [
        pytest.param(
            5, 8, 0, 5, "3 bets were not imported; the import history says why.", id="cap"
        ),
        pytest.param(
            3, 4, 0, 3, "1 bet was not imported; the import history says why.", id="cap-one"
        ),
        # A bet left out because a value cannot be stored counts the same, with room to spare.
        pytest.param(
            10,
            4,
            1,
            3,
            "1 bet was not imported; the import history says why.",
            id="rejected-one",
        ),
        pytest.param(
            10,
            6,
            2,
            4,
            "2 bets were not imported; the import history says why.",
            id="rejected",
        ),
        # Both reasons in one run: 2 rejected, then 6 storable bets for 5 places.
        pytest.param(
            5,
            8,
            2,
            5,
            "3 bets were not imported; the import history says why.",
            id="rejected-and-cap",
        ),
    ],
)
def test_the_import_notification_says_how_many_bets_the_run_left_out(
    make_app: AppFactory, cap: int, fetched: int, unstorable: int, imported: int, sentence: str
) -> None:
    app = make_app(max_bets_per_user=cap)
    app.state.sync_registry = SyncRegistry([UnstorableFirstProvider(fetched, unstorable)])
    with TestClient(app) as client:
        headers = auth_headers(client)
        connection = client.post(
            "/v1/sync/connections", json={"provider": "many"}, headers=headers
        ).json()
        run = client.post(f"/v1/sync/connections/{connection['id']}/sync", headers=headers).json()
        assert run["status"] == "succeeded" and run["imported_count"] == imported
        assert left_out(run) == fetched - imported
        [notice] = sync_notices(client, headers)
        assert notice["title"] == "Import finished"
        assert notice["body"].startswith(
            f"Many import finished: {imported} new, 0 already imported."
        )
        assert notice["body"].endswith(sentence)


def test_the_import_notification_says_nothing_was_left_out_when_nothing_was(
    client: TestClient, headers: Headers
) -> None:
    connection = client.post("/v1/sync/connections", json={}, headers=headers).json()
    run = client.post(f"/v1/sync/connections/{connection['id']}/sync", headers=headers).json()
    assert left_out(run) == 0
    [notice] = sync_notices(client, headers)
    assert "not imported" not in notice["body"]


@pytest.mark.skipif(
    EXTERNAL_DATABASE_URL is None,
    reason="needs row locks: SQLite has none, PostgreSQL (the server's database) does",
)
def test_an_import_and_creates_at_the_same_moment_cannot_pass_the_bet_cap(
    make_app: AppFactory,
) -> None:
    """An import waits on the same row lock as a create, so the two together stop at the
    cap. Without the lock in the import the account ended two to four bets over."""
    cap = 12
    app = make_app(max_bets_per_user=cap)
    app.state.sync_registry = SyncRegistry([ManyBetsProvider(cap)])
    lock = threading.Lock()
    with TestClient(app) as client:
        for attempt in range(3):  # three accounts, one race each
            headers = auth_headers(client, f"racer{attempt}@example.test")
            user_id = client.get("/v1/me", headers=headers).json()["id"]
            connection = client.post(
                "/v1/sync/connections", json={"provider": "many"}, headers=headers
            ).json()
            barrier = threading.Barrier(9)
            answers: list[tuple[str, int]] = []

            def send(
                kind: str,
                url: str,
                body: dict[str, Any] | None,
                headers: Headers = headers,
                barrier: threading.Barrier = barrier,
                answers: list[tuple[str, int]] = answers,
            ) -> None:
                barrier.wait()
                response = client.post(url, json=body, headers=headers)
                with lock:
                    answers.append((kind, response.status_code))

            sync_url = f"/v1/sync/connections/{connection['id']}/sync"
            threads = [threading.Thread(target=send, args=("import", sync_url, None))]
            threads += [
                threading.Thread(target=send, args=("create", "/v1/bets", bet())) for _ in range(8)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=60)
            assert len(answers) == 9 and ("import", 200) in answers, answers
            assert {status for kind, status in answers if kind == "create"} <= {201, 409}
            with app.state.session_factory() as db:
                stored = db.scalar(
                    select(func.count()).select_from(Bet).where(Bet.user_id == user_id)
                )
            # Every create that was accepted is stored and the import filled the rest.
            assert stored == cap, answers


def test_an_import_with_room_for_everything_reports_nothing_left_out(
    client: TestClient, headers: Headers
) -> None:
    connection = client.post("/v1/sync/connections", json={}, headers=headers).json()
    run = client.post(f"/v1/sync/connections/{connection['id']}/sync", headers=headers).json()
    assert run["imported_count"] == 10 and left_out(run) == 0
    assert run["error_message"] is None


# ------------------------------------------------------- per-user write limit
def test_bet_writes_are_limited_per_user_and_not_per_address(make_app: AppFactory) -> None:
    app = make_app(
        rate_limit_enabled=True,
        rate_limit_auth_per_minute=100,
        rate_limit_user_writes_per_minute=4,
    )
    with TestClient(app) as client:
        ada = auth_headers(client, "ada@example.test")
        grace = auth_headers(client, "grace@example.test")
        made = [create(client, ada) for _ in range(2)]
        # Every bet write counts: create, update, settle, auto-settle, delete.
        assert (
            client.patch(f"/v1/bets/{made[0]['id']}", json={"stake": 5}, headers=ada).status_code
            == 200
        )
        assert (
            client.post(
                f"/v1/bets/{made[0]['id']}/settle", json={"result": "won"}, headers=ada
            ).status_code
            == 200
        )
        blocked = [
            client.post("/v1/bets", json=bet(), headers=ada),
            client.patch(f"/v1/bets/{made[1]['id']}", json={"stake": 6}, headers=ada),
            client.post(f"/v1/bets/{made[1]['id']}/settle", json={"result": "won"}, headers=ada),
            client.post("/v1/bets/auto-settle", headers=ada),
            client.delete(f"/v1/bets/{made[1]['id']}", headers=ada),
        ]
        for response in blocked:
            assert response.status_code == 429, response.text
            assert_envelope(response.json(), "rate_limited")
            retry_after = int(response.headers["Retry-After"])
            assert 1 <= retry_after <= 60
            assert response.json()["error"]["details"] == {"retry_after_seconds": retry_after}
        assert bet_count(app) == 2  # nothing was written by the refused requests
        # Reads are not limited by it.
        assert client.get("/v1/bets", headers=ada).status_code == 200
        assert client.get("/v1/bets/summary", headers=ada).status_code == 200
        # The same address, another user: not limited. The key is the user id.
        create(client, grace)
        # Another address, the same user: still limited.
        app.state.settings.trust_proxy = True
        elsewhere = client.post(
            "/v1/bets", json=bet(), headers={**ada, "X-Forwarded-For": "203.0.113.9"}
        )
        assert elsewhere.status_code == 429


def test_the_write_limit_also_has_a_daily_ceiling(make_app: AppFactory) -> None:
    app = make_app(
        rate_limit_enabled=True,
        rate_limit_user_writes_per_minute=100,
        rate_limit_user_writes_per_day=3,
    )
    with TestClient(app) as client:
        headers = auth_headers(client)
        for _ in range(3):
            create(client, headers)
        blocked = client.post("/v1/bets", json=bet(), headers=headers)
        assert blocked.status_code == 429, blocked.text
        assert_envelope(blocked.json(), "rate_limited")
        # The wait is counted against the day, not the minute.
        assert 60 < int(blocked.headers["Retry-After"]) <= 86_400
        assert bet_count(app) == 3


def test_sync_writes_share_the_write_limit(make_app: AppFactory) -> None:
    app = make_app(rate_limit_enabled=True, rate_limit_user_writes_per_minute=3)
    with TestClient(app) as client:
        headers = auth_headers(client)
        connection = client.post("/v1/sync/connections", json={}, headers=headers)
        assert connection.status_code == 201
        url = f"/v1/sync/connections/{connection.json()['id']}/sync"
        assert client.post(url, headers=headers).status_code == 200
        assert client.post(url, headers=headers).status_code == 200
        blocked = client.post(url, headers=headers)
        assert blocked.status_code == 429 and "Retry-After" in blocked.headers
        assert client.post("/v1/bets", json=bet(), headers=headers).status_code == 429
        assert client.get("/v1/sync/connections", headers=headers).status_code == 200
        # Disconnecting is a write too: refused, and the connection is still there.
        disconnect = client.delete(
            f"/v1/sync/connections/{connection.json()['id']}", headers=headers
        )
        assert disconnect.status_code == 429 and "Retry-After" in disconnect.headers
        assert_envelope(disconnect.json(), "rate_limited")
        assert len(client.get("/v1/sync/connections", headers=headers).json()) == 1


def test_write_limit_defaults_and_off_switch(make_app: AppFactory, make_settings) -> None:  # type: ignore[no-untyped-def]
    settings = make_settings()
    assert settings.rate_limit_user_writes_per_minute == 120
    assert settings.rate_limit_user_writes_per_day == 2000
    assert settings.rate_limit_export_per_hour == 10
    # With the limiter off (the test default) nothing is counted.
    app = make_app(rate_limit_user_writes_per_minute=1, rate_limit_export_per_hour=1)
    with TestClient(app) as client:
        headers = auth_headers(client)
        for _ in range(3):
            create(client, headers)
            assert client.get("/v1/me/export", headers=headers).status_code == 200


def test_the_coarse_counter_counts_a_window_in_buckets() -> None:
    now = [1_000_000.0]
    counter = CoarseWindowCounter(window_seconds=86_400, buckets=24, clock=lambda: now[0])
    assert counter.check("u", 2) == (True, 0.0)
    now[0] += 3_600
    assert counter.check("u", 2) == (True, 0.0)
    allowed, retry_after = counter.check("u", 2)
    assert allowed is False
    # The first hit leaves the window when its hour bucket does: within the day, and no
    # later than a full window from now.
    assert 79_200 <= retry_after <= 86_400
    assert counter.check("someone-else", 2) == (True, 0.0)
    now[0] += retry_after
    assert counter.check("u", 2)[0] is True
    assert counter.check("u", 2)[0] is False
    # A refused request is not counted, so the wait does not grow by asking again.
    again = counter.check("u", 2)[1]
    assert counter.check("u", 2)[1] == again
    now[0] += 2 * 86_400
    assert counter.check("u", 2) == (True, 0.0)
    assert counter.size() == 1  # keys with nothing left in the window are dropped


# ------------------------------------------------------------- export limit
def test_the_export_has_its_own_lower_limit_per_user(make_app: AppFactory) -> None:
    app = make_app(
        rate_limit_enabled=True,
        rate_limit_auth_per_minute=100,
        rate_limit_export_per_hour=2,
        rate_limit_user_streams_at_once=1,
    )
    with TestClient(app) as client:
        ada = auth_headers(client, "ada@example.test")
        grace = auth_headers(client, "grace@example.test")
        assert client.get("/v1/me/export", headers=ada).status_code == 200
        assert client.get("/v1/me/export", headers=ada).status_code == 200
        blocked = client.get("/v1/me/export", headers=ada)
        assert blocked.status_code == 429, blocked.text
        assert_envelope(blocked.json(), "rate_limited")
        assert 60 < int(blocked.headers["Retry-After"]) <= 3_600
        # The refused export gave back its place among the streamed responses (one at
        # a time here): the bet list still answers, and the next export is refused for
        # the hour, not for want of a place.
        assert client.get("/v1/bets", headers=ada).status_code == 200
        again = client.get("/v1/me/export", headers=ada)
        assert again.status_code == 429 and int(again.headers["Retry-After"]) > 60
        assert client.get("/v1/bets", headers=ada).status_code == 200
        # A refused export is not audited as an export.
        with app.state.session_factory() as db:
            exports = db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action == "account.export")
            )
        assert exports == 2
        assert client.get("/v1/me/export", headers=grace).status_code == 200
        # The export limit does not use up the write limit, or the other way round.
        create(client, ada)


# ----------------------------------------------------------- streamed export
def _fill(client: TestClient, headers: Headers, count: int) -> None:
    for index in range(count):
        made = create(
            client,
            headers,
            stake=5 + index,
            notes=f'note {index} éè "quoted" \\ </script>',
            placed_at=f"2026-02-{1 + index % 28:02d}T12:00:00Z",
        )
        if index % 3 == 0:
            client.post(f"/v1/bets/{made['id']}/settle", json={"result": "won"}, headers=headers)


def test_the_export_is_one_json_document_of_the_documented_shape_read_in_batches(
    client: TestClient, headers: Headers, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(account_export, "BET_BATCH", 4)
    monkeypatch.setattr(account_export, "AUDIT_BATCH", 5)
    _fill(client, headers, 11)
    listed = client.get("/v1/bets", headers=headers).json()
    assert len(listed) == 11

    limits: list[int | None] = []

    def record(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        # Statements that read whole rows of the two tables that grow with an account
        # (sums and counts over them return one row and are not what this is about).
        text = " ".join(statement.split())
        if text.startswith("SELECT") and ("bets.notes" in text or "audit_log.action" in text):
            limits.append(row_limit(text, parameters))

    event.listen(app.state.engine, "before_cursor_execute", record)
    try:
        with client.stream("GET", "/v1/me/export", headers=headers) as response:
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/json"
            assert response.headers["cache-control"] == "no-store"
            assert "content-length" not in response.headers  # streamed, not buffered
            chunks = list(response.iter_raw())
    finally:
        event.remove(app.state.engine, "before_cursor_execute", record)
    assert len(chunks) > 3  # the document left in pieces

    # No statement read the account's bets or audit rows without a row limit.
    assert limits and all(limit is not None and limit <= 5 for limit in limits), limits

    body = json.loads(b"".join(chunks))
    document = AccountExportOut.model_validate(body)
    assert document.format_version == 1
    assert list(body) == list(AccountExportOut.model_fields)  # same keys, same order
    # The streamed text is exactly what the response model serialises to.
    expected = json.dumps(
        document.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":")
    )
    assert b"".join(chunks).decode() == expected

    # Every bet once, oldest first, each identical to what the bet routes return.
    assert [b["placed_at"] for b in body["bets"]] == sorted(b["placed_at"] for b in body["bets"])
    assert {b["id"]: b for b in body["bets"]} == {b["id"]: b for b in listed}
    assert len(body["bets"]) == 11
    # Every audit row once, oldest first, ending with this export.
    with app.state.session_factory() as db:
        audit_ids = list(db.scalars(select(AuditLog.id).order_by(AuditLog.created_at, AuditLog.id)))
    assert [entry["id"] for entry in body["audit_log"]] == audit_ids
    assert len(audit_ids) == 1 + 11 + 4 + 1  # register, creates, settles, this export
    assert body["audit_log"][-1]["action"] == "account.export"


def test_the_export_reads_import_runs_in_batches_too(
    client: TestClient, headers: Headers, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every import stores a run and nothing removes them, so the history grows with the
    account like bets and audit entries do. It must not be read in one go."""
    monkeypatch.setattr(account_export, "RUN_BATCH", 2)
    connection = client.post("/v1/sync/connections", json={}, headers=headers).json()
    for _ in range(5):
        run = client.post(f"/v1/sync/connections/{connection['id']}/sync", headers=headers)
        assert run.status_code == 200, run.text

    limits: list[int | None] = []

    def record(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        text = " ".join(statement.split())
        if text.startswith("SELECT") and "sync_import_runs.attempts" in text:
            limits.append(row_limit(text, parameters))

    event.listen(app.state.engine, "before_cursor_execute", record)
    try:
        response = client.get("/v1/me/export", headers=headers)
    finally:
        event.remove(app.state.engine, "before_cursor_execute", record)
    assert response.status_code == 200
    # No statement read run rows without a row limit, and none more than a batch.
    assert limits and all(limit is not None and limit <= 2 for limit in limits), limits
    assert len(limits) >= 3  # five runs, two at a time

    body = response.json()
    with app.state.session_factory() as db:
        run_ids = list(
            db.scalars(
                select(SyncImportRun.id).order_by(SyncImportRun.started_at, SyncImportRun.id)
            )
        )
    assert len(run_ids) == 5
    assert [run["id"] for run in body["sync_runs"]] == run_ids  # each once, oldest first
    history = client.get(f"/v1/sync/connections/{connection['id']}/runs", headers=headers).json()
    assert {run["id"]: run for run in body["sync_runs"]} == {run["id"]: run for run in history}
    # Still exactly the text the response model serialises to.
    document = AccountExportOut.model_validate(body)
    expected = json.dumps(
        document.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":")
    )
    assert response.content.decode() == expected


def _community_rows(app: FastAPI, user_id: str, other_id: str) -> None:
    """Seven picks, seven comments and five reports of ``user_id``, all on one timestamp,
    plus a like, a follow and a block. Written straight into the tables."""
    moment = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)

    def pick(owner: str, number: int, **extra: Any) -> CommunityPick:
        return CommunityPick(
            user_id=owner,
            event_id=f"event-{number}",
            league="nba",
            event_label="Harbor City Tides at Summit Peaks",
            selection="Summit Peaks -3.5",
            event_start_time=moment,
            market="spread",
            outcome_key="home",
            line=Decimal("-3.5"),
            price_decimal=Decimal("1.909091"),
            sportsbook_key="northline",
            sportsbook_name="Northline",
            analysis=f'analysis {number} éè "quoted" </script>',
            posted_at=moment,
            **extra,
        )

    with app.state.session_factory() as db:
        db.add(CommunityProfile(user_id=user_id, handle="ada_l", bio="bio", is_public=True))
        db.add(CommunityProfile(user_id=other_id, handle="grace_h", is_public=True))
        mine = [pick(user_id, number) for number in range(7)]
        mine[2].moderation_status = "hidden"
        mine[3].status, mine[3].result, mine[3].graded_at = "graded", "won", moment
        mine[3].home_score, mine[3].away_score = 101, 99
        theirs = pick(other_id, 100)
        db.add_all([*mine, theirs])
        db.flush()
        for number in range(7):
            db.add(
                CommunityComment(
                    pick_id=(theirs if number % 2 else mine[0]).id,
                    user_id=user_id,
                    body=f"comment {number}",
                    created_at=moment,
                    moderation_status="removed" if number == 4 else "visible",
                )
            )
        db.add(CommunityComment(pick_id=mine[0].id, user_id=other_id, body="theirs"))
        for number in range(5):
            db.add(
                CommunityReport(
                    reporter_id=user_id,
                    target_type="pick",
                    target_id=theirs.id,
                    target_user_id=other_id,
                    reason="spam",
                    details=f"report {number}",
                    created_at=moment,
                )
            )
        db.add(CommunityLike(pick_id=theirs.id, user_id=user_id))
        db.add(CommunityLike(pick_id=mine[0].id, user_id=other_id))
        db.add(CommunityFollow(follower_id=user_id, followed_id=other_id))
        db.add(CommunityBlock(blocker_id=user_id, blocked_id=other_id))
        db.commit()


def test_the_export_reads_community_picks_comments_and_reports_in_batches(
    client: TestClient, headers: Headers, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Comments (30 an hour), picks and reports keep growing with an account as long as
    it is used, like bets and audit entries. 100,000 comments read in one go cost one
    export about 370 MiB. They are read and sent in batches too, and the document is the
    one the community's own ``export_out`` describes."""
    for name in ("PICK_BATCH", "COMMENT_BATCH", "REPORT_BATCH"):
        monkeypatch.setattr(account_export, name, 2)
    user_id = client.get("/v1/me", headers=headers).json()["id"]
    other = auth_headers(client, "grace@example.test")
    other_id = client.get("/v1/me", headers=other).json()["id"]
    _community_rows(app, user_id, other_id)

    limits: dict[str, list[int | None]] = {"picks": [], "comments": [], "reports": []}
    whole_rows = {
        "community_picks.analysis": "picks",
        "community_comments.body": "comments",
        "community_reports.details": "reports",
    }

    def record(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        text = " ".join(statement.split())
        for column, name in whole_rows.items():
            if text.startswith("SELECT") and column in text:
                limits[name].append(row_limit(text, parameters))

    event.listen(app.state.engine, "before_cursor_execute", record)
    try:
        response = client.get("/v1/me/export", headers=headers)
    finally:
        event.remove(app.state.engine, "before_cursor_execute", record)
    assert response.status_code == 200, response.text
    # No statement read whole picks, comments or reports without a row limit, and none
    # more than a batch: seven, seven and five rows, two at a time.
    for name, least in (("picks", 4), ("comments", 4), ("reports", 3)):
        assert len(limits[name]) >= least, (name, limits)
        assert all(limit is not None and limit <= 2 for limit in limits[name]), (name, limits)

    body = response.json()
    community = body["community"]
    with app.state.session_factory() as db:
        expected = community_service.export_out(db, user_id, "synthetic")
        pick_ids = list(
            db.scalars(
                select(CommunityPick.id)
                .where(CommunityPick.user_id == user_id)
                .order_by(CommunityPick.id)
            )
        )
        comment_ids = list(
            db.scalars(
                select(CommunityComment.id)
                .where(CommunityComment.user_id == user_id)
                .order_by(CommunityComment.id)
            )
        )
    # Every row once, in the order of (time, id): all share one time here, so the id
    # alone decides where a batch ends. Nobody else's rows.
    assert [p["id"] for p in community["picks"]] == pick_ids and len(pick_ids) == 7
    assert [c["id"] for c in community["comments"]] == comment_ids and len(comment_ids) == 7
    assert len(community["reports"]) == 5
    assert community["following"] == ["grace_h"] and community["blocks"] == ["grace_h"]
    assert len(community["likes"]) == 1 and community["profile"]["handle"] == "ada_l"
    # The same document the community's own export describes ...
    assert community == expected.model_dump(mode="json")
    # The counts on a pick are worked out batch by batch: one pick has three visible
    # comments (the removed one and the blocked author's are not counted) and one like.
    assert sorted(p["comment_count"] for p in community["picks"]) == [0] * 6 + [3]
    assert sorted(p["like_count"] for p in community["picks"]) == [0] * 6 + [1]
    # ... and exactly the text the response model serialises to.
    document = AccountExportOut.model_validate(body)
    text = json.dumps(document.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))
    assert response.content.decode() == text
    assert list(community) == list(type(expected).model_fields)

    # An account that never used the community: the same keys, empty.
    stranger = auth_headers(client, "linus@example.test")
    empty = client.get("/v1/me/export", headers=stranger).json()["community"]
    assert empty == {
        "profile": None,
        "picks": [],
        "comments": [],
        "following": [],
        "likes": [],
        "blocks": [],
        "reports": [],
    }


def test_rows_that_share_a_timestamp_are_exported_once_where_batches_meet(
    client: TestClient, headers: Headers, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bets, import runs and audit entries are paged on (time, id). With every row on one
    timestamp the id alone decides where a batch ends: nothing repeated, nothing lost."""
    for name in ("BET_BATCH", "RUN_BATCH", "AUDIT_BATCH"):
        monkeypatch.setattr(account_export, name, 2)
    connection = client.post("/v1/sync/connections", json={}, headers=headers).json()
    for _ in range(5):
        client.post(f"/v1/sync/connections/{connection['id']}/sync", headers=headers)
    user_id = client.get("/v1/me", headers=headers).json()["id"]
    moment = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    with app.state.session_factory() as db:
        db.execute(update(Bet).values(placed_at=moment))
        db.execute(update(SyncImportRun).values(started_at=moment))
        db.execute(update(AuditLog).values(created_at=moment))
        db.commit()
        bet_ids = sorted(db.scalars(select(Bet.id)))
        run_ids = sorted(db.scalars(select(SyncImportRun.id)))
        audit_ids = sorted(db.scalars(select(AuditLog.id)))
    assert len(bet_ids) >= 5 and len(run_ids) == 5 and len(audit_ids) >= 7

    body = json.loads(b"".join(account_export.stream_export(app, user_id)))
    assert [b["id"] for b in body["bets"]] == bet_ids
    assert [r["id"] for r in body["sync_runs"]] == run_ids
    assert [a["id"] for a in body["audit_log"]] == audit_ids


def test_the_export_keeps_no_database_connection_while_it_waits_for_the_client(
    client: TestClient, headers: Headers, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Between two batches the stream holds no connection, so a client that reads slowly
    cannot tie up the connection pool."""
    monkeypatch.setattr(account_export, "BET_BATCH", 2)
    _fill(client, headers, 5)
    user_id = client.get("/v1/me", headers=headers).json()["id"]
    pool = app.state.engine.pool
    idle_before = pool.checkedout()
    stream = account_export.stream_export(app, user_id)
    seen = 0
    for _ in stream:
        seen += 1
        assert pool.checkedout() == idle_before, "a connection was held between chunks"
    assert seen > 3


def test_auto_settle_reads_pending_bets_in_batches_and_settles_a_bounded_number(
    client: TestClient, headers: Headers, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bets_service, "AUTO_SETTLE_BATCH", 3)
    monkeypatch.setattr(bets_service, "AUTO_SETTLE_MAX_PER_CALL", 4)
    final = client.get("/v1/events", params={"status": "final", "league": "nba"}).json()[0]
    gradeable = {
        "selection": "Home",
        "market": "moneyline",
        "odds": -110,
        "event_id": final["id"],
        "outcome_key": "home",
    }
    for index in range(10):
        # Alternate a bet that can be graded with one that cannot.
        legs = [gradeable] if index % 2 == 0 else bet()["legs"]
        create(client, headers, legs=legs, placed_at=f"2026-03-01T12:{index:02d}:00Z")

    loaded: list[int] = []

    def record(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        text = " ".join(statement.split())
        if text.startswith("SELECT") and "FROM bets" in text and "bets.notes" in text:
            loaded.append(row_limit(text, parameters))

    event.listen(app.state.engine, "before_cursor_execute", record)
    try:
        first = client.post("/v1/bets/auto-settle", headers=headers)
    finally:
        event.remove(app.state.engine, "before_cursor_execute", record)
    assert first.status_code == 200, first.text
    body = first.json()
    assert loaded and all(limit == 3 for limit in loaded), loaded
    assert len(body["settled"]) == 4 and body["has_more"] is True
    # The body is the response model's own JSON.
    assert first.headers["content-type"] == "application/json"
    by_id = {b["id"]: b for b in client.get("/v1/bets", headers=headers).json()}
    assert all(by_id[b["id"]] == b for b in body["settled"])
    # Stopped after the fourth settled bet: seven examined (4 settled, 3 skipped on the way).
    assert body["checked"] == 7 and len(body["skipped"]) == 3
    assert all(b["status"] == "settled" and b["settled_by"] == "auto" for b in body["settled"])

    # ``has_more`` is always sent: false once nothing is left unexamined.
    second = client.post("/v1/bets/auto-settle", headers=headers).json()
    assert set(second) == {"checked", "settled", "skipped", "has_more"}
    assert second["has_more"] is False
    assert len(second["settled"]) == 1
    assert second["checked"] == 6 and len(second["skipped"]) == 5
    third = client.post("/v1/bets/auto-settle", headers=headers).json()
    assert third == {"checked": 5, "settled": [], "skipped": third["skipped"], "has_more": False}
    with app.state.session_factory() as db:
        audited = db.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "bet.auto_settle")
        )
    assert audited == 5


def test_the_bet_list_reads_its_page_in_batches_and_returns_the_same_document(
    client: TestClient, headers: Headers, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    from oddvex_api.bets import router as bets_router
    from oddvex_api.bets.schemas import BetOut

    _fill(client, headers, 9)
    whole = client.get("/v1/bets", headers=headers)
    assert whole.status_code == 200 and len(whole.json()) == 9
    assert whole.headers["content-type"] == "application/json"
    assert "content-length" not in whole.headers  # streamed, not buffered
    # The body is what the response model serialises to.
    as_models = [BetOut.model_validate(item) for item in whole.json()]
    assert (
        whole.content
        == b"[" + b",".join(item.__pydantic_serializer__.to_json(item) for item in as_models) + b"]"
    )

    monkeypatch.setattr(bets_router, "LIST_BATCH", 2)
    limits: list[int | None] = []
    bet_reads: list[int] = []

    def record(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        text = " ".join(statement.split())
        if text.startswith("SELECT") and "bets.notes" in text:
            if "bets.id IN" in text:
                bet_reads.append(ids_bound(text, parameters))
            else:
                limits.append(row_limit(text, parameters))

    event.listen(app.state.engine, "before_cursor_execute", record)
    try:
        batched = client.get("/v1/bets", headers=headers)
        window = client.get("/v1/bets", params={"limit": 5, "offset": 1}, headers=headers)
        tail = client.get("/v1/bets", params={"limit": 4, "offset": 7}, headers=headers)
        beyond = client.get("/v1/bets", params={"offset": 50}, headers=headers)
        by_stake = client.get("/v1/bets", params={"sort": "stake", "limit": 3}, headers=headers)
    finally:
        event.remove(app.state.engine, "before_cursor_execute", record)
    # Whole bets are only ever read a batch at a time (by id, so the statement that reads
    # them carries no LIMIT: the batch is the list of ids).
    assert not limits, limits
    assert bet_reads and max(bet_reads) <= 2, bet_reads
    assert batched.content == whole.content
    assert window.json() == whole.json()[1:6]
    assert tail.json() == whole.json()[7:9]
    assert beyond.json() == [] and beyond.content == b"[]"
    assert [b["stake"] for b in by_stake.json()] == [5.0, 6.0, 7.0]


def test_the_bet_list_is_sent_a_batch_at_a_time_and_holds_no_connection_in_between(
    client: TestClient, headers: Headers, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A request holds one batch of bets, not the page: fifteen list requests at once
    for an account of large bets took the API past its memory limit before."""
    from oddvex_api.bets import router as bets_router

    monkeypatch.setattr(bets_router, "LIST_BATCH", 2)
    _fill(client, headers, 7)
    whole = client.get("/v1/bets", headers=headers)
    ids = [b["id"] for b in whole.json()]
    user_id = client.get("/v1/me", headers=headers).json()["id"]
    pool = app.state.engine.pool
    idle = pool.checkedout()
    chunks = []
    for chunk in bets_router.page_chunks(app.state.session_factory, user_id, ids):
        chunks.append(chunk)
        assert pool.checkedout() == idle, "a connection was held between chunks"
    # Four batches of at most two bets, then the closing bracket.
    assert len(chunks) == 5
    assert [len(json.loads(b"[" + c.lstrip(b"[,") + b"]")) for c in chunks[:4]] == [2, 2, 2, 1]
    assert b"".join(chunks) == whole.content
    # Somebody else's ids are never read, whatever is asked for.
    stranger = auth_headers(client, "grace@example.test")
    other_id = client.get("/v1/me", headers=stranger).json()["id"]
    assert b"".join(bets_router.page_chunks(app.state.session_factory, other_id, ids)) == b"[]"


def test_the_list_and_export_routes_hold_one_connection_at_most_while_they_send(
    client: TestClient, headers: Headers, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Through the routes, not the generators: while a batch is turned into JSON the only
    connection out of the pool is that batch's own. The route has given its own back
    before the first byte, so readers that stall cannot use up the pool (two accounts
    with eight stalled lists each would otherwise hold all fifteen connections)."""
    from oddvex_api.bets import router as bets_router

    monkeypatch.setattr(bets_router, "LIST_BATCH", 2)
    monkeypatch.setattr(account_export, "BET_BATCH", 2)
    _fill(client, headers, 5)
    pool = app.state.engine.pool
    idle = pool.checkedout()
    real_json = bets_service.bet_json
    during_a_batch: list[int] = []
    at_checkout: list[int] = []

    def spy(row: Bet) -> bytes:
        during_a_batch.append(pool.checkedout())
        return real_json(row)

    def checked_out(dbapi_connection: Any, record: Any, proxy: Any) -> None:
        at_checkout.append(pool.checkedout())

    monkeypatch.setattr(bets_service, "bet_json", spy)
    event.listen(app.state.engine, "checkout", checked_out)
    try:
        for path in ("/v1/bets", "/v1/me/export"):
            during_a_batch.clear()
            at_checkout.clear()
            response = client.get(path, headers=headers)
            assert response.status_code == 200, response.text
            document = response.json()
            assert len(document if path == "/v1/bets" else document["bets"]) == 5
            # Five bets in batches of two: the batch's own session and nothing else.
            assert during_a_batch == [idle + 1] * 5, (path, during_a_batch)
            # And at no moment of the request were two connections out at once.
            assert len(at_checkout) > 3 and max(at_checkout) == idle + 1, (path, at_checkout)
            assert pool.checkedout() == idle
    finally:
        event.remove(app.state.engine, "checkout", checked_out)


def test_a_page_of_the_bet_list_is_decided_by_one_statement(
    client: TestClient, headers: Headers, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bets of a page and their order come from one statement, so a bet created or
    deleted while the page is being sent cannot make another bet appear twice or go
    missing. A bet deleted in between is left out."""
    from oddvex_api.bets import router as bets_router

    monkeypatch.setattr(bets_router, "LIST_BATCH", 2)
    _fill(client, headers, 5)
    ids = [b["id"] for b in client.get("/v1/bets", headers=headers).json()]
    user_id = client.get("/v1/me", headers=headers).json()["id"]
    stream = bets_router.page_chunks(app.state.session_factory, user_id, ids)
    first = next(stream)
    # While the client is still reading: a newer bet arrives and an unsent one goes.
    create(client, headers, placed_at="2026-03-10T12:00:00Z")
    assert client.delete(f"/v1/bets/{ids[3]}", headers=headers).status_code == 204
    document = json.loads(first + b"".join(stream))
    assert [b["id"] for b in document] == [ids[0], ids[1], ids[2], ids[4]]


def test_a_streamed_response_that_fails_part_way_is_never_a_whole_document(
    client: TestClient, headers: Headers, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Once a streamed response has started its status is 200, whatever happens next. If a
    batch then cannot be read (no database connection in time, say) the text stops there.
    The closing bracket is only ever sent last, so what arrived cannot be parsed and a
    part of a page or of an export is never taken for the whole."""
    from oddvex_api.bets import router as bets_router

    monkeypatch.setattr(bets_router, "LIST_BATCH", 2)
    for name in ("BET_BATCH", "RUN_BATCH", "AUDIT_BATCH"):
        monkeypatch.setattr(account_export, name, 2)
    _fill(client, headers, 5)
    connection = client.post("/v1/sync/connections", json={}, headers=headers).json()
    client.post(f"/v1/sync/connections/{connection['id']}/sync", headers=headers)
    user_id = client.get("/v1/me", headers=headers).json()["id"]
    ids = [b["id"] for b in client.get("/v1/bets", headers=headers).json()]

    def fails_at(module: Any, name: str, number: int) -> None:
        """Make the ``number``-th call of ``module.name`` fail from now on."""
        real = getattr(module, name)
        calls = [0]

        def flaky(*args: Any, **kwargs: Any) -> Any:
            calls[0] += 1
            if calls[0] == number:
                raise TimeoutError("no database connection")
            return real(*args, **kwargs)

        monkeypatch.setattr(module, name, flaky)

    def collect(chunks: Any) -> tuple[bytes, bool]:
        got = b""
        try:
            for chunk in chunks:
                got += chunk
        except TimeoutError:
            return got, False
        return got, True

    def every_failure_point(module: Any, name: str, stream: Any) -> int:
        """Fail at the first batch, then the second, and so on until the stream gets
        through: each part that arrived must not parse. Returns how many were tried."""
        real = getattr(module, name)
        tried = 0
        while True:
            fails_at(module, name, tried + 1)
            text, whole = collect(stream())
            monkeypatch.setattr(module, name, real)
            if whole:
                json.loads(text)
                return tried
            tried += 1
            with pytest.raises(ValueError):
                json.loads(text)

    factory = app.state.session_factory
    page_batches = every_failure_point(
        bets_router, "_batch_json", lambda: bets_router.page_chunks(factory, user_id, ids)
    )
    assert page_batches >= 3  # at least five bets, two at a time
    export_batches = every_failure_point(
        account_export, "_read_batch", lambda: account_export.stream_export(app, user_id)
    )
    assert export_batches >= 6  # bets, import runs and audit entries, each in batches


def test_one_user_can_have_only_so_many_streamed_responses_at_once(
    make_app: AppFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A streamed response holds a batch for as long as the client takes to read it, so
    the number one user has in progress is limited: the list and the export together."""
    app = make_app(
        rate_limit_enabled=True,
        rate_limit_auth_per_minute=100,
        rate_limit_user_streams_at_once=1,
        rate_limit_export_per_hour=2,
    )
    real_json = bets_service.bet_json
    started, go_on = threading.Event(), threading.Event()
    held: list[int] = []

    def slow_once(row: Bet) -> bytes:
        if not held:
            held.append(1)
            started.set()
            assert go_on.wait(timeout=30)
        return real_json(row)

    with TestClient(app) as client:
        ada = auth_headers(client, "ada@example.test")
        grace = auth_headers(client, "grace@example.test")
        create(client, ada)
        create(client, grace)
        monkeypatch.setattr(bets_service, "bet_json", slow_once)
        answers: list[int] = []
        first = threading.Thread(
            target=lambda: answers.append(client.get("/v1/bets", headers=ada).status_code)
        )
        first.start()
        try:
            assert started.wait(timeout=30)
            # Ada's first response is still being produced: her next ones are refused.
            for path in ("/v1/bets", "/v1/me/export"):
                refused = client.get(path, headers=ada)
                assert refused.status_code == 429, refused.text
                assert_envelope(refused.json(), "rate_limited")
                assert int(refused.headers["Retry-After"]) >= 1
            # Another user is not affected.
            assert client.get("/v1/bets", headers=grace).status_code == 200
            assert client.get("/v1/me/export", headers=grace).status_code == 200
        finally:
            go_on.set()
            first.join(timeout=30)
        assert answers == [200]
        # The slot came back with the end of the response.
        assert client.get("/v1/bets", headers=ada).status_code == 200
        # The refused export was not audited and did not use up the hourly export limit.
        assert client.get("/v1/me/export", headers=ada).status_code == 200
        assert client.get("/v1/me/export", headers=ada).status_code == 200
        with app.state.session_factory() as db:
            exports = db.scalars(
                select(AuditLog.user_id).where(AuditLog.action == "account.export")
            ).all()
        assert len(exports) == 3  # two of Ada's, one of Grace's


def test_the_default_number_of_streams_at_once(make_settings) -> None:  # type: ignore[no-untyped-def]
    assert make_settings().rate_limit_user_streams_at_once == 8


def test_a_stream_gives_its_slot_back_however_it_ends() -> None:
    import asyncio
    import gc

    from oddvex_api.ratelimit import UserStreamResponse

    scope = {"type": "http", "asgi": {"spec_version": "2.4"}}

    async def receive() -> dict[str, Any]:  # pragma: no cover - never called
        return {"type": "http.disconnect"}

    def run(send: Any, content: Any) -> list[str]:
        given_back: list[str] = []
        response = UserStreamResponse(
            content, lambda: given_back.append("back"), media_type="application/json"
        )
        with contextlib.suppress(Exception):
            asyncio.run(response(scope, receive, send))
        return given_back

    async def accept(message: dict[str, Any]) -> None:
        return None

    sent: list[str] = []

    async def client_goes_away(message: dict[str, Any]) -> None:
        sent.append(message["type"])
        if len(sent) > 2:
            raise OSError("connection lost")

    def breaks() -> Any:
        yield b"["
        raise RuntimeError("the database went away")

    assert run(accept, iter([b"[", b"]"])) == ["back"]  # sent in full
    assert run(client_goes_away, iter([b"[", b"1", b"]"])) == ["back"]  # cut short
    assert run(accept, breaks()) == ["back"]  # failed part-way

    # Never sent at all: the slot comes back when the response is dropped.
    given_back: list[str] = []
    response = UserStreamResponse(iter([b"[]"]), lambda: given_back.append("back"), "text/plain")
    del response
    gc.collect()
    assert given_back == ["back"]


def test_a_slot_given_back_twice_frees_one_slot_not_two(make_app: AppFactory) -> None:
    """The call that gives a slot back can run twice (when the response ends and again
    when it is discarded). The second call must not free a slot that another response
    of the same user is still using."""
    from types import SimpleNamespace

    from oddvex_api.errors import ApiError
    from oddvex_api.ratelimit import _in_progress, take_user_stream_slot

    app = make_app(rate_limit_enabled=True, rate_limit_user_streams_at_once=2)
    request: Any = SimpleNamespace(app=app)
    counter = _in_progress(app, "streams")
    first = take_user_stream_slot(request, "ada")
    second = take_user_stream_slot(request, "ada")
    assert counter.active("ada") == 2
    first()
    first()
    assert counter.active("ada") == 1  # the second response still holds its slot
    third = take_user_stream_slot(request, "ada")
    with pytest.raises(ApiError) as refused:
        take_user_stream_slot(request, "ada")
    assert refused.value.status_code == 429
    second()
    third()
    third()
    assert counter.active("ada") == 0


def test_one_user_runs_one_auto_settle_at_a_time(
    make_app: AppFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auto-settle holds up to 200 bets while it works. Calls of one user that overlap
    would each hold that much, and would settle the same bets twice."""
    app = make_app(rate_limit_enabled=True, rate_limit_auth_per_minute=100)
    real = bets_service.auto_settle
    started, go_on = threading.Event(), threading.Event()
    calls: list[str] = []

    def slow_once(db: Any, user_id: str, *args: Any, **kwargs: Any) -> Any:
        calls.append(user_id)
        if len(calls) == 1:
            started.set()
            assert go_on.wait(timeout=30)
        return real(db, user_id, *args, **kwargs)

    with TestClient(app) as client:
        ada = auth_headers(client, "ada@example.test")
        grace = auth_headers(client, "grace@example.test")
        monkeypatch.setattr(bets_service, "auto_settle", slow_once)
        answers: list[int] = []
        first = threading.Thread(
            target=lambda: answers.append(
                client.post("/v1/bets/auto-settle", headers=ada).status_code
            )
        )
        first.start()
        try:
            assert started.wait(timeout=30)
            refused = client.post("/v1/bets/auto-settle", headers=ada)
            assert refused.status_code == 429, refused.text
            assert_envelope(refused.json(), "rate_limited")
            assert int(refused.headers["Retry-After"]) >= 1
            assert client.post("/v1/bets/auto-settle", headers=grace).status_code == 200
        finally:
            go_on.set()
            first.join(timeout=30)
        assert answers == [200]
        assert client.post("/v1/bets/auto-settle", headers=ada).status_code == 200
        assert len(calls) == 3  # the refused call never started


def test_summary_and_analytics_never_load_mapped_bets_or_their_notes(
    client: TestClient, headers: Headers, app: FastAPI
) -> None:
    """They read plain columns: no notes, no selections, and one row per leg at most."""
    _fill(client, headers, 6)
    parlay = create(
        client,
        headers,
        bet_type="parlay",
        legs=[
            {"selection": "A", "market": "moneyline", "odds": 120, "closing_odds": 110},
            {"selection": "B", "market": "total", "odds": -105, "closing_odds": -112},
        ],
    )
    client.post(f"/v1/bets/{parlay['id']}/settle", json={"result": "won"}, headers=headers)
    with app.state.session_factory() as db:
        mapped = list(db.scalars(select(Bet).where(Bet.user_id.is_not(None))))
        expected_summary = bets_service.summarize(mapped).model_dump(mode="json")

    statements: list[str] = []

    def record(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        statements.append(" ".join(statement.split()))

    event.listen(app.state.engine, "before_cursor_execute", record)
    try:
        summary = client.get("/v1/bets/summary", headers=headers)
        analytics = client.get("/v1/bets/analytics", headers=headers)
    finally:
        event.remove(app.state.engine, "before_cursor_execute", record)
    assert summary.status_code == 200 and analytics.status_code == 200
    bet_reads = [s for s in statements if "FROM bets" in s or "FROM bet_legs" in s]
    assert bet_reads
    for statement in bet_reads:
        assert "notes" not in statement and "selection" not in statement, statement
        assert "event_label" not in statement, statement
    # The same numbers as the calculation over the mapped rows.
    assert summary.json() == expected_summary
    assert summary.json()["totals"]["clv_sample"] == 1
    assert analytics.json()["clv"]["sample"] == 1
    assert analytics.json()["settled_count"] == 3


def test_export_of_another_users_data_is_never_mixed_in_by_the_batches(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(account_export, "BET_BATCH", 2)
    monkeypatch.setattr(account_export, "AUDIT_BATCH", 2)
    ada = register(client, "ada@example.test")
    grace = register(client, "grace@example.test")
    ada_headers = {"Authorization": f"Bearer {ada['access_token']}"}
    grace_headers = {"Authorization": f"Bearer {grace['access_token']}"}
    # Interleave the two accounts so their rows alternate in time.
    for index in range(5):
        create(client, ada_headers, notes=f"ada-{index}", placed_at="2026-03-01T12:00:00Z")
        create(client, grace_headers, notes=f"grace-{index}", placed_at="2026-03-01T12:00:00Z")
    body = client.get("/v1/me/export", headers=ada_headers).json()
    assert sorted(b["notes"] for b in body["bets"]) == [f"ada-{i}" for i in range(5)]
    assert len({b["id"] for b in body["bets"]}) == 5  # equal timestamps: none lost or repeated
    assert "grace" not in json.dumps(body)
    assert len(body["audit_log"]) == 1 + 5 + 1
    assert len({entry["id"] for entry in body["audit_log"]}) == 7


def test_leg_rows_of_the_summary_are_scoped_to_the_user(
    client: TestClient, headers: Headers, other_headers: Headers, app: FastAPI
) -> None:
    mine = create(
        client,
        headers,
        legs=[{"selection": "A", "market": "spread", "odds": 120, "closing_odds": 110}],
    )
    theirs = create(
        client,
        other_headers,
        legs=[{"selection": "B", "market": "total", "odds": -105, "closing_odds": -150}],
    )
    for made, who in ((mine, headers), (theirs, other_headers)):
        client.post(f"/v1/bets/{made['id']}/settle", json={"result": "won"}, headers=who)
    user_id = client.get("/v1/me", headers=headers).json()["id"]
    leg_reads: list[tuple[str, Any]] = []

    def record(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        text = " ".join(statement.split())
        if text.startswith("SELECT") and "FROM bet_legs" in text:
            leg_reads.append((text, parameters))

    event.listen(app.state.engine, "before_cursor_execute", record)
    try:
        summary = client.get("/v1/bets/summary", headers=headers).json()
    finally:
        event.remove(app.state.engine, "before_cursor_execute", record)
    # The statement that reads legs names the user, so it reads this user's legs only
    # (the result would be the same without it; the load would be every user's legs).
    assert len(leg_reads) == 1
    statement, parameters = leg_reads[0]
    assert "bets.user_id =" in statement
    bound = parameters.values() if isinstance(parameters, dict) else parameters
    assert user_id in list(bound)
    assert [row["key"] for row in summary["by_market"]] == ["spread"]
    assert summary["totals"]["clv_sample"] == 1
    assert summary["totals"]["avg_clv"] == mine["clv"]
    with app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(BetLeg)) == 2


def test_disconnecting_with_delete_data_removes_the_bets_and_their_legs_in_one_statement(
    client: TestClient, headers: Headers, app: FastAPI
) -> None:
    kept = create(client, headers)
    connection = client.post("/v1/sync/connections", json={}, headers=headers).json()
    client.post(f"/v1/sync/connections/{connection['id']}/sync", headers=headers)
    with app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Bet)) == 11  # 1 + 10 imported
        assert (db.scalar(select(func.count()).select_from(BetLeg)) or 0) > 11

    statements: list[str] = []

    def record(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        statements.append(" ".join(statement.split()))

    event.listen(app.state.engine, "before_cursor_execute", record)
    try:
        response = client.delete(
            f"/v1/sync/connections/{connection['id']}",
            params={"delete_data": "true"},
            headers=headers,
        )
    finally:
        event.remove(app.state.engine, "before_cursor_execute", record)
    assert response.json() == {"deleted": True, "bets_deleted": 10, "bets_kept": 0}
    # The imported bets were never loaded: no statement read their rows.
    assert not [s for s in statements if s.startswith("SELECT") and "bets.notes" in s]
    assert len([s for s in statements if s.startswith("DELETE FROM bets")]) == 1
    with app.state.session_factory() as db:
        assert list(db.scalars(select(Bet.id))) == [kept["id"]]
        assert db.scalar(select(func.count()).select_from(BetLeg)) == 1


def test_the_sliding_limiter_forgets_keys_nobody_has_used_inside_the_window() -> None:
    from oddvex_api.ratelimit import SlidingWindowRateLimiter, user_rate_limit

    now = [0.0]
    limiter = SlidingWindowRateLimiter(window_seconds=60, clock=lambda: now[0])
    for index in range(10_001):
        limiter.check(f"user-{index}", 5)
    now[0] = 120.0  # every one of those hits has left the window
    limiter.check("someone-new", 5)
    assert set(limiter._hits) == {"someone-new"}

    with pytest.raises(ValueError, match="unknown per-user rate limit bucket"):
        user_rate_limit("no-such-bucket")


def test_giving_a_slot_back_never_waits_for_the_counters_lock() -> None:
    """A slot can be given back by a finaliser (a streamed response that was dropped
    without being sent), and a finaliser can run in the middle of the counter's own code,
    in the thread that holds its lock. Giving back must not wait for that lock: it would
    wait for ever, and the next response to end would stop the server with it."""
    from oddvex_api.ratelimit import InProgressCounter

    counter = InProgressCounter()
    assert counter.enter("ada", 2) and counter.enter("ada", 2) and counter.enter("grace", 1)
    assert not counter.enter("ada", 2)
    with counter._lock:  # what such a finaliser meets
        giving_back = threading.Thread(target=counter.leave, args=("ada",))
        giving_back.start()
        giving_back.join(timeout=5)
        returned = not giving_back.is_alive()
    giving_back.join(timeout=5)
    assert returned, "leave() waited for the lock"
    # The slot is back for the next call that looks, and only that one slot.
    assert counter.active("ada") == 1 and counter.active("grace") == 1
    assert counter.enter("ada", 2) and not counter.enter("ada", 2)
    assert not counter.enter("grace", 1)
    for _ in range(2):
        counter.leave("ada")
    counter.leave("grace")
    counter.leave("grace")  # one too many changes nothing
    assert counter.active("ada") == 0 and counter.active("grace") == 0
    assert counter.enter("grace", 1)
