"""A bet is checked against what the database columns can hold before anything is saved.

Prices are stored with six decimal places and at most ten digits before the point, money
with two decimal places and at most twelve before it. A price that would be stored as
1.000000 or less, a stake that would be stored as 0.00 and a price or payout too large
for its column are refused with 422, and a refused request leaves no row behind. Rows that
already hold such values (written before these checks, or straight into a test database)
still load everywhere.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from oddvex_api.db import AuditLog, Bet, BetLeg
from oddvex_api.sync import (
    Authorization,
    ExternalBet,
    ExternalLeg,
    FetchResult,
    SyncProviderInfo,
    SyncRegistry,
)

from .conftest import EXTERNAL_DATABASE_URL, AppFactory, auth_headers
from .test_platform import assert_envelope

Headers = dict[str, str]

MAX_ODDS = "9999999999.999999"


def leg(**overrides: Any) -> dict[str, Any]:
    return {"selection": "Harbor City Tides ML", "market": "moneyline", "odds": -110, **overrides}


def straight(**overrides: Any) -> dict[str, Any]:
    return {
        "bet_type": "straight",
        "stake": 10,
        "sportsbook": "Northline",
        "legs": [leg()],
        **overrides,
    }


def parlay(count: int, leg_odds: Any, **overrides: Any) -> dict[str, Any]:
    """A parlay of ``count`` legs at American ``leg_odds``; ``overrides`` go on the bet."""
    return {
        "bet_type": "parlay",
        "stake": 10,
        "sportsbook": "Northline",
        "legs": [leg(selection=f"Leg {i}", odds=leg_odds) for i in range(count)],
        **overrides,
    }


def create(client: TestClient, headers: Headers, body: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/v1/bets", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def left_out(run: dict[str, Any]) -> int:
    """Bets a run fetched and neither imported nor skipped as already imported."""
    return int(run["fetched_count"] - run["imported_count"] - run["duplicate_count"])


def counts(app: FastAPI) -> tuple[int, int, int]:
    """(bets, legs, bet audit rows) stored right now."""
    with app.state.session_factory() as db:
        return (
            int(db.scalar(select(func.count()).select_from(Bet)) or 0),
            int(db.scalar(select(func.count()).select_from(BetLeg)) or 0),
            int(
                db.scalar(
                    select(func.count()).select_from(AuditLog).where(AuditLog.action.like("bet.%"))
                )
                or 0
            ),
        )


def every_read_works(client: TestClient, headers: Headers) -> None:
    for path in ("/v1/bets", "/v1/bets/summary", "/v1/bets/analytics", "/v1/me/export"):
        response = client.get(path, headers=headers)
        assert response.status_code == 200, f"{path}: {response.text[:300]}"
        response.json()


# ------------------------------------------------------------ refused on create
REFUSED_ON_CREATE = [
    # quant-data#3: a price that rounds to exactly 1.000000 at six decimal places.
    pytest.param(straight(legs=[leg(odds=-1000000000)]), "invalid_decimal_odds", id="american"),
    pytest.param(
        straight(legs=[leg(odds="-200000001")]), "invalid_decimal_odds", id="american-text"
    ),
    pytest.param(
        straight(legs=[leg(odds="1.0000004", odds_format="decimal")]),
        "invalid_decimal_odds",
        id="decimal",
    ),
    pytest.param(
        straight(legs=[leg(odds="1/3000000", odds_format="fractional")]),
        "invalid_decimal_odds",
        id="fractional",
    ),
    pytest.param(
        straight(legs=[leg(closing_odds=-1000000000)]), "invalid_decimal_odds", id="closing"
    ),
    pytest.param(
        straight(legs=[leg(closing_odds=-110, closing_opposite_odds=-1000000000)]),
        "invalid_decimal_odds",
        id="closing-opposite",
    ),
    pytest.param(
        parlay(2, -110, odds="1.0000001", odds_format="decimal"),
        "invalid_decimal_odds",
        id="bet-level-price",
    ),
    # api-data#3: a stake that rounds to 0.00.
    pytest.param(straight(stake=0.004), "invalid_stake", id="stake"),
    pytest.param(straight(stake=0.0049999), "invalid_stake", id="stake-just-under-half-a-cent"),
    # api-data#4: more than the price column (ten digits before the point) can hold.
    pytest.param(
        straight(legs=[leg(odds="10000000000", odds_format="decimal")]),
        "odds_out_of_range",
        id="one-price-too-long",
    ),
    pytest.param(
        straight(legs=[leg(odds="1e30", odds_format="decimal")]),
        "odds_out_of_range",
        id="one-price-far-too-long",
    ),
    pytest.param(
        straight(legs=[leg(odds="1e9999999")]), "odds_out_of_range", id="price-with-huge-exponent"
    ),
    pytest.param(
        straight(legs=[leg(closing_odds="1e30", odds_format="decimal", odds=2)]),
        "odds_out_of_range",
        id="closing-too-long",
    ),
    pytest.param(parlay(10, 900), "odds_out_of_range", id="parlay-of-ten-at-plus-900"),
    pytest.param(parlay(12, 600), "odds_out_of_range", id="parlay-of-twelve-at-plus-600"),
    pytest.param(parlay(20, 300), "odds_out_of_range", id="parlay-of-twenty-at-plus-300"),
    pytest.param(
        parlay(2, -110, odds="1e30", odds_format="decimal"),
        "odds_out_of_range",
        id="bet-level-price-too-long",
    ),
    # The money columns hold twelve digits before the point: stake x price must fit.
    pytest.param(
        straight(stake=1_000_000, legs=[leg(odds="1000001", odds_format="decimal")]),
        "payout_out_of_range",
        id="payout",
    ),
]


@pytest.mark.parametrize(("body", "code"), REFUSED_ON_CREATE)
def test_a_bet_that_cannot_be_stored_is_refused_and_nothing_is_saved(
    client: TestClient, headers: Headers, app: FastAPI, body: dict[str, Any], code: str
) -> None:
    before = counts(app)
    response = client.post("/v1/bets", json=body, headers=headers)
    assert response.status_code == 422, response.text
    assert_envelope(response.json(), code)
    assert counts(app) == before == (0, 0, 0)
    # The account is untouched: every read still answers.
    assert client.get("/v1/bets", headers=headers).json() == []
    assert client.get("/v1/bets/summary", headers=headers).json()["totals"]["pending_count"] == 0
    every_read_works(client, headers)


def test_values_at_the_edge_of_what_can_be_stored_are_accepted(
    client: TestClient, headers: Headers, app: FastAPI
) -> None:
    shortest = create(client, headers, straight(legs=[leg(odds="1.000001", odds_format="decimal")]))
    assert shortest["potential_payout"] == 10.0 and shortest["potential_profit"] == 0.0
    longest = create(
        client, headers, straight(stake=1, legs=[leg(odds=MAX_ODDS, odds_format="decimal")])
    )
    assert longest["potential_payout"] == 10_000_000_000.0
    # Half a cent rounds up to one cent, as before: only a stake stored as 0.00 is refused.
    cent = create(client, headers, straight(stake=0.005))
    assert cent["stake"] == 0.01
    # The largest stake at the longest price whose payout still fits the money column.
    create(
        client,
        headers,
        straight(stake=1_000_000, legs=[leg(odds="999999.99", odds_format="decimal")]),
    )
    with app.state.session_factory() as db:
        stored = sorted(Decimal(str(value)) for value in db.scalars(select(BetLeg.odds_decimal)))
    assert stored[0] == Decimal("1.000001")
    if EXTERNAL_DATABASE_URL is None:
        # SQLite keeps numbers as floating point: sixteen digits survive, give or take.
        assert float(stored[-1]) == pytest.approx(float(MAX_ODDS), rel=1e-12)
    else:
        assert stored[-1] == Decimal(MAX_ODDS)  # PostgreSQL keeps every digit
    every_read_works(client, headers)
    # A parlay just under the limit is stored; the same parlay one leg longer is not.
    under = create(client, headers, parlay(9, 900))
    assert under["combined_decimal_odds"] == 1_000_000_000.0
    assert client.post("/v1/bets", json=parlay(10, 900), headers=headers).status_code == 422


# ------------------------------------------------------------ refused on update
REFUSED_ON_UPDATE = [
    pytest.param({"stake": 0.004}, "invalid_stake", id="stake"),
    pytest.param({"legs": [leg(odds=-1000000000)]}, "invalid_decimal_odds", id="legs"),
    pytest.param(
        {"legs": [leg(odds="1e30", odds_format="decimal")]}, "odds_out_of_range", id="legs-long"
    ),
    pytest.param(
        {"odds": "1.0000004", "odds_format": "decimal"}, "invalid_decimal_odds", id="price"
    ),
    pytest.param({"odds": "1e30", "odds_format": "decimal"}, "odds_out_of_range", id="price-long"),
    pytest.param(
        {"stake": 1_000_000, "odds": "1000001", "odds_format": "decimal"},
        "payout_out_of_range",
        id="payout",
    ),
    pytest.param(
        {"bet_type": "parlay", "legs": [leg(selection=f"Leg {i}", odds=900) for i in range(10)]},
        "odds_out_of_range",
        id="parlay",
    ),
]


@pytest.mark.parametrize(("change", "code"), REFUSED_ON_UPDATE)
def test_an_update_that_cannot_be_stored_changes_nothing(
    client: TestClient, headers: Headers, app: FastAPI, change: dict[str, Any], code: str
) -> None:
    bet = create(client, headers, straight())
    before = counts(app)
    response = client.patch(f"/v1/bets/{bet['id']}", json=change, headers=headers)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == code
    assert counts(app) == before
    assert client.get(f"/v1/bets/{bet['id']}", headers=headers).json() == bet
    every_read_works(client, headers)


def test_a_stake_change_is_checked_against_the_price_already_stored(
    client: TestClient, headers: Headers
) -> None:
    bet = create(
        client, headers, straight(stake=1, legs=[leg(odds="1000001", odds_format="decimal")])
    )
    response = client.patch(f"/v1/bets/{bet['id']}", json={"stake": 1_000_000}, headers=headers)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "payout_out_of_range"
    assert client.get(f"/v1/bets/{bet['id']}", headers=headers).json() == bet


@pytest.mark.parametrize(
    ("closing", "code"),
    [
        ({"closing_odds": -1000000000}, "invalid_decimal_odds"),
        ({"closing_odds": -110, "closing_opposite_odds": -1000000000}, "invalid_decimal_odds"),
        ({"closing_odds": "1e30", "odds_format": "decimal"}, "odds_out_of_range"),
    ],
)
def test_a_closing_price_that_cannot_be_stored_is_refused(
    client: TestClient, headers: Headers, closing: dict[str, Any], code: str
) -> None:
    bet = create(client, headers, straight())
    leg_id = bet["legs"][0]["id"]
    response = client.patch(
        f"/v1/bets/{bet['id']}",
        json={"closing_odds": [{"leg_id": leg_id, **closing}]},
        headers=headers,
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == code
    # Nothing was written: the bet and the list read back exactly as before.
    assert client.get(f"/v1/bets/{bet['id']}", headers=headers).json() == bet
    assert client.get("/v1/bets", headers=headers).json() == [bet]
    every_read_works(client, headers)


# ------------------------------------------------- a 422 never leaves a row behind
def test_an_error_while_building_the_answer_does_not_keep_the_write(
    client: TestClient, headers: Headers, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The answer is built before the transaction is committed, so a request that ends in
    an error has written nothing, whatever the reason for the error."""
    from oddvex_api.bets import router as bets_router
    from oddvex_api.quant import QuantError

    kept = create(client, headers, straight())
    before = counts(app)
    real_bet_out = bets_router.service.bet_out

    def failing_bet_out(bet: Bet) -> Any:
        raise QuantError("cannot describe this bet", code="invalid_decimal_odds")

    monkeypatch.setattr(bets_router.service, "bet_out", failing_bet_out)
    created = client.post("/v1/bets", json=straight(stake=77), headers=headers)
    patched = client.patch(f"/v1/bets/{kept['id']}", json={"stake": 55}, headers=headers)
    settled = client.post(f"/v1/bets/{kept['id']}/settle", json={"result": "won"}, headers=headers)
    monkeypatch.setattr(bets_router.service, "bet_out", real_bet_out)

    assert (created.status_code, patched.status_code, settled.status_code) == (422, 422, 422)
    assert counts(app) == before
    assert client.get(f"/v1/bets/{kept['id']}", headers=headers).json() == kept
    assert client.get("/v1/bets", headers=headers).json() == [kept]


