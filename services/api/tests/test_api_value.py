"""Value screen: best price against the no-vig consensus of the other books."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from oddvex_api.board import VALUE_CAVEAT, VALUE_METHOD
from oddvex_api.providers import Event

from .conftest import AppFactory, admin_headers, set_flag
from .fakes import ControlledProvider, Quote, moneyline, spread, total
from .test_notification_copy import BANNED_PHRASES


@pytest.fixture
def world() -> ControlledProvider:
    return ControlledProvider()


@pytest.fixture
def app(make_app: AppFactory, world: ControlledProvider) -> FastAPI:
    return make_app(provider=world, admin_emails="boss@example.test")


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def fresh(book: str, outcomes: list[tuple[str, float | None, int]]) -> Quote:
    return (book, "open", 10.0, outcomes)


def upcoming(world: ControlledProvider, league: str = "nba") -> Event:
    return world.list_events(league=league, status="upcoming")[0]


def quiet(world: ControlledProvider, event: Event) -> None:
    """Remove every quote of the event so a test controls exactly what is on it."""
    for market in event.markets:
        world.set_odds(event.id, market, [])


def rows_for(client: TestClient, event: Event, **params: Any) -> list[dict[str, Any]]:
    response = client.get("/v1/value", params={"limit": 200, **params})
    assert response.status_code == 200, response.text
    return [row for row in response.json()["rows"] if row["event"]["id"] == event.id]


def american(price: int) -> float:
    return 1 + price / 100 if price > 0 else 1 + 100 / -price


def fair(price: int, other: int) -> float:
    """No-vig probability of the first side of a two-way market."""
    a, b = 1 / american(price), 1 / american(other)
    return a / (a + b)


# ----------------------------------------------------------------- the maths
def test_best_price_against_the_consensus_of_the_other_books(
    client: TestClient, world: ControlledProvider
) -> None:
    event = upcoming(world)
    quiet(world, event)
    world.set_odds(
        event.id,
        "moneyline",
        [
            fresh("northline", moneyline(130, -150)),
            fresh("cardinal", moneyline(110, -150)),
            fresh("summit", moneyline(105, -150)),
        ],
    )
    rows = rows_for(client, event)
    (row,) = rows  # only the home side is above its consensus
    assert row["market"] == "moneyline" and row["outcome_key"] == "home"
    assert row["line"] is None
    assert row["sportsbook"] == {"key": "northline", "name": "Northline"}
    assert row["best_price"]["american"] == 130 and row["best_price"]["decimal"] == 2.3
    # Consensus from cardinal and summit only: northline is not in its own consensus.
    consensus = (fair(110, -150) + fair(105, -150)) / 2
    assert row["books_in_consensus"] == 2
    assert row["consensus_probability"] == pytest.approx(consensus, abs=1e-6)
    assert row["edge"] == pytest.approx(consensus * 2.3 - 1, abs=1e-6)
    assert row["breakeven_probability"] == pytest.approx(1 / 2.3, abs=1e-6)
    assert row["edge"] > 0 and row["consensus_probability"] > row["breakeven_probability"]
    with_itself = (fair(130, -150) + fair(110, -150) + fair(105, -150)) / 3
    assert abs(row["consensus_probability"] - with_itself) > 1e-3
    # Freshness.
    assert row["last_updated"] == "2026-03-14T19:29:50Z"
    assert row["stale_after_seconds"] == 900
    assert row["event"]["status"] == "upcoming"

    # The same best price the odds comparison reports.
    odds = client.get(f"/v1/events/{event.id}/odds").json()
    best_home = next(b for b in odds["best"] if b["outcome_key"] == "home")
    assert best_home["sportsbook_key"] == "northline"
    assert best_home["price"] == row["best_price"]


def test_an_outcome_with_fewer_than_two_other_books_is_skipped(
    client: TestClient, world: ControlledProvider
) -> None:
    event = upcoming(world)
    quiet(world, event)
    world.set_odds(
        event.id,
        "moneyline",
        [fresh("northline", moneyline(300, -150)), fresh("cardinal", moneyline(110, -130))],
    )
    assert rows_for(client, event) == []
    world.set_odds(
        event.id,
        "moneyline",
        [
            fresh("northline", moneyline(300, -130)),
            fresh("cardinal", moneyline(110, -130)),
            fresh("summit", moneyline(110, -130)),
        ],
    )
    client.app.state.cache.clear()  # type: ignore[attr-defined]
    (row,) = rows_for(client, event)
    assert row["books_in_consensus"] == 2 and row["best_price"]["american"] == 300


def test_stale_suspended_and_unavailable_books_count_for_nothing(
    client: TestClient, world: ControlledProvider
) -> None:
    event = upcoming(world)
    quiet(world, event)
    world.set_odds(
        event.id,
        "moneyline",
        [
            ("oldmill", "open", 5000.0, moneyline(900, -2000)),  # stale
            ("kestrel", "suspended", 10.0, moneyline(800, -1500)),
            ("blueharbor", "unavailable", 10.0, []),
            fresh("northline", moneyline(130, -150)),
            fresh("cardinal", moneyline(110, -150)),
            fresh("summit", moneyline(105, -150)),
        ],
    )
    (row,) = rows_for(client, event)
    assert row["sportsbook"]["key"] == "northline" and row["best_price"]["american"] == 130
    assert row["books_in_consensus"] == 2

    # With only the unusable books offering more, and two fresh ones, nothing is listed.
    world.set_odds(
        event.id,
        "moneyline",
        [
            ("oldmill", "open", 5000.0, moneyline(900, -2000)),
            ("kestrel", "suspended", 10.0, moneyline(800, -1500)),
            fresh("northline", moneyline(130, -150)),
            fresh("cardinal", moneyline(110, -130)),
        ],
    )
    client.app.state.cache.clear()  # type: ignore[attr-defined]
    assert rows_for(client, event) == []


def test_spread_and_total_only_compare_books_on_the_same_line(
    client: TestClient, world: ControlledProvider
) -> None:
    event = upcoming(world)
    quiet(world, event)
    world.set_odds(
        event.id,
        "spread",
        [
            fresh("northline", spread(-3.5, 105, -125)),
            fresh("cardinal", spread(-3.5, -110, -110)),
            fresh("summit", spread(-3.5, -112, -108)),
            # A much longer price on another line is a different bet, not a discrepancy.
            fresh("blueharbor", spread(-6.5, 180, -220)),
            fresh("kestrel", spread(-6.5, 175, -215)),
        ],
    )
    world.set_odds(
        event.id,
        "total",
        [
            fresh("northline", total(221.5, -110, -110)),
            fresh("cardinal", total(221.5, -110, -110)),
            fresh("summit", total(221.5, -110, -110)),
        ],
    )
    rows = rows_for(client, event)
    (row,) = rows  # the total has no outcome above consensus; -6.5 has too few books
    assert (row["market"], row["outcome_key"], row["line"]) == ("spread", "home", -3.5)
    assert row["sportsbook"]["key"] == "northline" and row["best_price"]["american"] == 105
    consensus = (fair(-110, -110) + fair(-112, -108)) / 2
    assert row["consensus_probability"] == pytest.approx(consensus, abs=1e-6)
    assert row["edge"] == pytest.approx(consensus * 2.05 - 1, abs=1e-6)
    assert rows_for(client, event, market="total") == []
    assert rows_for(client, event, market="moneyline") == []
    assert rows_for(client, event, market="spread") == rows

    # The away side is quoted at its own line.
    world.set_odds(
        event.id,
        "spread",
        [
            fresh("northline", spread(-3.5, -125, 105)),
            fresh("cardinal", spread(-3.5, -110, -110)),
            fresh("summit", spread(-3.5, -110, -110)),
        ],
    )
    client.app.state.cache.clear()  # type: ignore[attr-defined]
    (away,) = rows_for(client, event)
    assert (away["outcome_key"], away["line"]) == ("away", 3.5)


def test_finished_events_are_not_on_the_screen(
    client: TestClient, world: ControlledProvider
) -> None:
    event = upcoming(world)
    quiet(world, event)
    world.set_odds(
        event.id,
        "moneyline",
        [
            fresh("northline", moneyline(130, -150)),
            fresh("cardinal", moneyline(110, -150)),
            fresh("summit", moneyline(105, -150)),
        ],
    )
    assert len(rows_for(client, event)) == 1
    world.finish(event.id, 101, 99)
    client.app.state.cache.clear()  # type: ignore[attr-defined]
    assert rows_for(client, event) == []


# ---------------------------------------------------------------- the screen
@pytest.fixture
def populated(world: ControlledProvider) -> list[Event]:
    """Four known discrepancies on three events in two leagues."""
    nba = world.list_events(league="nba", status="upcoming")[:2]
    nfl = world.list_events(league="nfl", status="upcoming")[:1]
    books = ("northline", "cardinal", "summit", "blueharbor")
    world.set_odds(
        nba[0].id,
        "moneyline",
        [
            fresh(books[0], moneyline(130, -150)),
            *(fresh(b, moneyline(108, -128)) for b in books[1:]),
        ],
    )
    world.set_odds(
        nba[1].id,
        "total",
        [fresh(books[1], total(219.5, -110, 104)), *(fresh(b, total(219.5)) for b in books[2:])],
    )
    world.set_odds(
        nfl[0].id,
        "spread",
        [fresh(books[2], spread(-2.5, 102, -120)), *(fresh(b, spread(-2.5)) for b in books[:2])],
    )
    world.set_odds(
        nfl[0].id,
        "moneyline",
        [
            fresh(books[0], moneyline(-140, 160)),
            *(fresh(b, moneyline(-145, 125)) for b in books[1:]),
        ],
    )
    return [*nba, *nfl]


def test_the_board_is_sorted_and_consistent(client: TestClient, populated: list[Event]) -> None:
    response = client.get("/v1/value", params={"limit": 200})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"rows", "min_edge", "as_of", "data_mode", "method", "caveat"}
    assert body["data_mode"] == "synthetic" and body["as_of"] == "2026-03-14T19:30:00Z"
    assert body["min_edge"] == 0 and body["method"] == VALUE_METHOD
    assert body["caveat"] == VALUE_CAVEAT
    rows = body["rows"]
    ours = {event.id for event in populated}
    found = {
        (r["event"]["league"], r["market"], r["outcome_key"], r["sportsbook"]["key"])
        for r in rows
        if r["event"]["id"] in ours
    }
    assert found >= {
        ("nba", "moneyline", "home", "northline"),
        ("nba", "total", "under", "cardinal"),
        ("nfl", "spread", "home", "summit"),
        ("nfl", "moneyline", "away", "northline"),
    }
    edges = [row["edge"] for row in rows]
    assert edges == sorted(edges, reverse=True)
    for row in rows:
        assert row["edge"] > 0 and row["books_in_consensus"] >= 2
        assert row["event"]["status"] in ("live", "upcoming")
        assert row["sportsbook"]["key"] != "oldmill"  # the always-stale book
        assert row["breakeven_probability"] == pytest.approx(
            1 / row["best_price"]["decimal"], abs=1e-4
        )
        assert row["edge"] == pytest.approx(
            row["consensus_probability"] * row["best_price"]["decimal"] - 1, abs=1e-4
        )
        assert (row["line"] is None) == (row["market"] == "moneyline")


def test_filters_min_edge_and_limit(client: TestClient, populated: list[Event]) -> None:
    everything = client.get("/v1/value", params={"limit": 200}).json()["rows"]
    assert len(client.get("/v1/value").json()["rows"]) == min(50, len(everything))
    assert len(everything) >= 4
    assert client.get("/v1/value", params={"limit": 1}).json()["rows"] == everything[:1]

    cut = everything[len(everything) // 2]["edge"]
    filtered = client.get("/v1/value", params={"limit": 200, "min_edge": cut}).json()
    assert filtered["min_edge"] == cut
    assert filtered["rows"] == [row for row in everything if row["edge"] >= cut]
    assert client.get("/v1/value", params={"min_edge": 9}).json()["rows"] == []

    for league in ("nba", "nfl"):
        rows = client.get("/v1/value", params={"limit": 200, "league": league}).json()["rows"]
        assert rows == [row for row in everything if row["event"]["league"] == league]
    for market in ("moneyline", "spread", "total"):
        rows = client.get("/v1/value", params={"limit": 200, "market": market}).json()["rows"]
        assert rows == [row for row in everything if row["market"] == market]


@pytest.mark.parametrize(
    "params",
    [
        {"market": "player_points"},
        {"league": "cricket"},
        {"min_edge": -0.1},
        {"min_edge": "abc"},
        {"limit": 0},
        {"limit": 201},
    ],
)
def test_invalid_parameters_use_the_error_envelope(
    client: TestClient, params: dict[str, Any]
) -> None:
    response = client.get("/v1/value", params=params)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_value_screen_is_public_and_behind_its_flag(client: TestClient) -> None:
    assert client.get("/v1/value").status_code == 200  # no sign-in, like the odds routes
    admin = admin_headers(client)
    set_flag(client, admin, "value_screen", False)
    off = client.get("/v1/value")
    assert off.status_code == 404
    assert off.json()["error"] == {
        "code": "feature_disabled",
        "message": "This feature is not available",
        "details": {"flag": "value_screen"},
    }
    assert client.get("/v1/flags").json()["flags"]["value_screen"] is False


# ------------------------------------------------------------------ the copy
def _value_texts(client: TestClient) -> dict[str, str]:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/v1/value"]["get"]
    texts = {
        "method": VALUE_METHOD,
        "caveat": VALUE_CAVEAT,
        "summary": operation["summary"],
        "description": operation["description"],
    }
    for name in ("ValueRowOut", "ValueScreenOut"):
        for field, spec in schema["components"]["schemas"][name]["properties"].items():
            if "description" in spec:
                texts[f"{name}.{field}"] = spec["description"]
    tag = next(tag for tag in schema["tags"] if tag["name"] == "value")
    texts["tag"] = tag["description"]
    return texts


def test_no_banned_phrase_anywhere_on_the_value_screen(client: TestClient) -> None:
    texts = _value_texts(client)
    assert len(texts) > 10
    for where, text in texts.items():
        lowered = text.lower()
        for phrase in (*BANNED_PHRASES, "guaranteed", "lock", "free money", "risk-free"):
            assert phrase not in lowered, f"{where}: banned phrase {phrase!r} in {text!r}"
        assert "!" not in text, where


def test_the_caveat_says_what_the_screen_is_not() -> None:
    lowered = VALUE_CAVEAT.lower()
    assert "not proof of an edge" in lowered
    assert "consensus can be wrong" in lowered
    assert "limits and availability vary" in lowered
    assert "not a prediction" in lowered
    assert "left out of that consensus" in VALUE_METHOD and "at least 2 other" in VALUE_METHOD
