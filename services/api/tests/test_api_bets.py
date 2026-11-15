from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from oddvex_api.db import AuditLog, BetLeg

Headers = dict[str, str]


def leg(**overrides: Any) -> dict[str, Any]:
    return {
        "selection": "Harbor City Tides ML",
        "market": "moneyline",
        "league": "nba",
        "odds": -110,
        **overrides,
    }


def straight(**overrides: Any) -> dict[str, Any]:
    return {
        "bet_type": "straight",
        "stake": 110,
        "sportsbook": "Northline",
        "legs": [leg()],
        **overrides,
    }


def create(
    client: TestClient, headers: Headers, body: dict[str, Any] | None = None
) -> dict[str, Any]:
    response = client.post("/v1/bets", json=body or straight(), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def settle(
    client: TestClient, headers: Headers, bet_id: str, body: dict[str, Any], status: int = 200
) -> dict[str, Any]:
    response = client.post(f"/v1/bets/{bet_id}/settle", json=body, headers=headers)
    assert response.status_code == status, response.text
    return response.json()


# ------------------------------------------------------------------- creation
def test_create_straight_bet(client: TestClient, headers: Headers) -> None:
    bet = create(
        client,
        headers,
        straight(
            legs=[
                leg(
                    event_id="evt_nba_20260315_0",
                    event_label="Anvils at Tides",
                    line=None,
                    closing_odds=-120,
                )
            ],
            notes="first one",
            placed_at="2026-03-10T18:00:00-05:00",
        ),
    )
    assert bet["status"] == "pending" and bet["result"] is None
    assert bet["source"] == "manual"
    assert bet["sport"] == "nba"
    assert bet["stake"] == 110.0
    assert bet["combined_price"] == {
        "american": -110,
        "decimal": 1.9091,
        "fractional": "10/11",
        "implied_probability": pytest.approx(0.52381, abs=1e-5),
    }
    assert bet["combined_decimal_odds"] == 1.9091
    assert bet["potential_payout"] == 210.0
    assert bet["potential_profit"] == 100.0
    assert bet["payout"] is None and bet["profit"] is None
    assert bet["placed_at"] == "2026-03-10T23:00:00Z"
    assert bet["notes"] == "first one"
    only = bet["legs"][0]
    assert only["price"]["american"] == -110
    assert only["closing_price"]["american"] == -120
    assert only["event_label"] == "Anvils at Tides"
    assert only["clv"] == pytest.approx((210 / 110) / (220 / 120) - 1, abs=1e-5)
    assert bet["clv"] == only["clv"]
    assert client.get(f"/v1/bets/{bet['id']}", headers=headers).json() == bet


@pytest.mark.parametrize(
    ("odds", "odds_format", "decimal", "american"),
    [
        ("+150", "american", 2.5, 150),
        (150, "american", 2.5, 150),
        (2.5, "decimal", 2.5, 150),
        ("3/2", "fractional", 2.5, 150),
        ("6/4", "fractional", 2.5, 150),
    ],
)
def test_odds_are_normalised_to_decimal(
    client: TestClient, headers: Headers, app, odds, odds_format, decimal, american
) -> None:  # type: ignore[no-untyped-def]
    bet = create(
        client, headers, straight(stake=20, legs=[leg(odds=odds, odds_format=odds_format)])
    )
    assert bet["combined_decimal_odds"] == decimal
    assert bet["legs"][0]["price"]["american"] == american
    assert bet["legs"][0]["price"]["fractional"] == "3/2"
    assert bet["potential_payout"] == 50.0
    with app.state.session_factory() as db:
        stored = db.scalar(select(BetLeg.odds_decimal).where(BetLeg.bet_id == bet["id"]))
    assert float(stored) == 2.5


def test_parlay_price_is_the_product_of_its_legs(client: TestClient, headers: Headers) -> None:
    bet = create(
        client,
        headers,
        {
            "bet_type": "parlay",
            "stake": 10,
            "sportsbook": "Summit Wager",
            "legs": [
                leg(odds=2.0, odds_format="decimal"),
                leg(selection="Over 6.5", market="total", league="nhl", odds=150),
            ],
        },
    )
    assert bet["combined_decimal_odds"] == 5.0
    assert bet["combined_price"]["american"] == 400
    assert bet["potential_payout"] == 50.0
    assert bet["odds_source"] == "legs"
    assert bet["sport"] == "multi"
    assert [item["position"] for item in bet["legs"]] == [0, 1]


def test_sgp_can_carry_its_own_price(client: TestClient, headers: Headers) -> None:
    bet = create(
        client,
        headers,
        {
            "bet_type": "sgp",
            "stake": 10,
            "sportsbook": "Kestrel Bets",
            "odds": "+260",
            "legs": [leg(), leg(selection="Over 224.5", market="total")],
        },
    )
    assert bet["odds_source"] == "override"
    assert bet["combined_decimal_odds"] == 3.6
    assert bet["potential_payout"] == 36.0


@pytest.mark.parametrize(
    ("body", "code"),
    [
        (straight(stake=0), "validation_error"),
        (straight(stake=-5), "validation_error"),
        (straight(legs=[]), "validation_error"),
        (straight(legs=[leg(), leg()]), "validation_error"),
        (straight(bet_type="parlay"), "validation_error"),
        (straight(bet_type="teaser"), "validation_error"),
        (straight(sportsbook=""), "validation_error"),
        (straight(placed_at="2026-03-10T18:00:00"), "validation_error"),
        (straight(legs=[leg(odds=50)]), "invalid_american_odds"),
        (straight(legs=[leg(odds=1.0, odds_format="decimal")]), "invalid_decimal_odds"),
        (straight(legs=[leg(odds="x/y", odds_format="fractional")]), "invalid_fractional_odds"),
        (straight(legs=[leg(closing_odds=10)]), "invalid_american_odds"),
        (straight(legs=[leg(selection="")]), "validation_error"),
    ],
)
def test_create_validation(client: TestClient, headers: Headers, body: dict, code: str) -> None:
    response = client.post("/v1/bets", json=body, headers=headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code
    assert client.get("/v1/bets", headers=headers).json() == []


# ----------------------------------------------------------------- settlement
@pytest.mark.parametrize(
    ("result", "payout", "profit"),
    [
        ("won", 210.0, 100.0),
        ("lost", 0.0, -110.0),
        ("push", 110.0, 0.0),
        ("void", 110.0, 0.0),
        ("half_won", 160.0, 50.0),
        ("half_lost", 55.0, -55.0),
    ],
)
def test_settle_straight(
    client: TestClient, headers: Headers, result: str, payout: float, profit: float
) -> None:
    bet = create(client, headers)
    settled = settle(client, headers, bet["id"], {"result": result})
    assert (settled["status"], settled["result"]) == ("settled", result)
    assert (settled["payout"], settled["profit"]) == (payout, profit)
    assert settled["settled_at"] is not None
    assert settled["legs"][0]["result"] == result


def test_cashout(client: TestClient, headers: Headers) -> None:
    bet = create(client, headers)
    settled = settle(client, headers, bet["id"], {"result": "cashout", "cashout_amount": 150.25})
    assert (settled["result"], settled["payout"], settled["profit"]) == ("cashout", 150.25, 40.25)
    assert settled["legs"][0]["result"] is None
    other = create(client, headers)
    missing = settle(client, headers, other["id"], {"result": "cashout"}, status=422)
    assert missing["error"]["code"] == "validation_error"


def test_settle_validation(client: TestClient, headers: Headers) -> None:
    bet = create(client, headers)
    assert settle(client, headers, bet["id"], {}, status=422)["error"]["code"] == "validation_error"
    assert (
        settle(client, headers, bet["id"], {"result": "maybe"}, status=422)["error"]["code"]
        == "validation_error"
    )
    unknown = settle(
        client,
        headers,
        bet["id"],
        {"leg_results": [{"leg_id": "nope", "result": "won"}]},
        status=422,
    )
    assert unknown["error"]["code"] == "unknown_leg"
    assert client.get(f"/v1/bets/{bet['id']}", headers=headers).json()["status"] == "pending"


def parlay(client: TestClient, headers: Headers, **overrides: Any) -> dict[str, Any]:
    return create(
        client,
        headers,
        {
            "bet_type": "parlay",
            "stake": 10,
            "sportsbook": "Summit Wager",
            "legs": [
                leg(odds=2.0, odds_format="decimal"),
                leg(selection="Over 6.5", market="total", odds=3.0, odds_format="decimal"),
                leg(selection="Stags -3", market="spread", odds=1.5, odds_format="decimal"),
            ],
            **overrides,
        },
    )


def leg_results(bet: dict[str, Any], *results: str) -> list[dict[str, str]]:
    pairs = zip(bet["legs"], results, strict=True)
    return [{"leg_id": item["id"], "result": result} for item, result in pairs]


def test_parlay_settles_from_leg_results_with_a_push_dropped(
    client: TestClient, headers: Headers
) -> None:
    bet = parlay(client, headers)
    assert bet["potential_payout"] == 90.0
    settled = settle(
        client, headers, bet["id"], {"leg_results": leg_results(bet, "won", "push", "won")}
    )
    assert settled["result"] == "won"
    assert settled["payout"] == 30.0  # 10 x 2.0 x 1.5; the pushed 3.0 leg drops out
    assert settled["profit"] == 20.0
    assert [item["result"] for item in settled["legs"]] == ["won", "push", "won"]


def test_parlay_with_a_lost_leg_loses(client: TestClient, headers: Headers) -> None:
    bet = parlay(client, headers)
    partial = [{"leg_id": bet["legs"][1]["id"], "result": "lost"}]
    settled = settle(client, headers, bet["id"], {"leg_results": partial})
    assert (settled["result"], settled["payout"], settled["profit"]) == ("lost", 0.0, -10.0)
    assert [item["result"] for item in settled["legs"]] == [None, "lost", None]


def test_parlay_leg_results_must_be_complete_and_consistent(
    client: TestClient, headers: Headers
) -> None:
    bet = parlay(client, headers)
    partial = [{"leg_id": bet["legs"][0]["id"], "result": "won"}]
    pending = settle(client, headers, bet["id"], {"leg_results": partial}, status=422)
    assert pending["error"]["code"] == "parlay_legs_pending"
    mismatch = settle(
        client,
        headers,
        bet["id"],
        {"result": "lost", "leg_results": leg_results(bet, "won", "won", "won")},
        status=422,
    )
    assert mismatch["error"]["code"] == "result_mismatch"
    fresh = client.get(f"/v1/bets/{bet['id']}", headers=headers).json()
    assert fresh["status"] == "pending"
    assert [item["result"] for item in fresh["legs"]] == [None, None, None]


def test_parlay_bet_level_result(client: TestClient, headers: Headers) -> None:
    won = settle(client, headers, parlay(client, headers)["id"], {"result": "won"})
    assert (won["payout"], won["profit"]) == (90.0, 80.0)
    assert [item["result"] for item in won["legs"]] == ["won", "won", "won"]
    void = settle(client, headers, parlay(client, headers)["id"], {"result": "void"})
    assert (void["payout"], void["profit"]) == (10.0, 0.0)


def test_sgp_with_its_own_price_settles_at_that_price(client: TestClient, headers: Headers) -> None:
    body = {
        "bet_type": "sgp",
        "stake": 10,
        "sportsbook": "Kestrel Bets",
        "odds": "+260",
        "legs": [leg(), leg(selection="Over 224.5", market="total")],
    }
    bet = create(client, headers, body)
    settled = settle(client, headers, bet["id"], {"leg_results": leg_results(bet, "won", "won")})
    assert (settled["result"], settled["payout"]) == ("won", 36.0)
    other = create(client, headers, body)
    unclear = settle(
        client, headers, other["id"], {"leg_results": leg_results(other, "won", "push")}, status=422
    )
    assert unclear["error"]["code"] == "result_required"


def test_resettling_corrects_a_mistake_and_is_audited(
    client: TestClient, headers: Headers, app
) -> None:  # type: ignore[no-untyped-def]
    bet = create(client, headers)
    settle(client, headers, bet["id"], {"result": "won"})
    corrected = settle(
        client, headers, bet["id"], {"result": "lost", "settled_at": "2026-03-01T12:00:00Z"}
    )
    assert (corrected["result"], corrected["profit"]) == ("lost", -110.0)
    assert corrected["settled_at"] == "2026-03-01T12:00:00Z"
    with app.state.session_factory() as db:
        rows = list(
            db.scalars(
                select(AuditLog)
                .where(AuditLog.action == "bet.settle")
                .order_by(AuditLog.created_at)
            )
        )
    assert [row.details for row in rows] == [
        {"result": "won", "previous_result": None},
        {"result": "lost", "previous_result": "won"},
    ]
    assert all(row.entity_id == bet["id"] for row in rows)


# ------------------------------------------------------------ update / delete
def test_patch_pending_bet(client: TestClient, headers: Headers) -> None:
    bet = create(client, headers)
    response = client.patch(
        f"/v1/bets/{bet['id']}",
        json={
            "stake": 55,
            "notes": "halved",
            "sportsbook": "Cardinal Sports",
            "legs": [leg(odds="+120", league="nfl")],
        },
        headers=headers,
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["stake"] == 55.0
    assert updated["notes"] == "halved"
    assert updated["sportsbook"] == "Cardinal Sports"
    assert updated["combined_decimal_odds"] == 2.2
    assert updated["potential_payout"] == 121.0
    assert updated["sport"] == "nfl"
    assert len(updated["legs"]) == 1 and updated["legs"][0]["id"] != bet["legs"][0]["id"]
    cleared = client.patch(f"/v1/bets/{bet['id']}", json={"notes": None}, headers=headers).json()
    assert cleared["notes"] is None and cleared["stake"] == 55.0


def test_patch_rules(client: TestClient, headers: Headers) -> None:
    bet = create(client, headers)
    bad_legs = client.patch(f"/v1/bets/{bet['id']}", json={"legs": [leg(), leg()]}, headers=headers)
    assert bad_legs.status_code == 422
    bad_odds = client.patch(f"/v1/bets/{bet['id']}", json={"legs": [leg(odds=5)]}, headers=headers)
    assert bad_odds.status_code == 422
    assert client.get(f"/v1/bets/{bet['id']}", headers=headers).json()["legs"] == bet["legs"]
    settle(client, headers, bet["id"], {"result": "won"})
    locked = client.patch(f"/v1/bets/{bet['id']}", json={"stake": 1}, headers=headers)
    assert locked.status_code == 409
    assert locked.json()["error"]["code"] == "bet_already_settled"
    notes = client.patch(f"/v1/bets/{bet['id']}", json={"notes": "after the fact"}, headers=headers)
    assert notes.status_code == 200 and notes.json()["notes"] == "after the fact"
    assert notes.json()["profit"] == 100.0


def test_closing_odds_can_be_recorded_after_settlement(
    client: TestClient, headers: Headers
) -> None:
    bet = create(client, headers, straight(legs=[leg(odds=150)]))
    assert bet["clv"] is None
    settle(client, headers, bet["id"], {"result": "lost"})
    body = {
        "closing_odds": [
            {"leg_id": bet["legs"][0]["id"], "closing_odds": 130, "closing_opposite_odds": -150}
        ]
    }
    updated = client.patch(f"/v1/bets/{bet['id']}", json=body, headers=headers).json()
    assert updated["legs"][0]["closing_price"]["american"] == 130
    assert updated["clv"] == pytest.approx(2.5 / 2.3 - 1, abs=1e-5)
    unknown = client.patch(
        f"/v1/bets/{bet['id']}",
        json={"closing_odds": [{"leg_id": "x", "closing_odds": 130}]},
        headers=headers,
    )
    assert unknown.status_code == 422 and unknown.json()["error"]["code"] == "unknown_leg"


def test_delete_bet(client: TestClient, headers: Headers, app) -> None:  # type: ignore[no-untyped-def]
    bet = create(client, headers)
    response = client.delete(f"/v1/bets/{bet['id']}", headers=headers)
    assert response.status_code == 204
    assert client.get(f"/v1/bets/{bet['id']}", headers=headers).status_code == 404
    assert client.delete(f"/v1/bets/{bet['id']}", headers=headers).status_code == 404
    with app.state.session_factory() as db:
        assert list(db.scalars(select(BetLeg))) == []
        assert (
            db.scalar(select(AuditLog).where(AuditLog.action == "bet.delete")).entity_id
            == bet["id"]
        )


# -------------------------------------------------------------------- listing
def test_list_filters_and_order(client: TestClient, headers: Headers) -> None:
    old = create(client, headers, straight(placed_at="2026-01-01T00:00:00Z"))
    new = create(
        client, headers, straight(placed_at="2026-02-01T00:00:00Z", legs=[leg(league="nhl")])
    )
    mid = create(client, headers, straight(placed_at="2026-01-15T00:00:00Z"))
    settle(client, headers, old["id"], {"result": "won"})
    settle(client, headers, mid["id"], {"result": "lost"})

    def ids(**params: Any) -> list[str]:
        response = client.get("/v1/bets", params=params, headers=headers)
        assert response.status_code == 200
        return [b["id"] for b in response.json()]

    assert ids() == [new["id"], mid["id"], old["id"]]
    assert ids(status="pending") == [new["id"]]
    assert ids(status="settled") == [mid["id"], old["id"]]
    assert ids(status="won") == [old["id"]]
    assert ids(status="lost") == [mid["id"]]
    assert ids(sport="nhl") == [new["id"]]
    assert ids(sport="NBA", status="settled") == [mid["id"], old["id"]]
    assert ids(sport="soccer") == []
    assert ids(limit=1, offset=1) == [mid["id"]]
    assert client.get("/v1/bets", params={"status": "open"}, headers=headers).status_code == 422


# -------------------------------------------------------------------- summary
def test_summary_of_an_empty_tracker(client: TestClient, headers: Headers) -> None:
    summary = client.get("/v1/bets/summary", headers=headers).json()
    assert summary["totals"] == {
        "staked": 0.0, "profit": 0.0, "roi": None, "wins": 0, "losses": 0, "pushes": 0,
        "pending_count": 0, "pending_exposure": 0.0, "avg_clv": None, "clv_sample": 0,
        "settled_count": 0,
    }  # fmt: skip
    assert summary["by_sport"] == summary["by_market"] == summary["timeline"] == []


def test_summary_totals_breakdowns_and_timeline(client: TestClient, headers: Headers) -> None:
    def add(result: str | None, when: str, **overrides: Any) -> dict[str, Any]:
        bet = create(client, headers, straight(**{"stake": 100, **overrides}))
        if result:
            settle(client, headers, bet["id"], {"result": result, "settled_at": when})
        return bet

    add("won", "2026-03-01T20:00:00Z", legs=[leg(odds=150, closing_odds=130)])  # +150
    add(
        "lost",
        "2026-03-01T22:00:00Z",
        legs=[leg(odds=-110, league="nfl", market="spread", closing_odds=-110)],
    )  # -100
    add("push", "2026-03-03T20:00:00Z", sportsbook="Summit Wager")  # 0
    add("void", "2026-03-03T21:00:00Z", sportsbook="Summit Wager")  # 0, not counted in staked
    add("half_lost", "2026-03-05T20:00:00Z", legs=[leg(league="nfl", market="spread")])  # -50
    add(None, "", stake=40)
    add(None, "", stake=60)
    multi = create(
        client,
        headers,
        {
            "bet_type": "parlay",
            "stake": 10,
            "sportsbook": "Northline",
            "legs": [
                leg(odds=2.0, odds_format="decimal"),
                leg(odds=2.0, odds_format="decimal", league="nhl"),
            ],
        },
    )
    settle(
        client, headers, multi["id"], {"result": "won", "settled_at": "2026-03-05T23:00:00Z"}
    )  # +30

    summary = client.get("/v1/bets/summary", headers=headers).json()
    totals = summary["totals"]
    assert totals["settled_count"] == 6
    assert totals["staked"] == 410.0  # 5 x 100 + 10 - the void 100
    assert totals["profit"] == 30.0
    assert totals["roi"] == pytest.approx(30 / 410, abs=1e-6)
    assert (totals["wins"], totals["losses"], totals["pushes"]) == (2, 2, 2)
    assert (totals["pending_count"], totals["pending_exposure"]) == (2, 100.0)
    assert totals["clv_sample"] == 2
    assert totals["avg_clv"] == pytest.approx(((2.5 / 2.3 - 1) + 0.0) / 2, abs=1e-5)

    def rows(name: str) -> dict[str, dict[str, Any]]:
        assert all(set(r) == {"key", "bets", "staked", "profit", "roi"} for r in summary[name])
        return {r["key"]: r for r in summary[name]}

    sport = rows("by_sport")
    assert (
        sport["nba"]["bets"] == 3
        and sport["nba"]["profit"] == 150.0
        and sport["nba"]["staked"] == 200.0
    )
    assert sport["nfl"] == {
        "key": "nfl",
        "bets": 2,
        "staked": 200.0,
        "profit": -150.0,
        "roi": -0.75,
    }
    assert sport["multi"]["profit"] == 30.0
    market = rows("by_market")
    assert market["moneyline"]["bets"] == 3
    assert market["spread"]["profit"] == -150.0
    assert market["multiple"]["bets"] == 1
    book = rows("by_sportsbook")
    assert book["Summit Wager"] == {
        "key": "Summit Wager",
        "bets": 2,
        "staked": 100.0,
        "profit": 0.0,
        "roi": 0.0,
    }
    kind = rows("by_bet_type")
    assert kind["straight"]["bets"] == 5 and kind["parlay"]["profit"] == 30.0
    for name in ("by_sport", "by_market", "by_sportsbook", "by_bet_type"):
        assert sum(r["profit"] for r in summary[name]) == pytest.approx(totals["profit"])
        assert sum(r["bets"] for r in summary[name]) == totals["settled_count"]

    assert summary["timeline"] == [
        {"date": "2026-03-01", "cumulative_profit": 50.0},
        {"date": "2026-03-03", "cumulative_profit": 50.0},
        {"date": "2026-03-05", "cumulative_profit": 30.0},
    ]
    assert "do not predict" in summary["note"]


# ---------------------------------------------------------------------- authz
def test_every_bet_route_requires_authentication(client: TestClient) -> None:
    calls = [
        ("GET", "/v1/bets", None),
        ("POST", "/v1/bets", straight()),
        ("GET", "/v1/bets/summary", None),
        ("GET", "/v1/bets/abc", None),
        ("PATCH", "/v1/bets/abc", {"notes": "x"}),
        ("DELETE", "/v1/bets/abc", None),
        ("POST", "/v1/bets/abc/settle", {"result": "won"}),
    ]
    for method, path, body in calls:
        response = client.request(method, path, json=body)
        assert response.status_code == 401, (method, path)
        assert response.json()["error"]["code"] == "not_authenticated"


def test_users_cannot_read_or_modify_each_others_bets(
    client: TestClient, headers: Headers, other_headers: Headers
) -> None:
    mine = create(client, headers, straight(notes="private"))
    theirs = create(client, other_headers, straight(stake=5))
    path = f"/v1/bets/{mine['id']}"

    assert client.get(path, headers=other_headers).status_code == 404
    assert (
        client.patch(path, json={"notes": "hacked", "stake": 1}, headers=other_headers).status_code
        == 404
    )
    assert (
        client.post(f"{path}/settle", json={"result": "lost"}, headers=other_headers).status_code
        == 404
    )
    assert client.delete(path, headers=other_headers).status_code == 404
    # Another user's leg id cannot be used to touch a bet either.
    cross = client.post(
        f"/v1/bets/{theirs['id']}/settle",
        json={"leg_results": [{"leg_id": mine["legs"][0]["id"], "result": "lost"}]},
        headers=other_headers,
    )
    assert cross.status_code == 422

    assert [b["id"] for b in client.get("/v1/bets", headers=other_headers).json()] == [theirs["id"]]
    assert [b["id"] for b in client.get("/v1/bets", headers=headers).json()] == [mine["id"]]
    other_summary = client.get("/v1/bets/summary", headers=other_headers).json()["totals"]
    assert other_summary["pending_exposure"] == 5.0 and other_summary["pending_count"] == 1

    untouched = client.get(path, headers=headers).json()
    assert untouched == mine
    assert untouched["notes"] == "private" and untouched["status"] == "pending"
