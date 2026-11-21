"""Cached board reads are keyed on the validated request (audit quant-data#1).

Before the fix ``GET /v1/props?market=*`` was computed with a filter that matches nothing
and stored under the key of the unfiltered board, so one anonymous request emptied the prop
board for everyone until the entry expired.
"""

from __future__ import annotations

import json
from collections import Counter

import pytest
from fastapi.testclient import TestClient

from oddvex_api.board import Board
from oddvex_api.cache import InMemoryTTLCache, cache_key
from oddvex_api.config import Settings
from oddvex_api.providers import SyntheticProvider

#: Values an attacker can type that are not a prop market of any league.
JUNK_MARKETS = ("*", "None", "null", "nothing", "points:", ":points", "%", "['points']", " * ")


def cold(client: TestClient) -> None:
    """Empty the shared cache, as if every entry had just expired."""
    client.app.state.cache.clear()  # type: ignore[attr-defined]


def entries(client: TestClient) -> int:
    return len(client.app.state.cache._data)  # type: ignore[attr-defined]


def props(client: TestClient, **params: str) -> list[dict]:
    response = client.get("/v1/props", params=params)
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------- the finding
def test_a_wildcard_market_cannot_empty_the_unfiltered_prop_board(client: TestClient) -> None:
    cold(client)
    assert props(client, market="*") == []
    board = props(client)
    assert len(board) > 300
    assert {row["player"]["league"] for row in board} == {"nba", "nfl", "mlb", "nhl", "soccer"}


def test_a_wildcard_market_cannot_empty_one_league_either(client: TestClient) -> None:
    cold(client)
    assert props(client, league="nba", market="*") == []
    assert len(props(client, league="nba")) == 128
    # The other direction: a warm unfiltered entry is not served for the wildcard.
    assert props(client, league="nba", market="*") == []
    assert props(client, market="*") == []


@pytest.mark.parametrize("junk", JUNK_MARKETS)
def test_an_unknown_market_is_an_empty_answer_whatever_was_cached(
    client: TestClient, junk: str
) -> None:
    cold(client)
    assert props(client, market=junk) == []
    assert props(client, league="nhl", market=junk) == []
    assert len(props(client)) > 300
    assert len(props(client, league="nhl")) > 0
    assert props(client, market=junk) == []  # the warm unfiltered board is not served for it


def test_unknown_markets_are_not_cached_at_all(client: TestClient) -> None:
    """Otherwise every made-up value would take one of the 2,048 cache slots and a few
    thousand requests would push the real entries out."""
    cold(client)
    for index in range(60):
        assert props(client, market=f"junk-{index}") == []
        assert props(client, league="mlb", market=f"junk-{index}") == []
    assert entries(client) == 0


def test_a_blank_market_means_no_market_filter(client: TestClient) -> None:
    cold(client)
    blank = props(client, market="")
    assert len(blank) > 300
    assert blank == props(client)
    cold(client)
    assert props(client, league="nba", market="") == props(client, league="nba")


def test_a_market_of_another_league_is_empty_and_not_cached(client: TestClient) -> None:
    cold(client)
    assert props(client, league="nba", market="hits") == []  # a baseball market
    assert entries(client) == 0
    hits = props(client, market="hits")
    assert hits and {row["player"]["league"] for row in hits} == {"mlb"}
    assert {row["market"] for row in hits} == {"hits"}


def test_each_filter_combination_has_its_own_answer(client: TestClient) -> None:
    cold(client)
    everything = props(client)
    for league in ("nba", "nhl"):
        expected = [row for row in everything if row["player"]["league"] == league]
        assert props(client, league=league) == expected
    for market in ("points", "shots"):
        expected = [row for row in everything if row["market"] == market]
        assert props(client, market=market) == expected
    # "points" is a market of two leagues: the league filter still applies with it.
    nba_points = props(client, league="nba", market="points")
    assert nba_points == [
        row for row in everything if row["market"] == "points" and row["player"]["league"] == "nba"
    ]
    assert len(nba_points) < len(props(client, market="points"))


def test_the_props_route_says_how_market_is_read(client: TestClient) -> None:
    operation = client.get("/openapi.json").json()["paths"]["/v1/props"]["get"]
    description = operation["description"]
    assert "empty list" in description
    assert "no market filter" in description


# ---------------------------------------------------------------- every cached read
def test_cache_keys_cannot_collide() -> None:
    assert cache_key("propsboard", None, None) != cache_key("propsboard", "*", "*")
    assert cache_key("propsboard", None, "nba") != cache_key("propsboard", "nba", None)
    assert cache_key("propsboard", None, None) != cache_key("propsboard", "None", "None")
    assert cache_key("propsboard", None, None) != cache_key("propsboard", "null", None)
    assert cache_key("propsboard", "a", "b:c") != cache_key("propsboard", "a:b", "c")
    assert cache_key("propsboard", 'a","b', None) != cache_key("propsboard", "a", "b")
    assert cache_key("propsboard", "", None) != cache_key("propsboard", None, None)
    assert cache_key("value", None, None) != cache_key("propsboard", None, None)
    assert cache_key("gamelog", "x") != cache_key("gamelog:x")
    assert cache_key("value", "nba", "total") == cache_key("value", "nba", "total")