# ----------------------------------------------------------------- settlement
def test_a_settlement_whose_payout_cannot_be_stored_is_refused(
    client: TestClient, headers: Headers, app: FastAPI
) -> None:
    """Reachable only for a row written before the checks: the payout would overflow."""
    bet = create(client, headers, straight(stake=1, legs=[leg(odds=2, odds_format="decimal")]))
    with app.state.session_factory() as db:
        row = db.get(Bet, bet["id"])
        assert row is not None
        row.stake = Decimal("1000000.00")
        row.odds_decimal = Decimal("1000001.000000")
        row.legs[0].odds_decimal = Decimal("1000001.000000")
        db.commit()
    response = client.post(f"/v1/bets/{bet['id']}/settle", json={"result": "won"}, headers=headers)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "payout_out_of_range"
    after = client.get(f"/v1/bets/{bet['id']}", headers=headers).json()
    assert after["status"] == "pending" and after["payout"] is None
    # A result that returns less still settles.
    lost = client.post(f"/v1/bets/{bet['id']}/settle", json={"result": "lost"}, headers=headers)
    assert lost.status_code == 200 and lost.json()["profit"] == -1_000_000.0


# ----------------------------------------------- rows that already hold such values
OUT_OF_RANGE_MOMENTS = ["9999-12-31T23:59:59-12:00", "0001-01-01T00:00:00+12:00"]


