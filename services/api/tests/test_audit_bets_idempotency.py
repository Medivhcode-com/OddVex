"""A repeated ``POST /v1/bets`` with the same ``client_request_id`` stores one bet (mobile#5).

The phone gives up on a request after eight seconds and invites a retry; the first
request may already have been stored. The client sends an id with each new bet and the
same id when it retries: the first request answers 201, every repeat answers 200 with
the bet stored the first time.
"""

from __future__ import annotations

import threading
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from oddvex_api.db import AuditLog, Bet, Notification

from .conftest import EXTERNAL_DATABASE_URL, AppFactory, auth_headers
from .test_platform import assert_envelope

Headers = dict[str, str]
REQUEST_ID = "3f0c1f0a-6c1d-4f6e-9a55-2f1d7e0b9c11"


def bet(**overrides: Any) -> dict[str, Any]:
    return {
        "bet_type": "straight",
        "stake": 20,
        "sportsbook": "Northline",
        "legs": [{"selection": "Harbor City Tides ML", "market": "moneyline", "odds": -110}],
        "placed_at": "2026-03-12T12:00:00Z",
        **overrides,
    }


def stored(app: FastAPI) -> tuple[int, int]:
    """(bets, ``bet.create`` audit rows) in the database."""
    with app.state.session_factory() as db:
        return (
            int(db.scalar(select(func.count()).select_from(Bet)) or 0),
            int(
                db.scalar(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(AuditLog.action == "bet.create")
                )
                or 0
            ),
        )


def test_a_repeat_returns_the_first_bet_with_200_and_stores_nothing(
    client: TestClient, headers: Headers, app: FastAPI
) -> None:
    body = bet(client_request_id=REQUEST_ID)
    first = client.post("/v1/bets", json=body, headers=headers)
    assert first.status_code == 201, first.text
    assert stored(app) == (1, 1)

    for _ in range(3):
        repeat = client.post("/v1/bets", json=body, headers=headers)
        assert repeat.status_code == 200, repeat.text
        assert repeat.json() == first.json()
    assert stored(app) == (1, 1)
    assert client.get("/v1/bets", headers=headers).json() == [first.json()]

    # The response model did not change: the id is not echoed, and the columns that
    # identify an imported bet are not used for it.
    assert "client_request_id" not in first.json()
    assert first.json()["external_bet_id"] is None and first.json()["source"] == "manual"
    with app.state.session_factory() as db:
        row = db.scalars(select(Bet)).one()
    assert row.client_request_id == REQUEST_ID
    assert row.external_provider is None and row.external_bet_id is None


def test_a_repeat_is_answered_with_the_stored_bet_even_if_its_body_differs(
    client: TestClient, headers: Headers, app: FastAPI
) -> None:
    first = client.post("/v1/bets", json=bet(client_request_id=REQUEST_ID), headers=headers)
    assert first.status_code == 201
    different = [
        bet(client_request_id=REQUEST_ID, stake=999, sportsbook="Elsewhere"),
        # A body the checks would refuse as a new bet is still answered as a repeat.
        bet(
            client_request_id=REQUEST_ID,
            legs=[{"selection": "x", "market": "moneyline", "odds": -1000000000}],
        ),
        bet(
            client_request_id=REQUEST_ID,
            legs=[
                {
                    "selection": "x",
                    "market": "moneyline",
                    "odds": -110,
                    "event_id": "evt_gone",
                    "outcome_key": "home",
                }
            ],
        ),
    ]
    for body in different:
        repeat = client.post("/v1/bets", json=body, headers=headers)
        assert repeat.status_code == 200, repeat.text
        assert repeat.json() == first.json()
        assert repeat.json()["stake"] == 20.0 and repeat.json()["sportsbook"] == "Northline"
    assert stored(app) == (1, 1)


def test_a_repeat_is_still_checked_as_a_request(make_app: AppFactory) -> None:
    """What the route description says for client authors: a known id does not get a
    request past the request schema (422) or past the write limit (429)."""
    app = make_app(
        rate_limit_enabled=True,
        rate_limit_auth_per_minute=100,
        rate_limit_user_writes_per_minute=3,
    )
    with TestClient(app) as client:
        headers = auth_headers(client)
        first = client.post("/v1/bets", json=bet(client_request_id=REQUEST_ID), headers=headers)
        assert first.status_code == 201
        no_legs = client.post(
            "/v1/bets", json=bet(client_request_id=REQUEST_ID, legs=[]), headers=headers
        )
        assert no_legs.status_code == 422, no_legs.text
        repeat = client.post("/v1/bets", json=bet(client_request_id=REQUEST_ID), headers=headers)
        assert repeat.status_code == 200 and repeat.json() == first.json()
        # Three writes this minute: the next one is refused, repeat or not.
        limited = client.post("/v1/bets", json=bet(client_request_id=REQUEST_ID), headers=headers)
        assert limited.status_code == 429, limited.text
        assert_envelope(limited.json(), "rate_limited")
        assert stored(app) == (1, 1)


