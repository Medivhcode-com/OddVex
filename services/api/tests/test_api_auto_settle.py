"""Structured bet legs, auto-settlement from final scores, and the bet list filters."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from oddvex_api.db import AuditLog, Bet
from oddvex_api.providers import SyntheticProvider
from oddvex_api.seed import DEMO_EMAIL, DEMO_GRADEABLE_COUNT

from .conftest import FROZEN_NOW, AppFactory, auth_headers
from .test_platform import assert_envelope

Headers = dict[str, str]


def events(client: TestClient, status: str, league: str | None = None) -> list[dict[str, Any]]:
    params = {"status": status, **({"league": league} if league else {})}
    return client.get("/v1/events", params=params).json()


def final_event(client: TestClient, league: str = "nba", index: int = 0) -> dict[str, Any]:
    event = events(client, "final", league)[index]
    assert event["score"] is not None
    return event


def sleg(event: dict[str, Any], market: str, outcome: str, **extra: Any) -> dict[str, Any]:
    return {
        "selection": f"{market} {outcome}",
        "market": market,
        "event_id": event["id"],
        "outcome_key": outcome,
        "odds": 100,
        **extra,
    }


def bet(legs: list[dict[str, Any]], **overrides: Any) -> dict[str, Any]:
    return {
        "bet_type": "straight" if len(legs) == 1 else "parlay",
        "stake": 10,
        "sportsbook": "Northline",
        "legs": legs,
        **overrides,
    }


def create(client: TestClient, headers: Headers, body: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/v1/bets", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def auto_settle(client: TestClient, headers: Headers) -> dict[str, Any]:
    response = client.post("/v1/bets/auto-settle", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"checked", "settled", "skipped"}
    return body


def winner(event: dict[str, Any]) -> tuple[str, str]:
    """(winning side, losing side) of a final event that was not a tie."""
    score = event["score"]
    assert score["home"] != score["away"]
    return ("home", "away") if score["home"] > score["away"] else ("away", "home")


# ------------------------------------------------------------ structured legs
def test_structured_leg_is_stored_and_reported_gradeable(
    client: TestClient, headers: Headers
) -> None:
    event = final_event(client)
    created = create(
        client,
        headers,
        bet([sleg(event, "Spread", "home", line=-3.5)]),
    )
    leg = created["legs"][0]
    assert leg["outcome_key"] == "home" and leg["line"] == -3.5 and leg["gradeable"] is True
    assert leg["event_id"] == event["id"] and leg["market"] == "spread"
    # League and label are filled in from the event when the client leaves them out.
    assert leg["league"] == "nba" and created["sport"] == "nba"
    assert leg["event_label"] == f"{event['away_team']['name']} at {event['home_team']['name']}"
    assert created["status"] == "pending" and created["settled_by"] is None
    assert client.get(f"/v1/bets/{created['id']}", headers=headers).json() == created


def test_legs_without_outcome_key_keep_working_and_are_not_gradeable(
    client: TestClient, headers: Headers
) -> None:
    free_text = create(
        client,
        headers,
        bet(
            [
                {
                    "selection": "Somebody ML",
                    "market": "moneyline",
                    "event_id": "an-id-the-provider-has-never-seen",
                    "odds": -110,
                }
            ]
        ),
    )
    leg = free_text["legs"][0]
    assert leg["outcome_key"] is None and leg["gradeable"] is False
    assert leg["event_id"] == "an-id-the-provider-has-never-seen"
    prop = create(
        client,
        headers,
        bet([{"selection": "Over 22.5", "market": "player_points", "line": 22.5, "odds": -110}]),
    )
    assert prop["legs"][0]["gradeable"] is False


@pytest.mark.parametrize(
    ("league", "leg_update", "code"),
    [
        ("nba", {"event_id": "evt_nba_19990101_0"}, "unknown_event"),
        ("nba", {"event_id": "nope"}, "unknown_event"),
        ("nba", {"event_id": None}, "invalid_selection"),
        (
            "nba",
            {"market": "player_points", "outcome_key": "over", "line": 2.5},
            "invalid_selection",
        ),
        ("nba", {"outcome_key": "draw"}, "invalid_selection"),  # 2-way moneyline
        ("nba", {"outcome_key": "over"}, "invalid_selection"),
        ("nba", {"market": "spread", "outcome_key": "home"}, "invalid_selection"),  # no line
        ("nba", {"market": "spread", "outcome_key": "over", "line": 1.5}, "invalid_selection"),
        ("nba", {"market": "total", "outcome_key": "over"}, "invalid_selection"),  # no line
        ("nba", {"market": "total", "outcome_key": "home", "line": 220.5}, "invalid_selection"),
        ("soccer", {"market": "spread", "line": -0.5}, "market_not_available"),
    ],
)
def test_invalid_structured_legs_are_rejected(
    client: TestClient, headers: Headers, league: str, leg_update: dict[str, Any], code: str
) -> None:
    event = final_event(client, league)
    leg = {**sleg(event, "moneyline", "home"), **leg_update}
    response = client.post("/v1/bets", json=bet([leg]), headers=headers)
    assert response.status_code == 422, response.text
    assert_envelope(response.json(), code)
    assert response.json()["error"]["details"]["leg"] == 0
    assert client.get("/v1/bets", headers=headers).json() == []


def test_outcome_key_must_be_a_known_value(client: TestClient, headers: Headers) -> None:
    event = final_event(client)
    response = client.post("/v1/bets", json=bet([sleg(event, "moneyline", "tie")]), headers=headers)
    assert response.status_code == 422
    assert_envelope(response.json(), "validation_error")


def test_draw_is_valid_on_a_three_way_moneyline(client: TestClient, headers: Headers) -> None:
    event = final_event(client, "soccer")
    created = create(client, headers, bet([sleg(event, "moneyline", "draw")]))
    assert created["legs"][0]["outcome_key"] == "draw" and created["legs"][0]["gradeable"] is True


def test_patching_legs_validates_structured_selections(
    client: TestClient, headers: Headers
) -> None:
    event = final_event(client)
    created = create(client, headers, bet([sleg(event, "moneyline", "home")]))
    bad = client.patch(
        f"/v1/bets/{created['id']}",
        json={"legs": [sleg(event, "moneyline", "draw")]},
        headers=headers,
    )
    assert bad.status_code == 422
    assert_envelope(bad.json(), "invalid_selection")
    good = client.patch(
        f"/v1/bets/{created['id']}",
        json={"legs": [sleg(event, "total", "over", line=200.5)]},
        headers=headers,
    )
    assert good.status_code == 200, good.text
    assert good.json()["legs"][0]["outcome_key"] == "over" and good.json()["legs"][0]["gradeable"]
    # Replacing the legs with free text makes the bet ungradeable again.
    plain = client.patch(
        f"/v1/bets/{created['id']}",
        json={"legs": [{"selection": "x", "market": "moneyline", "odds": 100}]},
        headers=headers,
    )
    assert plain.json()["legs"][0]["gradeable"] is False


def test_final_events_report_a_final_score(client: TestClient) -> None:
    finals = events(client, "final")
    assert finals
    for event in finals[:8]:
        detail = client.get(f"/v1/events/{event['id']}").json()
        assert detail["status"] == "final" and detail["status_detail"] == "Final"
        assert detail["score"] == event["score"]
        assert detail["score"]["home"] >= 0 and detail["score"]["away"] >= 0


# ---------------------------------------------------------------- auto-settle
def test_auto_settle_straight_bets_from_the_final_score(
    client: TestClient, headers: Headers, app
) -> None:  # type: ignore[no-untyped-def]
    event = final_event(client)
    win, lose = winner(event)
    total = event["score"]["home"] + event["score"]["away"]
    margin = event["score"]["home"] - event["score"]["away"]
    cases = {
        "ml_won": (sleg(event, "moneyline", win, odds=150), "won", 25.0, 15.0),
        "ml_lost": (sleg(event, "moneyline", lose, odds=150), "lost", 0.0, -10.0),
        "total_over_won": (sleg(event, "total", "over", line=total - 0.5), "won", 20.0, 10.0),
        "total_under_lost": (sleg(event, "total", "under", line=total - 0.5), "lost", 0.0, -10.0),
        "total_push": (sleg(event, "total", "over", line=total), "push", 10.0, 0.0),
        "spread_push": (sleg(event, "spread", "home", line=-margin), "push", 10.0, 0.0),
        "spread_won": (sleg(event, "spread", "home", line=-margin + 0.5), "won", 20.0, 10.0),
        "spread_away_lost": (sleg(event, "spread", "away", line=margin - 0.5), "lost", 0.0, -10.0),
    }
    ids = {name: create(client, headers, bet([leg]))["id"] for name, (leg, *_) in cases.items()}

    body = auto_settle(client, headers)
    assert body["checked"] == len(cases) and body["skipped"] == []
    settled = {b["id"]: b for b in body["settled"]}
    assert set(settled) == set(ids.values())
    for name, (_, result, payout, profit) in cases.items():
        out = settled[ids[name]]
        assert out["status"] == "settled" and out["settled_by"] == "auto", name
        assert out["result"] == result, name
        assert out["payout"] == payout and out["profit"] == profit, name
        assert out["legs"][0]["result"] == result, name
        assert out["settled_at"] is not None
        assert client.get(f"/v1/bets/{out['id']}", headers=headers).json() == out

    # Idempotent: nothing is pending any more.
    assert auto_settle(client, headers) == {"checked": 0, "settled": [], "skipped": []}

    with app.state.session_factory() as db:
        audit = [row for row in db.scalars(select(AuditLog)) if row.action == "bet.auto_settle"]
    assert {row.entity_id for row in audit} == set(ids.values()) and len(audit) == len(cases)
    by_bet = {row.entity_id: row.details for row in audit}
    assert by_bet[ids["ml_won"]] == {"result": "won", "legs": ["won"]}
    summary = client.get("/v1/bets/summary", headers=headers).json()["totals"]
    assert summary["settled_count"] == len(cases) and summary["pending_count"] == 0


def test_auto_settle_matches_a_manual_settle_of_the_same_bet(
    client: TestClient, headers: Headers
) -> None:
    event = final_event(client, "nfl")
    win, _ = winner(event)
    body = bet([sleg(event, "moneyline", win, odds=-135)], stake=27)
    manual = create(client, headers, body)
    by_hand = client.post(
        f"/v1/bets/{manual['id']}/settle", json={"result": "won"}, headers=headers
    ).json()
    assert by_hand["settled_by"] == "user"
    auto = create(client, headers, body)
    settled = auto_settle(client, headers)["settled"]
    assert [b["id"] for b in settled] == [auto["id"]]  # the manual one is not touched
    for field in ("result", "payout", "profit", "potential_payout", "combined_decimal_odds"):
        assert settled[0][field] == by_hand[field], field
    assert settled[0]["settled_by"] == "auto"
    assert client.get(f"/v1/bets/{manual['id']}", headers=headers).json()["settled_by"] == "user"


def test_auto_settle_three_way_moneyline(client: TestClient, headers: Headers) -> None:
    event = final_event(client, "soccer")
    score = event["score"]
    tied = score["home"] == score["away"]
    ids = {
        key: create(client, headers, bet([sleg(event, "moneyline", key)]))["id"]
        for key in ("home", "draw", "away")
    }
    settled = {b["id"]: b["result"] for b in auto_settle(client, headers)["settled"]}
    expected_winner = "draw" if tied else ("home" if score["home"] > score["away"] else "away")
    for key, bet_id in ids.items():
        assert settled[bet_id] == ("won" if key == expected_winner else "lost"), key


def test_auto_settle_parlays(client: TestClient, headers: Headers) -> None:
    first, second = final_event(client, "nba", 0), final_event(client, "nba", 1)
    win1, lose1 = winner(first)
    win2, _ = winner(second)
    total2 = second["score"]["home"] + second["score"]["away"]

    all_won = create(
        client,
        headers,
        bet([sleg(first, "moneyline", win1, odds=100), sleg(second, "moneyline", win2, odds=100)]),
    )
    one_lost = create(
        client,
        headers,
        bet([sleg(first, "moneyline", lose1), sleg(second, "moneyline", win2)]),
    )
    push_drops_out = create(
        client,
        headers,
        bet(
            [
                sleg(first, "moneyline", win1, odds=150),
                sleg(second, "total", "over", line=total2, odds=-110),
            ]
        ),
    )
    all_pushed = create(
        client,
        headers,
        bet(
            [
                sleg(second, "total", "over", line=total2),
                sleg(second, "total", "under", line=total2),
            ],
            bet_type="sgp",
        ),
    )
    settled = {b["id"]: b for b in auto_settle(client, headers)["settled"]}
    assert len(settled) == 4

    won = settled[all_won["id"]]
    assert won["result"] == "won" and won["payout"] == 40.0 and won["profit"] == 30.0
    assert [leg["result"] for leg in won["legs"]] == ["won", "won"]

    lost = settled[one_lost["id"]]
    assert lost["result"] == "lost" and lost["payout"] == 0.0 and lost["profit"] == -10.0
    assert [leg["result"] for leg in lost["legs"]] == ["lost", "won"]

    reduced = settled[push_drops_out["id"]]
    assert [leg["result"] for leg in reduced["legs"]] == ["won", "push"]
    assert reduced["result"] == "won" and reduced["payout"] == 25.0  # only the +150 leg counts

    pushed = settled[all_pushed["id"]]
    assert pushed["result"] == "push" and pushed["payout"] == 10.0 and pushed["profit"] == 0.0
    assert all(b["settled_by"] == "auto" for b in settled.values())


def test_auto_settle_parlay_with_its_own_price(client: TestClient, headers: Headers) -> None:
    first, second = final_event(client, "nba", 0), final_event(client, "nba", 1)
    win1, lose1 = winner(first)
    win2, _ = winner(second)
    total2 = second["score"]["home"] + second["score"]["away"]

    def sgp(legs: list[dict[str, Any]]) -> dict[str, Any]:
        return create(client, headers, bet(legs, bet_type="sgp", odds=300))

    won = sgp([sleg(first, "moneyline", win1), sleg(second, "moneyline", win2)])
    lost = sgp([sleg(first, "moneyline", lose1), sleg(second, "total", "over", line=total2)])
    all_push = sgp(
        [sleg(second, "total", "over", line=total2), sleg(second, "total", "under", line=total2)]
    )
    mixed = sgp([sleg(first, "moneyline", win1), sleg(second, "total", "over", line=total2)])

    body = auto_settle(client, headers)
    settled = {b["id"]: b for b in body["settled"]}
    assert settled[won["id"]]["result"] == "won" and settled[won["id"]]["payout"] == 40.0
    assert settled[lost["id"]]["result"] == "lost" and settled[lost["id"]]["payout"] == 0.0
    assert settled[all_push["id"]]["result"] == "push" and settled[all_push["id"]]["payout"] == 10.0
    # A win plus a push needs the book's reduced price: left for the user.
    assert body["skipped"] == [{"bet_id": mixed["id"], "reason": "manual_result_required"}]
    still = client.get(f"/v1/bets/{mixed['id']}", headers=headers).json()
    assert still["status"] == "pending" and still["settled_by"] is None
    assert all(leg["result"] is None for leg in still["legs"])


def test_auto_settle_skips_with_a_reason(client: TestClient, headers: Headers) -> None:
    final = final_event(client)
    win, _ = winner(final)
    upcoming = events(client, "upcoming", "nba")[0]
    live = events(client, "live")[0]

    free_text = create(
        client, headers, bet([{"selection": "Tides ML", "market": "moneyline", "odds": -110}])
    )
    not_started = create(client, headers, bet([sleg(upcoming, "moneyline", "home")]))
    in_play = create(client, headers, bet([sleg(live, "moneyline", "home")]))
    half_structured = create(
        client,
        headers,
        bet(
            [
                sleg(final, "moneyline", win),
                {"selection": "Player over 22.5", "market": "player_points", "odds": -110},
            ]
        ),
    )
    waiting_on_one_leg = create(
        client, headers, bet([sleg(final, "moneyline", win), sleg(upcoming, "moneyline", "home")])
    )
    ready = create(client, headers, bet([sleg(final, "moneyline", win)]))

    body = auto_settle(client, headers)
    assert body["checked"] == 6
    assert [b["id"] for b in body["settled"]] == [ready["id"]]
    assert {s["bet_id"]: s["reason"] for s in body["skipped"]} == {
        free_text["id"]: "not_gradeable",
        not_started["id"]: "event_not_final",
        in_play["id"]: "event_not_final",
        half_structured["id"]: "not_gradeable",
        waiting_on_one_leg["id"]: "event_not_final",
    }
    for skipped in body["skipped"]:
        untouched = client.get(f"/v1/bets/{skipped['bet_id']}", headers=headers).json()
        assert untouched["status"] == "pending" and untouched["result"] is None
        assert all(leg["result"] is None for leg in untouched["legs"])

    again = auto_settle(client, headers)
    assert again["checked"] == 5 and again["settled"] == [] and len(again["skipped"]) == 5


def test_auto_settle_when_the_provider_no_longer_has_the_event(make_app: AppFactory) -> None:
    clock = {"now": FROZEN_NOW}
    provider = SyntheticProvider(seed=20260101, clock=lambda: clock["now"])
    with TestClient(make_app(provider=provider)) as client:
        headers = auth_headers(client)
        upcoming = events(client, "upcoming", "nba")[0]
        created = create(client, headers, bet([sleg(upcoming, "moneyline", "home")]))
        assert auto_settle(client, headers)["skipped"] == [
            {"bet_id": created["id"], "reason": "event_not_final"}
        ]
        # A few hours later the game is over and the same call settles it.
        clock["now"] = FROZEN_NOW + timedelta(days=2)
        other = create(client, headers, bet([sleg(upcoming, "moneyline", "away")]))
        clock["now"] = FROZEN_NOW + timedelta(days=500)
        body = auto_settle(client, headers)
        assert body["settled"] == []
        assert {s["bet_id"]: s["reason"] for s in body["skipped"]} == {
            created["id"]: "event_unavailable",
            other["id"]: "event_unavailable",
        }
        clock["now"] = FROZEN_NOW + timedelta(days=2)
        settled = auto_settle(client, headers)["settled"]
        assert {b["id"] for b in settled} == {created["id"], other["id"]}
        assert sorted(b["result"] for b in settled) in (["lost", "won"], ["push", "push"])


def test_auto_settle_never_touches_another_users_bets(
    client: TestClient, headers: Headers, other_headers: Headers, app
) -> None:  # type: ignore[no-untyped-def]
    event = final_event(client)
    win, _ = winner(event)
    mine = create(client, headers, bet([sleg(event, "moneyline", win)]))
    theirs = create(client, other_headers, bet([sleg(event, "moneyline", win)]))

    body = auto_settle(client, headers)
    assert body["checked"] == 1 and [b["id"] for b in body["settled"]] == [mine["id"]]
    assert theirs["id"] not in str(body)
    other = client.get(f"/v1/bets/{theirs['id']}", headers=other_headers).json()
    assert other["status"] == "pending" and other["settled_by"] is None
    with app.state.session_factory() as db:
        rows = {b.id: (b.status, b.settled_by) for b in db.scalars(select(Bet))}
    assert rows == {mine["id"]: ("settled", "auto"), theirs["id"]: ("pending", None)}
    assert [b["id"] for b in auto_settle(client, other_headers)["settled"]] == [theirs["id"]]


def test_auto_settle_requires_authentication(client: TestClient) -> None:
    response = client.post("/v1/bets/auto-settle")
    assert response.status_code == 401
    assert_envelope(response.json(), "not_authenticated")
    assert client.get("/v1/bets/auto-settle").status_code == 401


def test_manual_settle_is_marked_user_and_a_correction_overrides_auto(
    client: TestClient, headers: Headers
) -> None:
    event = final_event(client)
    win, _ = winner(event)
    created = create(client, headers, bet([sleg(event, "moneyline", win)]))
    assert auto_settle(client, headers)["settled"][0]["settled_by"] == "auto"
    corrected = client.post(
        f"/v1/bets/{created['id']}/settle", json={"result": "void"}, headers=headers
    ).json()
    assert corrected["result"] == "void" and corrected["settled_by"] == "user"


def test_seeded_demo_bets_can_be_auto_settled(make_app: AppFactory) -> None:
    app = make_app(auto_seed_demo=True, demo_password="demo-password-123")
    with TestClient(app) as client:
        login = client.post(
            "/v1/auth/login", json={"email": DEMO_EMAIL, "password": "demo-password-123"}
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        pending = client.get("/v1/bets", params={"status": "pending"}, headers=headers).json()
        gradeable = [b for b in pending if all(leg["gradeable"] for leg in b["legs"])]
        assert len(gradeable) == DEMO_GRADEABLE_COUNT == 4
        assert {b["bet_type"] for b in gradeable} == {"straight", "parlay"}
        assert all(b["placed_at"] < FROZEN_NOW.isoformat() for b in gradeable)

        body = auto_settle(client, headers)
        assert body["checked"] == len(pending)
        assert {b["id"] for b in body["settled"]} == {b["id"] for b in gradeable}
        assert all(b["settled_by"] == "auto" and b["result"] for b in body["settled"])
        assert all(s["reason"] == "not_gradeable" for s in body["skipped"])
        assert len(body["skipped"]) == len(pending) - 4
        assert auto_settle(client, headers)["settled"] == []
    # Starting the app again does not re-create or re-open them.
    with TestClient(app) as client:
        login = client.post(
            "/v1/auth/login", json={"email": DEMO_EMAIL, "password": "demo-password-123"}
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert len(client.get("/v1/bets", headers=headers).json()) == 44
        assert auto_settle(client, headers)["settled"] == []


# --------------------------------------------------------------- list filters
@pytest.fixture
def varied(client: TestClient, headers: Headers) -> dict[str, dict[str, Any]]:
    def make(name: str, placed: str, **overrides: Any) -> dict[str, Any]:
        market = overrides.pop("market", "moneyline")
        body = bet(
            [{"selection": name, "market": market, "league": "nba", "odds": 100}],
            placed_at=placed,
            **overrides,
        )
        return create(client, headers, body)

    bets = {
        "a": make("a", "2026-03-01T12:00:00Z", stake=50, sportsbook="Northline"),
        "b": make("b", "2026-03-02T12:00:00Z", stake=10, sportsbook="Cardinal Sports"),
        "c": make("c", "2026-03-03T12:00:00Z", stake=30, sportsbook="northline", market="Total"),
        "d": make("d", "2026-03-04T12:00:00Z", stake=20, sportsbook="Summit Wager"),
    }
    parlay = create(
        client,
        headers,
        bet(
            [
                {"selection": "p1", "market": "spread", "odds": 100},
                {"selection": "p2", "market": "total", "odds": 100},
            ],
            stake=5,
            sportsbook="Northline",
            placed_at="2026-03-05T12:00:00Z",
        ),
    )
    bets["p"] = parlay
    for name, result in (("a", "won"), ("b", "lost"), ("c", "push")):
        client.post(f"/v1/bets/{bets[name]['id']}/settle", json={"result": result}, headers=headers)
    return bets


def _names(
    client: TestClient, headers: Headers, varied: dict[str, dict[str, Any]], **params: Any
) -> list[str]:
    response = client.get("/v1/bets", params=params, headers=headers)
    assert response.status_code == 200, response.text
    by_id = {b["id"]: name for name, b in varied.items()}
    return [by_id[b["id"]] for b in response.json()]


def test_list_sorting(
    client: TestClient, headers: Headers, varied: dict[str, dict[str, Any]]
) -> None:
    assert _names(client, headers, varied) == ["p", "d", "c", "b", "a"]  # default unchanged
    assert _names(client, headers, varied, sort="-placed_at") == ["p", "d", "c", "b", "a"]
    assert _names(client, headers, varied, sort="placed_at") == ["a", "b", "c", "d", "p"]
    assert _names(client, headers, varied, sort="stake") == ["p", "b", "d", "c", "a"]
    assert _names(client, headers, varied, sort="-stake") == ["a", "c", "d", "b", "p"]
    # profit: a +50, c 0, b -10; pending bets (no profit) come last either way, newest first.
    assert _names(client, headers, varied, sort="-profit") == ["a", "c", "b", "p", "d"]
    assert _names(client, headers, varied, sort="profit") == ["b", "c", "a", "p", "d"]


def test_list_filters_and_paging(
    client: TestClient, headers: Headers, varied: dict[str, dict[str, Any]]
) -> None:
    assert _names(client, headers, varied, market="moneyline") == ["d", "b", "a"]
    assert _names(client, headers, varied, market="TOTAL") == ["p", "c"]  # any leg, any case
    assert _names(client, headers, varied, market="spread") == ["p"]
    assert _names(client, headers, varied, market="futures") == []
    assert _names(client, headers, varied, sportsbook="northline") == ["p", "c", "a"]
    assert _names(client, headers, varied, sportsbook="Cardinal Sports") == ["b"]
    assert _names(client, headers, varied, sportsbook="Cardinal") == []  # exact, not prefix
    assert _names(client, headers, varied, bet_type="parlay") == ["p"]
    assert _names(client, headers, varied, bet_type="straight") == ["d", "c", "b", "a"]
    assert _names(client, headers, varied, bet_type="future") == []
    # Filters combine, also with the existing ones.
    assert _names(
        client, headers, varied, sportsbook="Northline", bet_type="straight", sort="stake"
    ) == ["c", "a"]
    assert _names(client, headers, varied, status="pending", market="total") == ["p"]
    assert _names(client, headers, varied, status="won", sportsbook="northline") == ["a"]
    assert _names(client, headers, varied, sort="stake", limit=2) == ["p", "b"]
    assert _names(client, headers, varied, sort="stake", limit=2, offset=2) == ["d", "c"]
    assert _names(client, headers, varied, sort="stake", limit=200, offset=4) == ["a"]


def test_list_rejects_bad_query_values_with_the_envelope(
    client: TestClient, headers: Headers
) -> None:
    for params in (
        {"sort": "odds"},
        {"sort": "+stake"},
        {"sort": "placed_at desc"},
        {"bet_type": "teaser"},
        {"limit": 0},
        {"limit": 1001},
        {"offset": -1},
    ):
        response = client.get("/v1/bets", params=params, headers=headers)
        assert response.status_code == 422, params
        assert_envelope(response.json(), "validation_error")


def test_list_filters_never_cross_users(
    client: TestClient, headers: Headers, other_headers: Headers, varied: dict[str, dict[str, Any]]
) -> None:
    for params in ({"sportsbook": "Northline"}, {"market": "moneyline"}, {"sort": "-stake"}):
        assert client.get("/v1/bets", params=params, headers=other_headers).json() == []