@pytest.mark.parametrize("moment", OUT_OF_RANGE_MOMENTS)
def test_a_date_that_cannot_be_recorded_is_refused_and_nothing_changes(
    client: TestClient, headers: Headers, app: FastAPI, moment: str
) -> None:
    """A time that falls outside the calendar once it is converted to UTC (the form the
    columns hold) was an unhandled error on create, update and settle."""
    refused = client.post("/v1/bets", json=straight(placed_at=moment), headers=headers)
    assert refused.status_code == 422, refused.text
    assert_envelope(refused.json(), "validation_error")
    assert refused.json()["error"]["details"][0]["loc"] == ["body", "placed_at"]
    assert counts(app) == (0, 0, 0)

    made = create(client, headers, straight())
    before = client.get(f"/v1/bets/{made['id']}", headers=headers).json()
    moved = client.patch(f"/v1/bets/{made['id']}", json={"placed_at": moment}, headers=headers)
    settled = client.post(
        f"/v1/bets/{made['id']}/settle",
        json={"result": "won", "settled_at": moment},
        headers=headers,
    )
    for response, field in ((moved, "placed_at"), (settled, "settled_at")):
        assert response.status_code == 422, response.text
        assert_envelope(response.json(), "validation_error")
        assert response.json()["error"]["details"][0]["loc"] == ["body", field]
    assert client.get(f"/v1/bets/{made['id']}", headers=headers).json() == before