def test_bets_without_an_id_or_with_different_ids_are_separate_bets(
    client: TestClient, headers: Headers, app: FastAPI
) -> None:
    assert client.post("/v1/bets", json=bet(), headers=headers).status_code == 201
    assert client.post("/v1/bets", json=bet(), headers=headers).status_code == 201
    for request_id in ("request-0001", "request-0002"):
        made = client.post("/v1/bets", json=bet(client_request_id=request_id), headers=headers)
        assert made.status_code == 201
    assert stored(app) == (4, 4)
    ids = {b["id"] for b in client.get("/v1/bets", headers=headers).json()}
    assert len(ids) == 4


def test_an_id_is_only_compared_within_one_account_and_is_free_after_a_delete(
    client: TestClient, headers: Headers, other_headers: Headers, app: FastAPI
) -> None:
    body = bet(client_request_id=REQUEST_ID)
    mine = client.post("/v1/bets", json=body, headers=headers)
    theirs = client.post("/v1/bets", json=body, headers=other_headers)
    assert (mine.status_code, theirs.status_code) == (201, 201)
    assert mine.json()["id"] != theirs.json()["id"]
    # Each user's repeat finds that user's own bet.
    assert client.post("/v1/bets", json=body, headers=headers).json()["id"] == mine.json()["id"]
    assert (
        client.post("/v1/bets", json=body, headers=other_headers).json()["id"]
        == theirs.json()["id"]
    )
    assert stored(app) == (2, 2)
    # Once the bet is deleted the id is free: the same id creates a new bet.
    assert client.delete(f"/v1/bets/{mine.json()['id']}", headers=headers).status_code == 204
    again = client.post("/v1/bets", json=body, headers=headers)
    assert again.status_code == 201 and again.json()["id"] != mine.json()["id"]


@pytest.mark.parametrize(
    "request_id",
    ["short-1", "x" * 65, "has space 1", "semi;colon1", "ünïcödé-id", "new\nline-01", "", 12345678],
)
def test_the_id_must_be_8_to_64_url_safe_characters(
    client: TestClient, headers: Headers, app: FastAPI, request_id: Any
) -> None:
    response = client.post("/v1/bets", json=bet(client_request_id=request_id), headers=headers)
    assert response.status_code == 422, response.text
    assert_envelope(response.json(), "validation_error")
    assert response.json()["error"]["details"][0]["loc"] == ["body", "client_request_id"]
    assert stored(app) == (0, 0)


@pytest.mark.parametrize("request_id", ["a" * 8, "Z" * 64, "aZ09_-aZ09_-", REQUEST_ID])
def test_ids_of_the_documented_shape_are_accepted(
    client: TestClient, headers: Headers, request_id: str
) -> None:
    made = client.post("/v1/bets", json=bet(client_request_id=request_id), headers=headers)
    assert made.status_code == 201, made.text
    assert (
        client.post("/v1/bets", json=bet(client_request_id=request_id), headers=headers).status_code
        == 200
    )


def test_a_repeat_runs_no_second_stake_reminder_and_writes_no_second_audit_row(
    client: TestClient, headers: Headers, app: FastAPI
) -> None:
    threshold = client.put(
        "/v1/me/stake-reminder", json={"weekly_stake_threshold": 30}, headers=headers
    )
    assert threshold.status_code == 200, threshold.text
    body = bet(client_request_id=REQUEST_ID, stake=20)
    assert client.post("/v1/bets", json=body, headers=headers).status_code == 201
    # 20 of 30: no reminder yet. A repeat that was stored again would make it 40.
    for _ in range(2):
        assert client.post("/v1/bets", json=body, headers=headers).status_code == 200
    reminder = client.get("/v1/me/stake-reminder", headers=headers).json()
    assert reminder["staked_this_week"] == 20.0 and reminder["exceeded"] is False
    with app.state.session_factory() as db:
        reminders = db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.kind == "stake_reminder")
        )
        actions = list(
            db.scalars(
                select(AuditLog.action).where(
                    AuditLog.action.in_(["bet.create", "stake_reminder.reached"])
                )
            )
        )
    assert reminders == 0 and actions == ["bet.create"]

    # A second, different bet crosses the threshold once; its repeat adds nothing.
    crossing = bet(client_request_id="another-request-1", stake=15)
    assert client.post("/v1/bets", json=crossing, headers=headers).status_code == 201
    assert client.post("/v1/bets", json=crossing, headers=headers).status_code == 200
    with app.state.session_factory() as db:
        reminders = db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.kind == "stake_reminder")
        )
        reached = db.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action == "stake_reminder.reached")
        )
    assert reminders == 1 and reached == 1
    assert stored(app) == (2, 2)


