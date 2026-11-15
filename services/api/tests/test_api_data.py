"""Public sports-data routes."""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from .conftest import FROZEN_NOW


def events(client: TestClient, **params: str) -> list[dict]:
    response = client.get("/v1/events", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_health_and_meta(client: TestClient) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["data_mode"] == "synthetic"
    meta = client.get("/v1/meta").json()
    assert set(meta) >= {"data_mode", "provider", "version", "server_time"}
    assert (meta["data_mode"], meta["provider"]) == ("synthetic", "synthetic")
    assert datetime.fromisoformat(meta["server_time"]) == FROZEN_NOW
    assert meta["server_time"].endswith("Z")
    assert "synthetic" in meta["notice"].lower()


def test_leagues_and_sportsbooks(client: TestClient) -> None:
    leagues = client.get("/v1/leagues").json()
    assert [league["key"] for league in leagues] == ["nba", "nfl", "mlb", "nhl", "soccer"]
    soccer = leagues[-1]
    assert soccer["has_draw"] is True
    assert soccer["markets"] == ["moneyline", "total"]
    books = client.get("/v1/sportsbooks").json()
    assert len(books) == 6
    assert all(set(book) == {"key", "name"} for book in books)


def test_event_list_shape(client: TestClient) -> None:
    items = events(client)
    assert len(items) == 160
    assert {e["status"] for e in items} == {"live", "upcoming", "final"}
    assert [e["start_time"] for e in items] == sorted(e["start_time"] for e in items)
    for event in items:
        assert set(event) == {
            "id", "league", "home_team", "away_team", "start_time", "status", "score",
            "status_detail", "best_moneyline",
        }  # fmt: skip
        assert set(event["home_team"]) == {"id", "name", "abbreviation"}
        assert isinstance(event["id"], str)
        if event["status"] == "upcoming":
            assert event["score"] is None and event["status_detail"] is None
        else:
            assert set(event["score"]) == {"home", "away"}
        if event["status"] == "final":
            assert event["status_detail"] == "Final"
            assert event["best_moneyline"] is None
        if event["status"] == "live":
            assert event["status_detail"] not in (None, "Final")


def test_event_filters(client: TestClient) -> None:
    assert {e["league"] for e in events(client, league="nhl")} == {"nhl"}
    assert {e["status"] for e in events(client, status="live")} == {"live"}
    live_nba = events(client, league="nba", status="live")
    assert len(live_nba) == 1
    assert live_nba[0]["status_detail"].startswith("Q")
    day = events(client, date="2026-03-15")
    assert len(day) == 20
    assert {e["start_time"][:10] for e in day} == {"2026-03-15"}
    assert events(client, date="2030-01-01") == []


@pytest.mark.parametrize(
    "params",
    [{"league": "cricket"}, {"status": "postponed"}, {"date": "tomorrow"}, {"date": "2026-13-40"}],
)
def test_event_filter_validation(client: TestClient, params: dict[str, str]) -> None:
    response = client.get("/v1/events", params=params)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_best_moneyline_in_summaries(client: TestClient) -> None:
    upcoming = events(client, league="nba", status="upcoming")[0]
    best = upcoming["best_moneyline"]
    assert best["draw"] is None
    for side in ("home", "away"):
        assert set(best[side]) == {"price", "sportsbook"}
        assert set(best[side]["price"]) == {
            "american",
            "decimal",
            "fractional",
            "implied_probability",
        }
        assert best[side]["sportsbook"]["key"] != "oldmill"  # the stale book can never be best
    soccer = events(client, league="soccer", status="upcoming")[0]
    assert soccer["best_moneyline"]["draw"] is not None


def test_event_detail(client: TestClient) -> None:
    summary = events(client, league="nfl", status="upcoming")[0]
    detail = client.get(f"/v1/events/{summary['id']}").json()
    assert detail["available_markets"] == ["moneyline", "spread", "total"]
    assert detail["id"] == summary["id"]
    assert detail["has_draw"] is False
    assert detail["data_mode"] == "synthetic"
    assert len(detail["players"]) == 8
    assert {p["team"]["id"] for p in detail["players"]} == {
        summary["home_team"]["id"],
        summary["away_team"]["id"],
    }
    soccer = events(client, league="soccer")[0]
    assert client.get(f"/v1/events/{soccer['id']}").json()["available_markets"] == [
        "moneyline",
        "total",
    ]


def test_unknown_event_is_404(client: TestClient) -> None:
    for path in (
        "/v1/events/evt_nope",
        "/v1/events/evt_nope/odds",
        "/v1/events/evt_nope/line-history",
    ):
        response = client.get(path)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"


@pytest.mark.parametrize("market", ["moneyline", "spread", "total"])
def test_odds_comparison(client: TestClient, market: str) -> None:
    event = events(client, league="nba", status="upcoming")[0]
    response = client.get(f"/v1/events/{event['id']}/odds", params={"market": market})
    assert response.status_code == 200
    odds = response.json()
    assert odds["market"] == market
    assert odds["event"]["id"] == event["id"]
    assert odds["data_mode"] == "synthetic"
    assert datetime.fromisoformat(odds["as_of"]) == FROZEN_NOW
    assert len(odds["books"]) == 6
    statuses = {b["sportsbook"]["key"]: b for b in odds["books"]}
    assert set(statuses) == {"northline", "cardinal", "summit", "blueharbor", "kestrel", "oldmill"}

    usable = {
        key for key, book in statuses.items() if book["status"] == "open" and not book["is_stale"]
    }
    for book in odds["books"]:
        assert book["status"] in ("open", "suspended", "unavailable")
        if book["status"] == "unavailable":
            assert book["outcomes"] == [] and book["last_updated"] is None
        for outcome in book["outcomes"]:
            assert (outcome["line"] is None) == (market == "moneyline")
            if outcome["is_best"]:
                assert book["sportsbook"]["key"] in usable
    if statuses["oldmill"]["status"] != "unavailable":
        assert statuses["oldmill"]["is_stale"] is True

    # `best` agrees with the flags, and nothing usable on the consensus line beats it.
    assert odds["consensus"]["books_used"] <= len(usable)
    for best in odds["best"]:
        assert best["sportsbook_key"] in usable
        row = next(
            o
            for o in statuses[best["sportsbook_key"]]["outcomes"]
            if o["key"] == best["outcome_key"]
        )
        assert row["is_best"] is True
        assert row["price"] == best["price"]
        for key in usable:
            for outcome in statuses[key]["outcomes"]:
                if outcome["key"] == best["outcome_key"] and outcome["line"] == best["line"]:
                    assert outcome["price"]["decimal"] <= best["price"]["decimal"]
    total = sum(o["no_vig_probability"] for o in odds["consensus"]["outcomes"])
    assert total == pytest.approx(1.0, abs=1e-4)
    assert (odds["consensus"]["line"] is None) == (market == "moneyline")
    priced = {b["sportsbook"]["key"] for b in odds["books"] if b["outcomes"]}
    assert {h["sportsbook_key"] for h in odds["holds"]} == priced
    assert all(0 < h["hold"] < 0.15 for h in odds["holds"])


def test_odds_default_market_and_three_way(client: TestClient) -> None:
    event = events(client, league="soccer", status="upcoming")[0]
    odds = client.get(f"/v1/events/{event['id']}/odds").json()
    assert odds["market"] == "moneyline"
    assert [o["key"] for o in odds["consensus"]["outcomes"]] == ["home", "draw", "away"]
    assert {b["outcome_key"] for b in odds["best"]} == {"home", "draw", "away"}


def test_odds_market_validation(client: TestClient) -> None:
    soccer = events(client, league="soccer")[0]
    response = client.get(f"/v1/events/{soccer['id']}/odds", params={"market": "spread"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "market_not_available"
    assert response.json()["error"]["details"]["available_markets"] == ["moneyline", "total"]
    response = client.get(f"/v1/events/{soccer['id']}/odds", params={"market": "corners"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_live_event_uses_the_live_stale_threshold(client: TestClient) -> None:
    live = events(client, status="live")[0]
    odds = client.get(f"/v1/events/{live['id']}/odds").json()
    assert odds["stale_after_seconds"] == 120
    upcoming = events(client, status="upcoming")[0]
    assert client.get(f"/v1/events/{upcoming['id']}/odds").json()["stale_after_seconds"] == 900


def test_final_event_has_no_open_markets(client: TestClient) -> None:
    final = events(client, status="final")[0]
    odds = client.get(f"/v1/events/{final['id']}/odds").json()
    assert {b["status"] for b in odds["books"]} == {"unavailable"}
    assert odds["best"] == []
    assert odds["consensus"]["books_used"] == 0


def test_line_history(client: TestClient) -> None:
    event = events(client, league="nba", status="upcoming")[0]
    history = client.get(
        f"/v1/events/{event['id']}/line-history", params={"market": "total"}
    ).json()
    assert history["market"] == "total"
    assert history["series"]
    for series in history["series"]:
        assert set(series) == {"sportsbook", "outcome_key", "outcome_name", "points"}
        assert series["outcome_key"] in ("over", "under")
        assert len(series["points"]) >= 40
        stamps = [p["timestamp"] for p in series["points"]]
        assert stamps == sorted(stamps)
        point = series["points"][0]
        assert set(point) == {"timestamp", "line", "price"}
        assert point["line"] is not None
        assert set(point["price"]) == {"american", "decimal", "fractional", "implied_probability"}
    first = datetime.fromisoformat(history["series"][0]["points"][0]["timestamp"])
    assert 44 <= (FROZEN_NOW - first).total_seconds() / 3600 <= 48


def test_player_search_and_detail(client: TestClient) -> None:
    everyone = client.get("/v1/players").json()
    assert len(everyone) == 160
    assert [p["name"] for p in everyone] == sorted(p["name"] for p in everyone)
    nba = client.get("/v1/players", params={"league": "nba"}).json()
    assert len(nba) == 32
    target = nba[0]
    assert set(target) == {
        "id",
        "name",
        "league",
        "team",
        "position",
        "jersey_number",
        "prop_markets",
    }
    found = client.get("/v1/players", params={"q": target["name"].split()[0].lower()}).json()
    assert target["id"] in {p["id"] for p in found}
    assert client.get("/v1/players", params={"q": "zzzz"}).json() == []
    detail = client.get(f"/v1/players/{target['id']}").json()
    assert detail["next_event"]["status"] in ("live", "upcoming")
    assert detail["opponent"]["id"] != target["team"]["id"]
    missing = client.get("/v1/players/plr_nobody")
    assert missing.status_code == 404
    assert client.get("/v1/players/plr_nobody/props").status_code == 404


def test_player_props(client: TestClient) -> None:
    player = client.get("/v1/players", params={"league": "nba"}).json()[3]
    response = client.get(f"/v1/players/{player['id']}/props", params={"market": "rebounds"})
    assert response.status_code == 200
    props = response.json()
    assert props["market"] == "rebounds"
    assert props["available_markets"] == ["points", "rebounds", "assists", "threes"]
    assert (props["window"], props["split"]) == ("10", "all")
    assert props["opponent"] is not None and props["next_event"] is not None
    assert len(props["offers"]) == 6
    for offer in props["offers"]:
        assert set(offer) == {
            "sportsbook", "status", "line", "over", "under", "last_updated", "is_stale",
            "is_best_over", "is_best_under",
        }  # fmt: skip
        if offer["is_best_over"] or offer["is_best_under"]:
            assert offer["status"] == "open" and not offer["is_stale"]
            assert offer["line"] == props["consensus_line"]
    assert len(props["game_log"]) == 10
    line = props["hit_rate"]["line"]
    assert line == props["consensus_line"]
    for entry in props["game_log"]:
        assert set(entry) == {"event_id", "date", "opponent", "is_home", "value", "result"}
        expected = (
            "push" if entry["value"] == line else "over" if entry["value"] > line else "under"
        )
        assert entry["result"] == expected
    rate = props["hit_rate"]
    overs = sum(1 for e in props["game_log"] if e["result"] == "over")
    pushes = sum(1 for e in props["game_log"] if e["result"] == "push")
    assert rate["over_count"] == overs
    assert rate["pushes"] == pushes
    assert rate["sample_size"] == 10 - pushes
    assert rate["rate"] == pytest.approx(overs / (10 - pushes), abs=1e-4)
    assert rate["ci_low"] <= rate["rate"] <= rate["ci_high"]
    values = [e["value"] for e in props["game_log"]]
    assert props["averages"]["window"] == pytest.approx(sum(values) / 10, abs=0.01)
    assert set(props["averages"]) == {"window", "season", "home", "away", "vs_opponent"}
    assert "not a prediction" in props["caveat"]
    assert "historical" in props["caveat"].lower()


def test_player_props_windows_and_splits(client: TestClient) -> None:
    player = client.get("/v1/players", params={"league": "nba"}).json()[0]
    base = f"/v1/players/{player['id']}/props"
    default = client.get(base).json()
    assert default["market"] == player["prop_markets"][0]
    assert len(client.get(base, params={"window": "5"}).json()["game_log"]) == 5
    assert len(client.get(base, params={"window": "20"}).json()["game_log"]) == 20
    season = client.get(base, params={"window": "season"}).json()
    assert len(season["game_log"]) >= 25
    assert season["averages"]["window"] == season["averages"]["season"]
    home = client.get(base, params={"split": "home", "window": "season"}).json()
    assert home["game_log"] and all(e["is_home"] for e in home["game_log"])
    assert home["averages"]["window"] == home["averages"]["home"]
    away = client.get(base, params={"split": "away", "window": "5"}).json()
    assert len(away["game_log"]) == 5 and not any(e["is_home"] for e in away["game_log"])
    versus = client.get(base, params={"split": "vs_opponent", "window": "season"}).json()
    assert all(e["opponent"]["id"] == versus["opponent"]["id"] for e in versus["game_log"])
    if versus["game_log"]:
        assert versus["averages"]["vs_opponent"] == versus["averages"]["window"]
    else:
        assert versus["hit_rate"]["rate"] is None and versus["hit_rate"]["sample_size"] == 0


def test_player_props_validation(client: TestClient) -> None:
    player = client.get("/v1/players", params={"league": "mlb"}).json()[0]
    base = f"/v1/players/{player['id']}/props"
    response = client.get(base, params={"market": "touchdowns"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "market_not_available"
    assert client.get(base, params={"window": "7"}).status_code == 422
    assert client.get(base, params={"split": "night"}).status_code == 422


def test_props_board(client: TestClient) -> None:
    rows = client.get("/v1/props", params={"league": "nba", "market": "points"}).json()
    assert len(rows) == 32
    for row in rows:
        assert set(row) == {
            "player", "event", "market", "consensus_line", "best_over", "best_under",
            "l10_hit_rate", "l10_over_count", "l10_sample",
        }  # fmt: skip
        assert row["market"] == "points"
        assert row["player"]["league"] == "nba"
        assert row["event"]["status"] in ("live", "upcoming")
        if row["consensus_line"] is None:
            assert row["best_over"] is None and row["l10_hit_rate"] is None
        else:
            assert 0 <= row["l10_sample"] <= 10
            if row["l10_sample"]:
                assert row["l10_hit_rate"] == pytest.approx(
                    row["l10_over_count"] / row["l10_sample"], abs=1e-4
                )
        for side in ("best_over", "best_under"):
            if row[side]:
                assert row[side]["sportsbook"]["key"] != "oldmill"
    everything = client.get("/v1/props").json()
    assert len(everything) > 300
    assert {r["player"]["league"] for r in everything} == {"nba", "nfl", "mlb", "nhl", "soccer"}
    assert client.get("/v1/props", params={"market": "nothing"}).json() == []
    assert client.get("/v1/props", params={"league": "xfl"}).status_code == 422


def test_props_board_matches_player_props(client: TestClient) -> None:
    row = next(
        r for r in client.get("/v1/props", params={"league": "nhl"}).json() if r["consensus_line"]
    )
    props = client.get(
        f"/v1/players/{row['player']['id']}/props", params={"market": row["market"]}
    ).json()
    assert props["consensus_line"] == row["consensus_line"]
    assert props["hit_rate"]["over_count"] == row["l10_over_count"]
    assert props["hit_rate"]["sample_size"] == row["l10_sample"]