@pytest.mark.parametrize("moment", ["0001-01-01T00:00:00Z", "9999-12-31T23:59:59Z"])
def test_the_first_and_last_dates_that_can_be_recorded_load_everywhere(
    client: TestClient, headers: Headers, moment: str
) -> None:
    """The analytics grouped months by a text key that is shorter for a year before 1000
    and answered 500 for as long as such a bet was settled."""
    made = create(client, headers, straight(placed_at=moment))
    settled = client.post(
        f"/v1/bets/{made['id']}/settle",
        json={"result": "won", "settled_at": moment},
        headers=headers,
    )
    assert settled.status_code == 200, settled.text
    every_read_works(client, headers)
    months = client.get("/v1/bets/analytics", headers=headers).json()["by_month"]
    year, month = moment[:4], int(moment[5:7])
    assert [row["key"] for row in months] == [f"{year}-{month:02d}"]
    assert months[0]["label"].endswith(year)


def _poison(app: FastAPI, bet_id: str, **values: Any) -> None:
    """Write values straight into the database, as a release without the checks did."""
    with app.state.session_factory() as db:
        row = db.get(Bet, bet_id)
        assert row is not None
        for name, value in values.items():
            if name.startswith("leg_"):
                setattr(row.legs[0], name[4:], value)
            else:
                setattr(row, name, value)
        db.commit()