def stored(client: TestClient) -> dict[str, int]:
    """Cached board reads by kind (the prop board also caches one game log per player)."""
    kinds = Counter(json.loads(key)[0] for key in client.app.state.cache._data)  # type: ignore[attr-defined]
    return {kind: count for kind, count in kinds.items() if kind != "gamelog"}


def value(client: TestClient, **params: str) -> dict:
    response = client.get("/v1/value", params={"limit": "200", **params})
    assert response.status_code == 200, response.text
    return response.json()


def test_the_prop_board_and_the_value_screen_share_one_cache_without_mixing(
    client: TestClient,
) -> None:
    """Both reads are cached on (league, market) in the same cache. Whichever is read
    first, each route gives its own rows."""
    filters: list[dict[str, str]] = [{}, {"league": "nba"}, {"league": "nhl"}]
    alone = []
    for params in filters:
        cold(client)
        board_rows = props(client, **params)
        cold(client)
        alone.append((board_rows, value(client, **params)))
        assert board_rows and all("player" in row for row in board_rows)
    assert alone[0][1]["rows"] and all("edge" in row for row in alone[0][1]["rows"])

    for first_read in ("props", "value"):
        cold(client)
        for params, (board_rows, screen) in zip(filters, alone, strict=True):
            if first_read == "props":
                assert props(client, **params) == board_rows
                assert value(client, **params) == screen
            else:
                assert value(client, **params) == screen
                assert props(client, **params) == board_rows
        # One entry per read and filter: nothing was served from the other read's entry.
        assert stored(client) == {"propsboard": len(filters), "value": len(filters)}
        # Warm: the same answers again.
        for params, (board_rows, screen) in zip(filters, alone, strict=True):
            assert props(client, **params) == board_rows
            assert value(client, **params) == screen
        assert stored(client) == {"propsboard": len(filters), "value": len(filters)}


@pytest.fixture
def board(provider: SyntheticProvider) -> Board:
    return Board(provider, Settings(_env_file=None), InMemoryTTLCache())  # type: ignore[call-arg]


def test_the_value_screen_never_stores_an_unknown_filter(board: Board) -> None:
    """The route only lets known leagues and markets through; the board does not rely on it."""
    for league, market in (("*", None), (None, "*"), ("*", "*"), ("", ""), ("xfl", "moneyline")):
        assert board.value_screen(league, market, 0.0, 200).rows == []
    assert len(board.cache._data) == 0  # type: ignore[attr-defined]
    everything = board.value_screen(None, None, 0.0, 200).rows
    assert everything
    for league, market in (("*", None), (None, "*"), ("*", "*")):
        assert board.value_screen(league, market, 0.0, 200).rows == []
    assert board.value_screen(None, None, 0.0, 200).rows == everything
    totals = board.value_screen(None, "total", 0.0, 200).rows
    assert totals == [row for row in everything if row.market == "total"]


def test_the_prop_board_validates_inside_the_board_too(board: Board) -> None:
    assert board.props_board("*", None) == []
    assert board.props_board(None, "*") == []
    assert board.props_board("nba", "hits") == []
    assert len(board.cache._data) == 0  # type: ignore[attr-defined]
    assert len(board.props_board(None, None)) > 300
    assert board.props_board(None, "*") == []


def test_value_route_rejects_unknown_filters_before_the_cache(client: TestClient) -> None:
    cold(client)
    for params in ({"market": "*"}, {"league": "*"}, {"market": ""}, {"league": ""}):
        response = client.get("/v1/value", params=params)
        assert response.status_code == 422, params
    assert entries(client) == 0
    assert client.get("/v1/props", params={"league": "*"}).status_code == 422
    assert client.get("/v1/props", params={"league": ""}).status_code == 422
    assert entries(client) == 0


def test_the_game_log_is_cached_per_player(client: TestClient) -> None:
    cold(client)
    players = client.get("/v1/players", params={"league": "nba"}).json()[:2]
    logs = []
    for player in players:
        body = client.get(f"/v1/players/{player['id']}/props", params={"window": "season"}).json()
        logs.append([entry["value"] for entry in body["game_log"]])
    assert logs[0] != logs[1]
    again = client.get(f"/v1/players/{players[0]['id']}/props", params={"window": "season"}).json()
    assert [entry["value"] for entry in again["game_log"]] == logs[0]
    # An unknown player is a 404 and leaves nothing behind.
    before = entries(client)
    assert client.get("/v1/players/plr_nba_hct_1:x/props").status_code == 404
    assert entries(client) == before