def test_a_repeat_is_answered_at_the_bet_cap_and_under_no_other_users_id(
    make_app: AppFactory,
) -> None:
    app = make_app(max_bets_per_user=1)
    with TestClient(app) as client:
        headers = auth_headers(client)
        body = bet(client_request_id=REQUEST_ID)
        first = client.post("/v1/bets", json=body, headers=headers)
        assert first.status_code == 201
        # The account is full: a new bet is refused, the repeat is still answered.
        assert client.post("/v1/bets", json=bet(), headers=headers).status_code == 409
        repeat = client.post("/v1/bets", json=body, headers=headers)
        assert repeat.status_code == 200 and repeat.json() == first.json()
        assert stored(app) == (1, 1)


def test_a_retry_that_arrives_while_the_first_request_is_in_flight_gets_the_first_bet(
    client: TestClient, headers: Headers, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The retry finds nothing when it looks, then the first request commits, then the
    retry inserts: the unique index refuses it and it answers with the first bet."""
    from oddvex_api.bets import router as bets_router

    user_id = client.get("/v1/me", headers=headers).json()["id"]
    real_create = bets_router.service.create_bet
    first_ids: list[str] = []

    def create_after_the_first_request_commits(owner: str, data: Any) -> Bet:
        if not first_ids:
            # The "first request": same user and id, its own transaction, commits now,
            # after this request's look-up and before its insert.
            with app.state.session_factory() as other:
                first = real_create(owner, data)
                other.add(first)
                other.commit()
                first_ids.append(first.id)
        return real_create(owner, data)

    monkeypatch.setattr(bets_router.service, "create_bet", create_after_the_first_request_commits)
    response = client.post("/v1/bets", json=bet(client_request_id=REQUEST_ID), headers=headers)
    assert response.status_code == 200, response.text
    assert [response.json()["id"]] == first_ids
    assert "IntegrityError" not in response.text
    with app.state.session_factory() as db:
        rows = list(db.scalars(select(Bet).where(Bet.user_id == user_id)))
        audit = db.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "bet.create")
        )
    assert [row.id for row in rows] == first_ids
    assert audit == 0  # the losing request wrote nothing, not even an audit row


def test_a_retry_in_flight_is_answered_when_the_first_request_took_the_last_free_slot(
    make_app: AppFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The retry finds nothing when it looks, then the first request commits and fills
    the account. The retry must answer with that bet, not with ``bet_limit_reached``."""
    from oddvex_api.bets import router as bets_router

    app = make_app(max_bets_per_user=2)
    with TestClient(app) as client:
        headers = auth_headers(client)
        assert client.post("/v1/bets", json=bet(), headers=headers).status_code == 201
        real_create = bets_router.service.create_bet
        first_ids: list[str] = []

        def create_after_the_first_request_commits(owner: str, data: Any) -> Bet:
            if not first_ids:
                with app.state.session_factory() as other:
                    first = real_create(owner, data)
                    other.add(first)
                    other.commit()
                    first_ids.append(first.id)
            return real_create(owner, data)

        monkeypatch.setattr(
            bets_router.service, "create_bet", create_after_the_first_request_commits
        )
        body = bet(client_request_id=REQUEST_ID)
        response = client.post("/v1/bets", json=body, headers=headers)
        assert response.status_code == 200, response.text
        assert [response.json()["id"]] == first_ids
        assert stored(app) == (2, 1)  # the losing request wrote no bet and no audit row
        # A different bet is still refused: the account is full.
        full = client.post(
            "/v1/bets", json=bet(client_request_id="another-request-1"), headers=headers
        )
        assert full.status_code == 409
        assert_envelope(full.json(), "bet_limit_reached")


def _post_together(
    client: TestClient, headers: Headers, body: dict[str, Any], count: int
) -> list[tuple[int, str]]:
    """``count`` identical creates sent at the same moment: (status, bet id or error text)."""
    barrier = threading.Barrier(count)
    results: list[tuple[int, str]] = []
    lock = threading.Lock()

    def post() -> None:
        barrier.wait()
        response = client.post("/v1/bets", json=body, headers=headers)
        with lock:
            results.append((response.status_code, response.json().get("id", response.text)))

    threads = [threading.Thread(target=post) for _ in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    return results


def test_parallel_requests_with_one_id_for_the_last_free_slot_are_all_answered(
    make_app: AppFactory,
) -> None:
    """One 201 and otherwise 200, never 409: the bet was stored, so no request may be
    told that the account is full."""
    app = make_app(max_bets_per_user=3)
    with TestClient(app) as client:
        headers = auth_headers(client)
        for _ in range(2):
            assert client.post("/v1/bets", json=bet(), headers=headers).status_code == 201
        for round_number in range(4):
            body = bet(client_request_id=f"last-slot-round-{round_number}")
            results = _post_together(client, headers, body, 8)
            statuses = sorted(status for status, _ in results)
            assert statuses == [200] * 7 + [201], results
            assert len({bet_id for _, bet_id in results}) == 1
            # One bet and one audit row more per round (the audit rows of deleted bets stay).
            assert stored(app) == (3, 3 + round_number)
            # Make room again for the next round.
            made = results[0][1]
            assert client.delete(f"/v1/bets/{made}", headers=headers).status_code == 204


def test_the_database_itself_refuses_a_second_bet_with_the_same_id(
    client: TestClient, headers: Headers, other_headers: Headers, app: FastAPI
) -> None:
    from oddvex_api.bets import service
    from oddvex_api.bets.schemas import BetCreate

    mine = client.get("/v1/me", headers=headers).json()["id"]
    theirs = client.get("/v1/me", headers=other_headers).json()["id"]
    data = BetCreate.model_validate(bet(client_request_id=REQUEST_ID))
    plain = BetCreate.model_validate(bet())
    with app.state.session_factory() as db:
        db.add(service.create_bet(mine, data))
        db.add(service.create_bet(theirs, data))  # another user: allowed
        db.add(service.create_bet(mine, plain))  # no id: never collides
        db.add(service.create_bet(mine, plain))
        db.commit()
        db.add(service.create_bet(mine, data))
        with pytest.raises(IntegrityError):
            db.commit()


def test_parallel_requests_with_one_id_store_one_bet(make_app: AppFactory) -> None:
    app = make_app()
    with TestClient(app) as client:
        headers = auth_headers(client)
        body = bet(client_request_id=REQUEST_ID)
        barrier = threading.Barrier(6)
        results: list[tuple[int, str]] = []
        lock = threading.Lock()

        def post() -> None:
            barrier.wait()
            response = client.post("/v1/bets", json=body, headers=headers)
            with lock:
                results.append((response.status_code, response.json().get("id", response.text)))

        threads = [threading.Thread(target=post) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)
        statuses = sorted(status for status, _ in results)
        assert statuses == [200, 200, 200, 200, 200, 201], results
        assert len({bet_id for _, bet_id in results}) == 1
        assert stored(app) == (1, 1)


@pytest.mark.skipif(
    EXTERNAL_DATABASE_URL is None,
    reason="needs row locks: SQLite has none, PostgreSQL (the server's database) does",
)
def test_parallel_creates_cannot_pass_the_bet_cap(make_app: AppFactory) -> None:
    app = make_app(max_bets_per_user=3)
    with TestClient(app) as client:
        headers = auth_headers(client)
        barrier = threading.Barrier(8)
        statuses: list[int] = []
        lock = threading.Lock()

        def post() -> None:
            barrier.wait()
            response = client.post("/v1/bets", json=bet(), headers=headers)
            with lock:
                statuses.append(response.status_code)

        threads = [threading.Thread(target=post) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)
        assert sorted(statuses) == [201, 201, 201, 409, 409, 409, 409, 409]
        assert stored(app) == (3, 3)


def test_the_route_documents_the_field_and_the_200_answer(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/v1/bets"]["post"]
    assert set(operation["responses"]) >= {"200", "201", "409", "422", "429"}
    assert "client_request_id" in operation["description"]
    assert "200" in operation["description"] and "differs" in operation["description"]
    field = schema["components"]["schemas"]["BetCreate"]["properties"]["client_request_id"]
    options = field["anyOf"]
    text = next(option for option in options if option.get("type") == "string")
    assert (text["minLength"], text["maxLength"]) == (8, 64)
    assert text["pattern"] == "^[A-Za-z0-9_-]{8,64}$"
    assert "client_request_id" not in schema["components"]["schemas"]["BetCreate"]["required"]
    # The response model is unchanged: no such property on BetOut.
    assert "client_request_id" not in schema["components"]["schemas"]["BetOut"]["properties"]