def test_rows_stored_before_the_checks_still_load_everywhere(
    client: TestClient, headers: Headers, app: FastAPI
) -> None:
    good = create(client, headers, straight(stake=20, legs=[leg(odds=150)]))
    client.post(f"/v1/bets/{good['id']}/settle", json={"result": "won"}, headers=headers)
    short = create(client, headers, straight(sportsbook="Short price"))
    zero = create(client, headers, straight(sportsbook="Zero stake"))
    closing = create(client, headers, straight(sportsbook="Short close"))
    settled = create(client, headers, straight(sportsbook="Settled short", stake=30))
    client.post(f"/v1/bets/{settled['id']}/settle", json={"result": "lost"}, headers=headers)
    one = Decimal("1.000000")
    _poison(app, short["id"], odds_decimal=one, leg_odds_decimal=one)
    _poison(app, zero["id"], stake=Decimal("0.00"))
    _poison(app, closing["id"], leg_closing_odds_decimal=one, leg_closing_opposite_odds_decimal=one)
    _poison(app, settled["id"], odds_decimal=one, leg_odds_decimal=one)

    listed = client.get("/v1/bets", headers=headers)
    assert listed.status_code == 200, listed.text
    by_book = {bet["sportsbook"]: bet for bet in listed.json()}
    assert len(by_book) == 5

    # A price stored as 1.000000 is shown as the shortest price there is. At the four
    # decimal places of the response that is the stored value.
    shown = by_book["Short price"]
    assert shown["combined_decimal_odds"] == 1.0
    assert shown["combined_price"] == {
        "american": -100000000,
        "decimal": 1.0,
        "fractional": "1/100",
        "implied_probability": pytest.approx(0.999999, abs=1e-6),
    }
    assert shown["legs"][0]["price"] == shown["combined_price"]
    assert shown["potential_payout"] == 10.0 and shown["potential_profit"] == 0.0

    # A stake stored as 0.00 is shown as 0 with nothing to win.
    nothing = by_book["Zero stake"]
    assert (nothing["stake"], nothing["potential_payout"], nothing["potential_profit"]) == (0, 0, 0)
    assert nothing["combined_price"]["american"] == -110

    # A closing price stored as 1.000000 is shown the same way; no CLV is computed from it.
    closed = by_book["Short close"]
    assert closed["legs"][0]["closing_price"]["american"] == -100000000
    assert closed["legs"][0]["clv"] is None and closed["clv"] is None

    for bet in listed.json():
        one_bet = client.get(f"/v1/bets/{bet['id']}", headers=headers)
        assert one_bet.status_code == 200 and one_bet.json() == bet

    summary = client.get("/v1/bets/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    totals = summary.json()["totals"]
    assert totals["pending_count"] == 3 and totals["settled_count"] == 2
    assert totals["pending_exposure"] == 20.0  # 10 + 0 + 10
    assert totals["staked"] == 50.0 and totals["profit"] == 0.0  # +30 and -30

    analytics = client.get("/v1/bets/analytics", headers=headers)
    assert analytics.status_code == 200, analytics.text
    bands = {row["key"]: row["bets"] for row in analytics.json()["by_odds_band"]}
    assert bands["-200_or_shorter"] == 1 and bands["+101_to_+200"] == 1
    assert analytics.json()["settled_count"] == 2

    export = client.get("/v1/me/export", headers=headers)
    assert export.status_code == 200, export.text
    assert {bet["id"]: bet for bet in export.json()["bets"]} == {
        bet["id"]: bet for bet in listed.json()
    }

    # Such a bet cannot be settled as it is (422, nothing changed) ...
    refused = client.post(f"/v1/bets/{zero['id']}/settle", json={"result": "won"}, headers=headers)
    assert refused.status_code == 422, refused.text
    assert client.get(f"/v1/bets/{zero['id']}", headers=headers).json()["status"] == "pending"
    # ... auto-settle leaves it alone ...
    auto = client.post("/v1/bets/auto-settle", headers=headers)
    assert auto.status_code == 200 and auto.json()["settled"] == []
    # ... and it can be corrected or deleted.
    fixed = client.patch(f"/v1/bets/{zero['id']}", json={"stake": 5}, headers=headers)
    assert fixed.status_code == 200 and fixed.json()["potential_payout"] == 9.55
    repriced = client.patch(
        f"/v1/bets/{short['id']}", json={"legs": [leg(odds=-120)]}, headers=headers
    )
    assert repriced.status_code == 200 and repriced.json()["combined_price"]["american"] == -120
    assert client.delete(f"/v1/bets/{closing['id']}", headers=headers).status_code == 204
    assert client.delete(f"/v1/bets/{settled['id']}", headers=headers).status_code == 204
    every_read_works(client, headers)


@pytest.mark.skipif(
    EXTERNAL_DATABASE_URL is not None, reason="PostgreSQL cannot store a price this long"
)
def test_a_price_longer_than_the_column_in_an_old_sqlite_row_still_loads(
    client: TestClient, headers: Headers, app: FastAPI
) -> None:
    bet = create(client, headers, parlay(2, 900))
    client.post(f"/v1/bets/{bet['id']}/settle", json={"result": "lost"}, headers=headers)
    _poison(app, bet["id"], odds_decimal=Decimal("1e30"), leg_odds_decimal=Decimal("1e30"))
    shown = client.get(f"/v1/bets/{bet['id']}", headers=headers)
    assert shown.status_code == 200, shown.text
    assert shown.json()["combined_decimal_odds"] == 10_000_000_000.0
    every_read_works(client, headers)


# ---------------------------------------------------------------- sync import
class OddProvider:
    """A provider that sends bets a column cannot hold next to good ones."""

    info = SyncProviderInfo(
        "odd", "Odd", "Sends odd values", is_mock=True, requires_credentials=False
    )

    def authorize(self, options: dict[str, Any], now: datetime) -> Authorization:
        return Authorization(label="Odd")

    def fetch_bets(self, state: dict[str, Any], now: datetime) -> FetchResult:
        def bet(key: str, stake: str, *odds: str, **extra: Any) -> ExternalBet:
            return ExternalBet(
                external_bet_id=key,
                bet_type="straight" if len(odds) == 1 else "parlay",
                sportsbook="Odd",
                stake=Decimal(stake),
                placed_at=datetime(2026, 3, 1, tzinfo=UTC),
                legs=tuple(
                    ExternalLeg(selection="Tides ML", market="moneyline", odds_decimal=Decimal(o))
                    for o in odds
                ),
                **extra,
            )

        bets = (
            bet("good-1", "10", "2.0"),
            bet("short-price", "10", "1.0000001"),
            bet("below-one", "10", "0.5"),
            bet("long-price", "10", "1e30"),
            bet("zero-stake", "0.004", "2.0"),
            bet("negative-stake", "-5", "2.0"),
            bet("long-parlay", "10", *["10"] * 12),
            # Only the check of each leg refuses this one: its combined price is fine.
            bet("parlay-with-a-short-leg", "10", "2.0", "1.0000001"),
            # Only the check of the combined price refuses this one: its payout would fit.
            bet("long-parlay-small-stake", "0.01", *["10"] * 12),
            bet("big-payout", "1000000", "1000001"),
            bet(
                "payout-too-big",
                "10",
                "2.0",
                result="won",
                payout=Decimal("1e13"),
                settled_at=datetime(2026, 3, 2, tzinfo=UTC),
            ),
            bet("id-" + "x" * 200, "10", "2.0"),
            bet("too-many-legs", "10", *["1.01"] * 21),
            bet("unknown-result", "10", "2.0", result="maybe", payout=Decimal("5")),
            bet("good-2", "10", "3.0", result="won", payout=Decimal("30")),
            # A time that leaves the calendar when it is converted to UTC.
            replace(
                bet("date-out-of-range", "10", "2.0"),
                placed_at=datetime(9999, 12, 31, 23, tzinfo=timezone(timedelta(hours=-12))),
            ),
        )
        return FetchResult(bets=bets, state=state)


def test_an_import_leaves_out_bets_that_cannot_be_stored(make_app: AppFactory) -> None:
    app = make_app()
    app.state.sync_registry = SyncRegistry([OddProvider()])
    with TestClient(app) as client:
        headers = auth_headers(client)
        connection = client.post(
            "/v1/sync/connections", json={"provider": "odd"}, headers=headers
        ).json()
        response = client.post(f"/v1/sync/connections/{connection['id']}/sync", headers=headers)
        assert response.status_code == 200, response.text
        run = response.json()
        assert (run["fetched_count"], run["imported_count"], run["duplicate_count"]) == (16, 2, 0)
        assert left_out(run) == 14
        assert run["status"] == "succeeded"
        assert "14 bets were not imported" in run["error_message"]
        bets = client.get("/v1/bets", headers=headers).json()
        assert sorted(bet["external_bet_id"] for bet in bets) == ["good-1", "good-2"]
        every_read_works(client, headers)
        # Running it again reports the same bets again and stores nothing new.
        again = client.post(f"/v1/sync/connections/{connection['id']}/sync", headers=headers).json()
        assert (again["imported_count"], again["duplicate_count"]) == (0, 2)
        assert left_out(again) == 14
        history = client.get(
            f"/v1/sync/connections/{connection['id']}/runs", headers=headers
        ).json()
        assert [left_out(r) for r in history] == [14, 14]
        with app.state.session_factory() as db:
            details = db.scalars(
                select(AuditLog.details).where(AuditLog.action == "sync.import")
            ).first()
        assert details is not None
        assert details["not_imported"] == 14 and details["rejected"] == 14
        assert details["over_limit"] == 0
