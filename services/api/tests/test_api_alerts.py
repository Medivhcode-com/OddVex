"""Alert rules: routes, validation, ownership, and evaluation against a controllable provider."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from oddvex_api.alerts import service as alerts_service
from oddvex_api.alerts.schemas import MAX_ACTIVE_ALERTS
from oddvex_api.board import Board
from oddvex_api.cache import InMemoryTTLCache
from oddvex_api.db import AlertRule, AuditLog, Notification, User
from oddvex_api.notifications import service as notifications_service
from oddvex_api.notifications import templates
from oddvex_api.providers import Event

from .conftest import EXTERNAL_DATABASE_URL, AppFactory
from .fakes import ControlledProvider, moneyline, spread, total
from .test_platform import assert_envelope

Headers = dict[str, str]


@pytest.fixture
def world() -> ControlledProvider:
    return ControlledProvider()


@pytest.fixture
def app(make_app: AppFactory, world: ControlledProvider) -> FastAPI:
    # No throttle: every read of the notifications evaluates the rules.
    return make_app(provider=world, alert_eval_min_seconds=0)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def upcoming(world: ControlledProvider, league: str = "nba", index: int = 0) -> Event:
    return world.list_events(league=league, status="upcoming")[index]


def name(world: ControlledProvider, team_id: str) -> str:
    team = world.get_team(team_id)
    assert team is not None
    return team.name


def create(client: TestClient, headers: Headers, body: dict[str, Any], status: int = 201) -> Any:
    response = client.post("/v1/alerts", json=body, headers=headers)
    assert response.status_code == status, response.text
    return response.json()


def price_alert(event: Event, threshold: Any = 150, **extra: Any) -> dict[str, Any]:
    return {
        "kind": "price_at_least",
        "event_id": event.id,
        "market": "moneyline",
        "outcome_key": "home",
        "threshold": threshold,
        **extra,
    }


def notifications(client: TestClient, headers: Headers) -> list[dict[str, Any]]:
    response = client.get("/v1/notifications", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def evaluate(client: TestClient, headers: Headers) -> dict[str, int]:
    response = client.post("/v1/alerts/evaluate", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def rule(client: TestClient, headers: Headers, rule_id: str) -> dict[str, Any]:
    items = client.get("/v1/alerts", headers=headers).json()["items"]
    return next(item for item in items if item["id"] == rule_id)


def fresh(book: str, outcomes: list[tuple[str, float | None, int]]) -> Any:
    return (book, "open", 10.0, outcomes)


# ------------------------------------------------------------- price_at_least
def test_price_alert_that_is_already_met_fires_on_the_next_read(
    client: TestClient, headers: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world)
    home = name(world, event.home_team_id)
    world.set_odds(
        event.id,
        "moneyline",
        [fresh("northline", moneyline(150, -170)), fresh("cardinal", moneyline(140, -160))],
    )
    created = create(client, headers, price_alert(event, 145))
    assert created["kind"] == "price_at_least" and created["state"] == "active"
    assert created["event_id"] == event.id and created["team_id"] is None
    assert created["market"] == "moneyline" and created["outcome_key"] == "home"
    assert created["threshold"]["american"] == 145 and created["threshold"]["decimal"] == 2.45
    assert created["summary"] == f"{home} moneyline at +145 or higher"
    assert created["event"]["id"] == event.id and created["available"] is True
    assert created["label"] == f"{name(world, event.away_team_id)} at {home}"
    assert created["league"] == "nba" and created["triggered_at"] is None

    (item,) = notifications(client, headers)
    assert item["kind"] == "price_alert" and item["read_at"] is None
    assert item["title"] == "Price reached +150"
    assert item["body"] == f"{home} moneyline is +150 at Northline, at or above your +145 alert."
    assert item["href"] == f"/app/games/{event.id}?market=moneyline"
    assert item["data"]["alert_id"] == created["id"] and item["data"]["event_id"] == event.id
    assert item["data"]["price_american"] == 150 and item["data"]["sportsbook_key"] == "northline"

    after = rule(client, headers, created["id"])
    assert after["state"] == "triggered" and after["triggered_at"] is not None
    # One-shot: nothing more happens however often the rules are evaluated.
    assert evaluate(client, headers) == {"evaluated": 0, "fired": 0, "expired": 0}
    assert len(notifications(client, headers)) == 1


@pytest.mark.parametrize(
    ("threshold", "odds_format"),
    [(150, "american"), ("+150", "american"), (2.5, "decimal"), ("3/2", "fractional")],
)
def test_threshold_is_accepted_in_every_odds_format_and_stored_as_decimal(
    client: TestClient,
    headers: Headers,
    world: ControlledProvider,
    app: FastAPI,
    threshold: Any,
    odds_format: str,
) -> None:
    created = create(
        client, headers, price_alert(upcoming(world), threshold, odds_format=odds_format)
    )
    assert created["threshold"] == {
        "american": 150,
        "decimal": 2.5,
        "fractional": "3/2",
        "implied_probability": 0.4,
    }
    with app.state.session_factory() as db:
        stored = db.scalar(select(AlertRule.threshold_decimal))
    assert float(stored) == 2.5  # type: ignore[arg-type]


def test_price_alert_waits_until_the_threshold_is_met_exactly(
    client: TestClient, headers: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world)
    world.set_odds(event.id, "moneyline", [fresh("northline", moneyline(-111, -109))])
    created = create(client, headers, price_alert(event, -110))
    assert evaluate(client, headers) == {"evaluated": 1, "fired": 0, "expired": 0}
    assert rule(client, headers, created["id"])["state"] == "active"

    world.set_odds(event.id, "moneyline", [fresh("northline", moneyline(-110, -110))])
    assert evaluate(client, headers) == {"evaluated": 1, "fired": 1, "expired": 0}
    (item,) = notifications(client, headers)
    assert item["title"] == "Price reached -110" and "your -110 alert" in item["body"]
    # Running it again creates nothing new.
    assert evaluate(client, headers) == {"evaluated": 0, "fired": 0, "expired": 0}
    assert len(notifications(client, headers)) == 1


def test_stale_suspended_and_unavailable_books_are_ignored(
    client: TestClient, headers: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world)
    world.set_odds(
        event.id,
        "moneyline",
        [
            ("oldmill", "open", 5000.0, moneyline(400, -500)),  # stale
            ("cardinal", "suspended", 10.0, moneyline(300, -400)),
            ("summit", "unavailable", 10.0, []),
            ("kestrel", "closed", 10.0, moneyline(350, -450)),
            fresh("northline", moneyline(120, -140)),
        ],
    )
    created = create(client, headers, price_alert(event, 150))
    assert notifications(client, headers) == []
    assert rule(client, headers, created["id"])["state"] == "active"

    # The same number the odds endpoint reports as best.
    odds = client.get(f"/v1/events/{event.id}/odds", params={"market": "moneyline"}).json()
    best_home = next(b for b in odds["best"] if b["outcome_key"] == "home")
    assert best_home["price"]["american"] == 120 and best_home["sportsbook_key"] == "northline"

    world.set_odds(
        event.id,
        "moneyline",
        [
            ("oldmill", "open", 5000.0, moneyline(400, -500)),
            fresh("northline", moneyline(120, -140)),
            fresh("blueharbor", moneyline(155, -180)),
        ],
    )
    (item,) = notifications(client, headers)
    assert item["title"] == "Price reached +155" and "BlueHarbor Book" in item["body"]


def test_spread_alert_only_compares_books_on_its_own_line(
    client: TestClient, headers: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world)
    home = name(world, event.home_team_id)
    world.set_odds(
        event.id,
        "spread",
        [
            fresh("northline", spread(-3.5, home=120)),  # a far higher price, on another line
            fresh("cardinal", spread(-4.5, home=-110)),
            fresh("summit", spread(-4.5, home=-108)),
        ],
    )
    body = price_alert(event, -105, market="spread", line=-4.5)
    created = create(client, headers, body)
    assert created["line"] == -4.5
    assert created["summary"] == f"{home} -4.5 spread at -105 or higher"
    assert notifications(client, headers) == []

    world.set_odds(
        event.id,
        "spread",
        [fresh("northline", spread(-3.5, home=120)), fresh("summit", spread(-4.5, home=-104))],
    )
    (item,) = notifications(client, headers)
    assert (
        item["body"] == f"{home} -4.5 spread is -104 at Summit Wager, at or above your -105 alert."
    )
    assert item["href"] == f"/app/games/{event.id}?market=spread"
    assert item["data"]["line"] == -4.5

    # The away side of that market is the same number with the other sign.
    away = create(
        client, headers, price_alert(event, -115, market="spread", outcome_key="away", line=4.5)
    )
    assert away["summary"] == f"{name(world, event.away_team_id)} +4.5 spread at -115 or higher"
    assert len(notifications(client, headers)) == 2


def test_total_alert_fires_on_its_line(
    client: TestClient, headers: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world)
    world.set_odds(
        event.id,
        "total",
        [fresh("northline", total(224.5, over=-105)), fresh("cardinal", total(225.5, over=110))],
    )
    create(client, headers, price_alert(event, 100, market="total", outcome_key="over", line=225.5))
    create(client, headers, price_alert(event, 100, market="total", outcome_key="over", line=224.5))
    (item,) = notifications(client, headers)
    assert item["title"] == "Price reached +110" and item["body"].startswith("Over 225.5 in ")


# ------------------------------------------------------------------ line_move
def test_line_move_records_the_baseline_and_fires_at_exactly_min_move(
    client: TestClient, headers: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world)
    home = name(world, event.home_team_id)
    world.set_odds(
        event.id,
        "spread",
        [
            fresh("northline", spread(-3.5)),
            fresh("cardinal", spread(-3.5)),
            fresh("summit", spread(-4.5)),
        ],
    )
    created = create(
        client,
        headers,
        {
            "kind": "line_move",
            "event_id": event.id,
            "market": "spread",
            "outcome_key": "home",
            "min_move": 1,
        },
    )
    assert created["baseline_line"] == -3.5 and created["min_move"] == 1
    assert created["summary"] == (
        f"{created['label']} spread line for {home} moves 1 point or more from -3.5"
    )
    assert notifications(client, headers) == []

    # The consensus is still -3.5 while most books stay there.
    world.set_odds(
        event.id,
        "spread",
        [
            fresh("northline", spread(-3.5)),
            fresh("cardinal", spread(-3.5)),
            fresh("summit", spread(-5.5)),
        ],
    )
    assert evaluate(client, headers)["fired"] == 0
    # Half a point is not enough.
    world.set_odds(
        event.id, "spread", [fresh("northline", spread(-4.0)), fresh("summit", spread(-4.0))]
    )
    assert evaluate(client, headers)["fired"] == 0
    # Exactly one point is.
    world.set_odds(
        event.id, "spread", [fresh("northline", spread(-4.5)), fresh("summit", spread(-4.5))]
    )
    assert evaluate(client, headers) == {"evaluated": 1, "fired": 1, "expired": 0}
    (item,) = notifications(client, headers)
    assert item["kind"] == "line_move" and item["title"] == "Line moved to -4.5"
    assert item["body"] == (
        f"{created['label']} spread: the consensus line for {home} is -4.5. "
        "It was -3.5 when you set this alert."
    )
    assert item["href"] == f"/app/games/{event.id}?market=spread"
    assert rule(client, headers, created["id"])["state"] == "triggered"

    # Re-arming takes the current consensus line as the new baseline.
    rearmed = client.patch(
        f"/v1/alerts/{created['id']}", json={"state": "active"}, headers=headers
    ).json()
    assert rearmed["state"] == "active" and rearmed["baseline_line"] == -4.5
    assert rearmed["triggered_at"] is None
    assert evaluate(client, headers)["fired"] == 0
    world.set_odds(
        event.id, "spread", [fresh("northline", spread(-3.5)), fresh("summit", spread(-3.5))]
    )
    assert evaluate(client, headers)["fired"] == 1  # the other direction
    titles = [n["title"] for n in notifications(client, headers)]
    assert titles == ["Line moved to -3.5", "Line moved to -4.5"]


def test_line_move_for_the_away_side_and_for_totals(
    client: TestClient, headers: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world)
    world.set_odds(
        event.id, "spread", [fresh("northline", spread(-3.5)), fresh("summit", spread(-3.5))]
    )
    world.set_odds(
        event.id, "total", [fresh("northline", total(224.5)), fresh("summit", total(224.5))]
    )
    base = {"kind": "line_move", "event_id": event.id}
    away = create(
        client, headers, {**base, "market": "spread", "outcome_key": "away", "min_move": 2}
    )
    over = create(
        client, headers, {**base, "market": "total", "outcome_key": "over", "min_move": 1.5}
    )
    assert away["baseline_line"] == 3.5 and over["baseline_line"] == 224.5
    assert over["summary"].endswith("total line for the total moves 1.5 points or more from 224.5")

    world.set_odds(
        event.id, "total", [fresh("northline", total(223.0)), fresh("summit", total(223.0))]
    )
    (item,) = notifications(client, headers)
    assert item["title"] == "Line moved to 223" and item["data"]["baseline_line"] == 224.5
    assert rule(client, headers, away["id"])["state"] == "active"


def test_line_move_needs_a_current_line_to_start_from(
    client: TestClient, headers: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world)
    world.set_odds(event.id, "spread", [("oldmill", "open", 5000.0, spread(-3.5))])
    body = {
        "kind": "line_move",
        "event_id": event.id,
        "market": "spread",
        "outcome_key": "home",
        "min_move": 1,
    }
    assert_envelope(create(client, headers, body, status=422), "line_not_available")
    assert_envelope(
        create(client, headers, {**body, "market": "moneyline"}, status=422), "validation_error"
    )
    assert_envelope(
        create(client, headers, {**body, "min_move": 0}, status=422), "validation_error"
    )
    assert_envelope(
        create(client, headers, {**body, "min_move": 0.001}, status=422), "validation_error"
    )


# ----------------------------------------------------------------- game_start
def test_event_game_start_fires_inside_the_window_and_only_once(
    client: TestClient, headers: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world)
    to_start = event.start_time - world.current
    assert to_start > timedelta(minutes=31)
    created = create(
        client, headers, {"kind": "game_start", "event_id": event.id, "minutes_before": 30}
    )
    assert created["minutes_before"] == 30
    assert created["summary"] == f"{created['label']}, 30 minutes before the start"

    world.current = event.start_time - timedelta(minutes=30, seconds=1)
    assert notifications(client, headers) == []
    world.current = event.start_time - timedelta(minutes=30)
    (item,) = notifications(client, headers)
    assert item["kind"] == "game_start"
    assert item["title"] == f"Game starts at {event.start_time:%H:%M} UTC"
    assert item["body"].startswith(f"{created['label']} starts at {event.start_time:%H:%M} UTC on ")
    assert item["body"].endswith("Your alert is set for 30 minutes before the start.")
    assert item["href"] == f"/app/games/{event.id}"
    assert rule(client, headers, created["id"])["state"] == "triggered"
    world.current = event.start_time - timedelta(minutes=5)
    assert len(notifications(client, headers)) == 1


def test_event_game_start_that_was_never_evaluated_in_time_expires(
    client: TestClient, headers: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world)
    created = create(
        client, headers, {"kind": "game_start", "event_id": event.id, "minutes_before": 5}
    )
    world.current = event.start_time + timedelta(minutes=10)  # nobody opened the app in time
    assert evaluate(client, headers) == {"evaluated": 1, "fired": 0, "expired": 1}
    assert notifications(client, headers) == []
    assert rule(client, headers, created["id"])["state"] == "expired"


def test_team_game_start_fires_for_successive_games_and_stays_active(
    client: TestClient, headers: Headers, world: ControlledProvider
) -> None:
    first = upcoming(world)
    team_id = first.home_team_id
    created = create(
        client, headers, {"kind": "game_start", "team_id": team_id, "minutes_before": 60}
    )
    assert created["team"]["id"] == team_id and created["event"] is None
    assert created["label"] == name(world, team_id)
    assert created["summary"] == f"Each {name(world, team_id)} game, 60 minutes before the start"
    assert notifications(client, headers) == []

    world.current = first.start_time - timedelta(minutes=45)
    assert [n["data"]["event_id"] for n in notifications(client, headers)] == [first.id]
    assert len(notifications(client, headers)) == 1  # not again for the same game
    assert rule(client, headers, created["id"])["state"] == "active"

    world.current = first.start_time + timedelta(hours=6)
    second = world.next_event_for_team(team_id)
    assert second is not None and second.id != first.id
    world.current = second.start_time - timedelta(minutes=10)
    assert [n["data"]["event_id"] for n in notifications(client, headers)] == [second.id, first.id]
    assert rule(client, headers, created["id"])["state"] == "active"
    assert evaluate(client, headers)["fired"] == 0


# ----------------------------------------------------------------- game_final
def test_event_game_final_fires_with_the_score(
    client: TestClient, headers: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world)
    created = create(client, headers, {"kind": "game_final", "event_id": event.id})
    assert created["summary"] == f"Final score of {created['label']}"
    assert notifications(client, headers) == []

    world.finish(event.id, home=101, away=99)
    (item,) = notifications(client, headers)
    home, away = name(world, event.home_team_id), name(world, event.away_team_id)
    assert item["kind"] == "game_final"
    assert item["body"] == f"Final score: {away} 99, {home} 101."
    assert item["title"].startswith("Final: ") and " 99, " in item["title"]
    assert item["data"] == {
        "alert_id": created["id"],
        "event_id": event.id,
        "home_score": 101,
        "away_score": 99,
    }
    assert rule(client, headers, created["id"])["state"] == "triggered"


def test_team_game_final_reports_only_games_that_end_after_it_was_created(
    client: TestClient, headers: Headers, world: ControlledProvider, app: FastAPI
) -> None:
    live = world.list_events(league="nba", status="live")[0]
    team_id = live.home_team_id
    already_final = [
        e
        for e in world.list_events(league="nba", status="final")
        if team_id in (e.home_team_id, e.away_team_id)
    ]
    assert already_final  # the team has finished games in the provider's window
    created = create(client, headers, {"kind": "game_final", "team_id": team_id})
    assert created["summary"] == f"Final score of each {name(world, team_id)} game"
    assert notifications(client, headers) == []

    world.finish(live.id, home=88, away=90)
    (item,) = notifications(client, headers)
    assert item["data"]["event_id"] == live.id and item["data"]["away_score"] == 90
    assert rule(client, headers, created["id"])["state"] == "active"
    assert evaluate(client, headers)["fired"] == 0

    # Paused while the next game ends: that game is not reported after resuming.
    client.patch(f"/v1/alerts/{created['id']}", json={"state": "paused"}, headers=headers)
    other = next(
        e
        for e in world.list_events(league="nba", status="upcoming")
        if team_id in (e.home_team_id, e.away_team_id)
    )
    world.finish(other.id, home=1, away=2)
    assert evaluate(client, headers) == {"evaluated": 0, "fired": 0, "expired": 0}
    resumed = client.patch(
        f"/v1/alerts/{created['id']}", json={"state": "active"}, headers=headers
    ).json()
    assert resumed["state"] == "active"
    assert evaluate(client, headers)["fired"] == 0
    assert len(notifications(client, headers)) == 1


# --------------------------------------------------------------------- expiry
def test_rules_expire_when_the_event_ends_or_disappears_except_game_final(
    client: TestClient, headers: Headers, world: ControlledProvider
) -> None:
    ended, gone = upcoming(world, index=0), upcoming(world, index=1)
    for event in (ended, gone):
        world.set_odds(
            event.id, "spread", [fresh("northline", spread(-2.5)), fresh("summit", spread(-2.5))]
        )
    ids: dict[str, str] = {}
    for tag, event in (("ended", ended), ("gone", gone)):
        ids[f"{tag}:price"] = create(client, headers, price_alert(event, 900))["id"]
        ids[f"{tag}:line"] = create(
            client,
            headers,
            {
                "kind": "line_move",
                "event_id": event.id,
                "market": "spread",
                "outcome_key": "home",
                "min_move": 20,
            },
        )["id"]
        ids[f"{tag}:start"] = create(
            client, headers, {"kind": "game_start", "event_id": event.id, "minutes_before": 5}
        )["id"]
        ids[f"{tag}:final"] = create(client, headers, {"kind": "game_final", "event_id": event.id})[
            "id"
        ]

    world.finish(ended.id, home=100, away=90)
    world.hide(gone.id)
    result = evaluate(client, headers)
    assert result == {"evaluated": 8, "fired": 1, "expired": 7}
    states = {tag: rule(client, headers, rule_id)["state"] for tag, rule_id in ids.items()}
    assert states == {
        "ended:price": "expired",
        "ended:line": "expired",
        "ended:start": "expired",
        "ended:final": "triggered",  # the one exception: a final event is what it waits for
        "gone:price": "expired",
        "gone:line": "expired",
        "gone:start": "expired",
        "gone:final": "expired",
    }
    assert [n["kind"] for n in notifications(client, headers)] == ["game_final"]
    gone_rule = rule(client, headers, ids["gone:price"])
    assert gone_rule["available"] is False and gone_rule["event"] is None
    assert gone_rule["summary"] == "Home team moneyline at +900 or higher"
    # Expired rules are not evaluated again.
    assert evaluate(client, headers) == {"evaluated": 0, "fired": 0, "expired": 0}
    expired = client.get("/v1/alerts", params={"state": "expired"}, headers=headers).json()
    assert len(expired["items"]) == 7


def test_a_live_event_can_still_trigger_a_price_alert(
    client: TestClient, headers: Headers, world: ControlledProvider
) -> None:
    live = world.list_events(league="nba", status="live")[0]
    world.set_odds(live.id, "moneyline", [fresh("northline", moneyline(210, -260))])
    create(client, headers, price_alert(live, 200))
    assert [n["title"] for n in notifications(client, headers)] == ["Price reached +210"]


# ----------------------------------------------------------------- validation
def test_creating_on_an_unknown_or_finished_event_is_a_422(
    client: TestClient, headers: Headers, world: ControlledProvider
) -> None:
    final = world.list_events(league="nba", status="final")[0]
    live = world.list_events(league="nba", status="live")[0]
    for body in (
        price_alert(final),
        {
            "kind": "line_move",
            "event_id": final.id,
            "market": "total",
            "outcome_key": "over",
            "min_move": 1,
        },
        {"kind": "game_start", "event_id": final.id, "minutes_before": 30},
        {"kind": "game_final", "event_id": final.id},
        {"kind": "game_start", "event_id": live.id, "minutes_before": 30},
    ):
        error = create(client, headers, body, status=422)
        assert_envelope(error, "event_not_open")
    for body in (
        {**price_alert(final), "event_id": "evt_nba_19990101_0"},
        {"kind": "game_final", "event_id": "nope"},
        {"kind": "game_start", "event_id": "nope", "minutes_before": 30},
    ):
        assert_envelope(create(client, headers, body, status=422), "unknown_event")
    assert_envelope(
        create(client, headers, {"kind": "game_final", "team_id": "team_nope"}, status=422),
        "unknown_team",
    )
    assert client.get("/v1/alerts", headers=headers).json() == {"items": []}


def test_per_kind_fields_are_validated(
    client: TestClient, headers: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world)
    soccer = upcoming(world, league="soccer")
    assert "spread" not in soccer.markets

    def error(body: dict[str, Any]) -> dict[str, Any]:
        return create(client, headers, body, status=422)["error"]

    # Selection rules, like structured bet legs.
    assert error(price_alert(event, outcome_key="draw"))["code"] == "invalid_selection"
    assert error(price_alert(event, outcome_key="over"))["code"] == "invalid_selection"
    assert error(price_alert(event, market="total"))["code"] == "invalid_selection"  # home on total
    missing_line = error(price_alert(event, market="spread"))
    assert missing_line["code"] == "invalid_selection" and "needs a line" in missing_line["message"]
    assert error(price_alert(event, line=-3.5))["code"] == "invalid_selection"  # moneyline + line
    unavailable = error(price_alert(soccer, market="spread", line=-0.5))
    assert unavailable["code"] == "market_not_available"
    assert unavailable["details"]["available_markets"] == ["moneyline", "total"]
    bad_outcome = error(price_alert(event, market="spread", outcome_key="over", line=-3.5))
    assert bad_outcome["details"]["valid_outcome_keys"] == ["home", "away"]
    # A draw is fine where the moneyline is 3-way.
    assert create(client, headers, price_alert(soccer, outcome_key="draw"))["outcome_key"] == "draw"

    # Shape rules: the envelope's validation_error with a location per problem.
    for body in (
        {"kind": "price_at_least", "event_id": event.id},  # missing fields
        {**price_alert(event), "kind": "nonsense"},
        {k: v for k, v in price_alert(event).items() if k != "kind"},
        {**price_alert(event), "minutes_before": 30},  # a field of another kind
        {**price_alert(event), "market": "player_points"},
        {"kind": "game_start", "event_id": event.id, "minutes_before": 4},
        {"kind": "game_start", "event_id": event.id, "minutes_before": 1441},
        {"kind": "game_start", "event_id": event.id},
        {"kind": "game_start", "minutes_before": 30},  # neither event nor team
        {"kind": "game_final", "event_id": event.id, "team_id": event.home_team_id},  # both
        {"kind": "game_final"},
        {"kind": "line_move", "event_id": event.id, "market": "total", "outcome_key": "over"},
        {
            "kind": "line_move",
            "event_id": event.id,
            "market": "total",
            "outcome_key": "over",
            "min_move": -1,
        },
    ):
        problem = error(body)
        assert problem["code"] == "validation_error", body
        assert problem["details"] and {"loc", "message", "type"} <= set(problem["details"][0])

    # Prices that are not prices.
    for threshold, odds_format in ((50, "american"), (1.0, "decimal"), ("abc", "american")):
        response = client.post(
            "/v1/alerts",
            json=price_alert(event, threshold, odds_format=odds_format),
            headers=headers,
        )
        assert response.status_code == 422, response.text
        assert set(response.json()) == {"error"}
    assert len(client.get("/v1/alerts", headers=headers).json()["items"]) == 1


# ------------------------------------------------------- duplicates and caps
def test_an_exact_duplicate_of_an_active_rule_returns_the_existing_rule(
    client: TestClient, headers: Headers, world: ControlledProvider, other_headers: Headers
) -> None:
    event = upcoming(world)
    first = create(client, headers, price_alert(event, 900))
    again = create(client, headers, price_alert(event, "+900"), status=200)
    assert again["id"] == first["id"]
    same_price_other_format = create(
        client, headers, price_alert(event, 10.0, odds_format="decimal"), status=200
    )
    assert same_price_other_format["id"] == first["id"]
    assert create(client, headers, price_alert(event, 901))["id"] != first["id"]
    assert create(client, headers, price_alert(event, 900, outcome_key="away"))["id"] != first["id"]
    # Another user's identical rule is their own.
    assert create(client, other_headers, price_alert(event, 900))["id"] != first["id"]

    start = {"kind": "game_start", "team_id": event.home_team_id, "minutes_before": 30}
    start_id = create(client, headers, start)["id"]
    assert create(client, headers, start, status=200)["id"] == start_id
    assert create(client, headers, {**start, "minutes_before": 31})["id"] != start_id
    final = {"kind": "game_final", "event_id": event.id}
    final_id = create(client, headers, final)["id"]
    assert create(client, headers, final, status=200)["id"] == final_id

    # Only active rules count as duplicates: a paused one does not block a new rule.
    client.patch(f"/v1/alerts/{first['id']}", json={"state": "paused"}, headers=headers)
    replacement = create(client, headers, price_alert(event, 900))
    assert replacement["id"] != first["id"]
    # ...and resuming the paused one would now create a second identical active rule.
    conflict = client.patch(f"/v1/alerts/{first['id']}", json={"state": "active"}, headers=headers)
    assert conflict.status_code == 409
    assert_envelope(conflict.json(), "alert_duplicate")


def test_at_most_100_active_rules_per_user(
    client: TestClient, headers: Headers, world: ControlledProvider, other_headers: Headers
) -> None:
    event = upcoming(world)
    assert MAX_ACTIVE_ALERTS == 100
    ids = [
        create(
            client, headers, {"kind": "game_start", "event_id": event.id, "minutes_before": 5 + i}
        )["id"]
        for i in range(100)
    ]
    full = client.post("/v1/alerts", json=price_alert(event), headers=headers)
    assert full.status_code == 409
    assert_envelope(full.json(), "alerts_full")
    assert full.json()["error"]["details"] == {"max_active": 100}
    # An existing duplicate is still returned, and other users are unaffected.
    duplicate = {"kind": "game_start", "event_id": event.id, "minutes_before": 5}
    assert create(client, headers, duplicate, status=200)["id"] == ids[0]
    create(client, other_headers, price_alert(event))

    # Pausing one frees a slot; with the slot taken, the paused rule cannot be resumed.
    client.patch(f"/v1/alerts/{ids[0]}", json={"state": "paused"}, headers=headers)
    create(client, headers, price_alert(event))
    resume = client.patch(f"/v1/alerts/{ids[0]}", json={"state": "active"}, headers=headers)
    assert resume.status_code == 409
    assert_envelope(resume.json(), "alerts_full")
    # Deleting one makes room again.
    assert client.delete(f"/v1/alerts/{ids[1]}", headers=headers).status_code == 204
    resumed = client.patch(f"/v1/alerts/{ids[0]}", json={"state": "active"}, headers=headers)
    assert resumed.status_code == 200 and resumed.json()["state"] == "active"
    assert (
        len(client.get("/v1/alerts", params={"state": "active"}, headers=headers).json()["items"])
        == 100
    )


# ------------------------------------------------------- pause, resume, re-arm
def test_pause_resume_and_rearm(
    client: TestClient, headers: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world)
    world.set_odds(event.id, "moneyline", [fresh("northline", moneyline(150, -170))])
    created = create(client, headers, price_alert(event, 145))
    url = f"/v1/alerts/{created['id']}"

    paused = client.patch(url, json={"state": "paused"}, headers=headers)
    assert paused.status_code == 200 and paused.json()["state"] == "paused"
    # A paused rule is not evaluated, even though its condition is met.
    assert evaluate(client, headers) == {"evaluated": 0, "fired": 0, "expired": 0}
    assert notifications(client, headers) == []
    assert client.patch(url, json={"state": "paused"}, headers=headers).json()["state"] == "paused"

    resumed = client.patch(url, json={"state": "active"}, headers=headers)
    assert resumed.status_code == 200 and resumed.json()["state"] == "active"
    assert len(notifications(client, headers)) == 1
    assert rule(client, headers, created["id"])["state"] == "triggered"

    # A triggered rule cannot be paused, but it can be re-armed and then fires again.
    not_pausable = client.patch(url, json={"state": "paused"}, headers=headers)
    assert not_pausable.status_code == 409
    assert_envelope(not_pausable.json(), "invalid_state_transition")
    rearmed = client.patch(url, json={"state": "active"}, headers=headers).json()
    assert rearmed["state"] == "active" and rearmed["triggered_at"] is None
    assert evaluate(client, headers) == {"evaluated": 1, "fired": 1, "expired": 0}
    assert [n["title"] for n in notifications(client, headers)] == ["Price reached +150"] * 2

    # Once the event is over there is nothing left to re-arm.
    world.finish(event.id, home=1, away=0)
    over = client.patch(url, json={"state": "active"}, headers=headers)
    assert over.status_code == 422
    assert_envelope(over.json(), "event_not_open")
    assert rule(client, headers, created["id"])["state"] == "triggered"

    for body in (
        {"state": "triggered"},
        {"state": "expired"},
        {},
        {"state": "active", "threshold": 1},
    ):
        invalid = client.patch(url, json=body, headers=headers)
        assert invalid.status_code == 422
        assert_envelope(invalid.json(), "validation_error")


# ------------------------------------------------------------------ ownership
def test_rules_are_private_to_their_owner(
    client: TestClient, headers: Headers, other_headers: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world)
    world.set_odds(event.id, "moneyline", [fresh("northline", moneyline(150, -170))])
    mine = create(client, headers, price_alert(event, 145))
    url = f"/v1/alerts/{mine['id']}"

    assert client.get("/v1/alerts", headers=other_headers).json() == {"items": []}
    for response in (
        client.patch(url, json={"state": "paused"}, headers=other_headers),
        client.delete(url, headers=other_headers),
    ):
        assert response.status_code == 404
        assert_envelope(response.json(), "not_found")
    # The other user's evaluation and notifications never touch my rule.
    assert evaluate(client, other_headers) == {"evaluated": 0, "fired": 0, "expired": 0}
    assert notifications(client, other_headers) == []
    assert rule(client, headers, mine["id"])["state"] == "active"
    assert len(notifications(client, headers)) == 1
    assert notifications(client, other_headers) == []


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/v1/alerts"),
        ("POST", "/v1/alerts"),
        ("POST", "/v1/alerts/evaluate"),
        ("PATCH", "/v1/alerts/abc"),
        ("DELETE", "/v1/alerts/abc"),
    ],
)
def test_alert_routes_require_authentication(client: TestClient, method: str, path: str) -> None:
    response = client.request(method, path, json={})
    assert response.status_code == 401
    assert_envelope(response.json(), "not_authenticated")
    bad = client.request(method, path, json={}, headers={"Authorization": "Bearer nope"})
    assert bad.status_code == 401
    assert_envelope(bad.json(), "invalid_token")


# --------------------------------------------------------- list, delete, audit
def test_list_is_newest_first_and_filters_by_state(
    client: TestClient, headers: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world)
    world.set_odds(event.id, "moneyline", [fresh("northline", moneyline(150, -170))])
    first = create(client, headers, price_alert(event, 145))
    second = create(client, headers, price_alert(event, 900))
    third = create(client, headers, {"kind": "game_final", "event_id": event.id})
    client.patch(f"/v1/alerts/{third['id']}", json={"state": "paused"}, headers=headers)
    evaluate(client, headers)

    listed = client.get("/v1/alerts", headers=headers).json()
    assert set(listed) == {"items"}
    assert [item["id"] for item in listed["items"]] == [third["id"], second["id"], first["id"]]
    for state, expected in (
        ("active", [second["id"]]),
        ("triggered", [first["id"]]),
        ("paused", [third["id"]]),
        ("expired", []),
    ):
        items = client.get("/v1/alerts", params={"state": state}, headers=headers).json()["items"]
        assert [item["id"] for item in items] == expected
    invalid = client.get("/v1/alerts", params={"state": "done"}, headers=headers)
    assert invalid.status_code == 422
    assert_envelope(invalid.json(), "validation_error")


def test_delete_keeps_delivered_notifications_and_everything_is_audited(
    client: TestClient, headers: Headers, world: ControlledProvider, app: FastAPI
) -> None:
    event = upcoming(world)
    world.set_odds(event.id, "moneyline", [fresh("northline", moneyline(150, -170))])
    created = create(client, headers, price_alert(event, 145))
    expiring = create(
        client, headers, {"kind": "game_start", "event_id": event.id, "minutes_before": 5}
    )
    assert len(notifications(client, headers)) == 1
    world.finish(event.id, home=3, away=1)
    evaluate(client, headers)

    assert client.delete(f"/v1/alerts/{created['id']}", headers=headers).status_code == 204
    missing = client.delete(f"/v1/alerts/{created['id']}", headers=headers)
    assert missing.status_code == 404
    assert_envelope(missing.json(), "not_found")
    assert [item["id"] for item in client.get("/v1/alerts", headers=headers).json()["items"]] == [
        expiring["id"]
    ]
    assert len(notifications(client, headers)) == 1

    with app.state.session_factory() as db:
        rows = list(
            db.scalars(
                select(AuditLog)
                .where(AuditLog.action.like("alert.%"))
                .order_by(AuditLog.created_at, AuditLog.id)
            )
        )
    by_action = {row.action: row for row in rows}
    assert sorted(row.action for row in rows) == [
        "alert.create",
        "alert.create",
        "alert.delete",
        "alert.expired",
        "alert.fired",
    ]
    assert by_action["alert.delete"].entity_id == created["id"]
    assert by_action["alert.delete"].entity_type == "alert_rule"
    assert by_action["alert.delete"].details == {
        "kind": "price_at_least",
        "event_id": event.id,
        "team_id": None,
    }
    assert by_action["alert.fired"].details == {"kind": "price_at_least", "fired": 1, "notified": 1}
    assert by_action["alert.expired"].entity_id == expiring["id"]
    assert all(row.request_id for row in rows)


# ---------------------------------------------------- preferences, idempotency
def test_a_disabled_kind_changes_rule_state_without_creating_a_notification(
    client: TestClient, headers: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world)
    world.set_odds(event.id, "moneyline", [fresh("northline", moneyline(150, -170))])
    client.put(
        "/v1/me/notification-preferences",
        json={"in_app": {"price_alert": False}},
        headers=headers,
    )
    created = create(client, headers, price_alert(event, 145))
    final = create(client, headers, {"kind": "game_final", "event_id": event.id})
    world.finish(event.id, home=2, away=1)
    # The price rule's event is final, so it expires; test the suppression on a live one.
    other = upcoming(world, index=1)
    world.set_odds(other.id, "moneyline", [fresh("northline", moneyline(150, -170))])
    suppressed = create(client, headers, price_alert(other, 145))

    assert evaluate(client, headers) == {"evaluated": 3, "fired": 2, "expired": 1}
    assert rule(client, headers, suppressed["id"])["state"] == "triggered"
    assert rule(client, headers, created["id"])["state"] == "expired"
    assert rule(client, headers, final["id"])["state"] == "triggered"
    assert [n["kind"] for n in notifications(client, headers)] == ["game_final"]


def test_evaluation_is_idempotent_and_safe_to_repeat_for_the_same_rule(
    client: TestClient, headers: Headers, world: ControlledProvider, app: FastAPI
) -> None:
    event = upcoming(world)
    world.set_odds(event.id, "moneyline", [fresh("northline", moneyline(150, -170))])
    created = create(client, headers, price_alert(event, 145))
    board = Board(world, app.state.settings, InMemoryTTLCache())

    with app.state.session_factory() as db:
        user = db.scalar(select(User))
        assert user is not None
        first = alerts_service.evaluate_user_alerts(db, user, board.now, board)
        second = alerts_service.evaluate_user_alerts(db, user, board.now, board)
        db.commit()
        assert (first.evaluated, first.fired, first.expired) == (1, 1, 0)
        assert (second.evaluated, second.fired, second.expired) == (0, 0, 0)

        # What a second, concurrent run would have seen: the rule still active. The unique
        # (user_id, dedupe_key) constraint stops it from notifying again.
        stored = db.get(AlertRule, created["id"])
        assert stored is not None
        stored.state = "active"
        db.commit()
        raced = alerts_service.evaluate_user_alerts(db, user, board.now, board)
        db.commit()
        assert (raced.evaluated, raced.fired) == (1, 0)
        assert db.get(AlertRule, created["id"]).state == "triggered"  # type: ignore[union-attr]
        rows = list(db.scalars(select(Notification)))
        assert len(rows) == 1 and rows[0].rule_id == created["id"]
        assert rows[0].dedupe_key == f"alert:{created['id']}:0:{event.id}"

        # The channel itself reports the duplicate.
        draft = templates.game_final(
            rule_id="r",
            dedupe_key="same-key",
            event_id=event.id,
            home="A",
            away="B",
            home_abbr="A",
            away_abbr="B",
            home_score=1,
            away_score=0,
        )
        assert notifications_service.notify(db, user.id, draft) == "delivered"
        assert notifications_service.notify(db, user.id, draft) == "duplicate"
        db.commit()
        assert len(list(db.scalars(select(Notification)))) == 2
    assert len(notifications(client, headers)) == 2


@pytest.mark.skipif(
    not (EXTERNAL_DATABASE_URL or "").startswith("postgres"),
    reason="needs a database with real concurrent writers (set ODDVEX_TEST_DATABASE_URL)",
)
def test_two_concurrent_evaluations_create_one_notification(
    client: TestClient, headers: Headers, world: ControlledProvider, app: FastAPI
) -> None:
    event = upcoming(world)
    world.set_odds(event.id, "moneyline", [fresh("northline", moneyline(150, -170))])
    create(client, headers, price_alert(event, 145))
    factory = app.state.session_factory
    results: list[int] = []

    def second_run() -> None:
        board = Board(world, app.state.settings, InMemoryTTLCache())
        with factory() as db:
            user = db.scalar(select(User))
            # Blocks on the unique index until the first transaction commits.
            results.append(alerts_service.evaluate_user_alerts(db, user, board.now, board).fired)
            db.commit()

    board = Board(world, app.state.settings, InMemoryTTLCache())
    with factory() as db:
        user = db.scalar(select(User))
        assert user is not None
        first = alerts_service.evaluate_user_alerts(db, user, board.now, board)
        thread = threading.Thread(target=second_run)
        thread.start()
        thread.join(timeout=1.0)  # the second run is now waiting on the first one's insert
        assert thread.is_alive()
        db.commit()
        thread.join(timeout=10.0)
    assert not thread.is_alive()
    assert first.fired == 1 and results == [0]
    with factory() as db:
        assert len(list(db.scalars(select(Notification)))) == 1
        assert db.scalar(select(AlertRule.state)) == "triggered"
