"""Contract tests: synthetic vendor-format fixtures -> canonical provider models."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from oddvex_api.providers.normalize import (
    ProviderContractError,
    normalize_event,
    normalize_game_log,
    normalize_odds_snapshot,
    parse_timestamp,
)

FIXTURES = Path(__file__).resolve().parents[3] / "data" / "fixtures"
FETCHED = datetime(2026, 1, 10, 18, 6, tzinfo=UTC)


def load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_fixture_files_are_labelled_synthetic() -> None:
    files = sorted(FIXTURES.glob("*.json"))
    assert len(files) >= 4
    for path in files:
        assert "SYNTHETIC" in json.loads(path.read_text(encoding="utf-8"))["_note"]
    assert "synthetic" in (FIXTURES / "README.md").read_text(encoding="utf-8").lower()


def test_events_normalize() -> None:
    scheduled, live, final = (
        normalize_event(raw, "fixture", FETCHED) for raw in load("events.sample.json")["events"]
    )
    assert scheduled.status == "upcoming"
    assert scheduled.league == "nba"  # vendor sends "NBA"
    assert scheduled.score is None
    assert scheduled.start_time == datetime(2026, 1, 11, 0, 0, tzinfo=UTC)  # -05:00 -> UTC
    assert scheduled.home_team_id == "team_nba_hct"
    assert scheduled.markets == ["moneyline", "spread", "total"]
    assert (scheduled.provider, scheduled.provider_id, scheduled.fetched_at) == (
        "fixture",
        "evt_nba_20260110_0",
        FETCHED,
    )

    assert live.status == "live"
    assert (live.score.home, live.score.away) == (2, 1)  # type: ignore[union-attr]
    assert live.period_text == "P2 11:42"

    assert final.status == "final"
    assert final.period_text == "Final"
    assert final.markets == ["moneyline", "total"]  # soccer has no spread


def test_odds_snapshots_normalize() -> None:
    snapshots = [
        normalize_odds_snapshot(raw, "fixture", FETCHED)
        for raw in load("odds_snapshots.sample.json")["snapshots"]
    ]
    moneyline, spread, off_board, three_way, total = snapshots

    assert (moneyline.market, moneyline.status, moneyline.sportsbook_id) == (
        "moneyline",
        "open",
        "northline",
    )
    assert [(o.key, o.price_american, o.line) for o in moneyline.outcomes] == [
        ("home", -150, None),
        ("away", 130, None),
    ]
    assert moneyline.last_updated == datetime(2026, 1, 10, 18, 5, 30, tzinfo=UTC)
    assert moneyline.provider_id == "evt_nba_20260110_0:moneyline:northline"

    assert (spread.market, spread.status, spread.sportsbook_id) == (
        "spread",
        "suspended",
        "cardinal",
    )
    assert [o.line for o in spread.outcomes] == [-3.5, 3.5]

    assert off_board.status == "unavailable"
    assert off_board.outcomes == []
    assert off_board.last_updated is None

    assert three_way.status == "closed"
    assert [o.key for o in three_way.outcomes] == ["home", "draw", "away"]

    assert [(o.key, o.line) for o in total.outcomes] == [("over", 224.5), ("under", 224.5)]


def test_game_log_normalizes_and_sorts_newest_first() -> None:
    entries = normalize_game_log(load("player_game_log.sample.json"), "fixture", FETCHED)
    assert [e.event_id for e in entries] == [
        "evt_nba_20260108_3",
        "evt_nba_20260106_0",
        "evt_nba_20260105_1",
    ]
    newest = entries[0]
    assert newest.player_id == "plr_nba_hct_1"
    assert newest.is_home is True
    assert newest.stats == {"points": 31.0, "rebounds": 6.0, "assists": 7.0, "threes": 5.0}
    assert entries[-1].is_home is False
    assert newest.provider_id == "plr_nba_hct_1:evt_nba_20260108_3"


@pytest.mark.parametrize(
    "case", load("invalid_payloads.sample.json")["events"], ids=lambda case: case["reason"]
)
def test_invalid_events_are_rejected(case: dict[str, Any]) -> None:
    with pytest.raises(ProviderContractError):
        normalize_event(case["payload"], "fixture", FETCHED)


@pytest.mark.parametrize(
    "case", load("invalid_payloads.sample.json")["snapshots"], ids=lambda case: case["reason"]
)
def test_invalid_snapshots_are_rejected(case: dict[str, Any]) -> None:
    with pytest.raises(ProviderContractError):
        normalize_odds_snapshot(case["payload"], "fixture", FETCHED)


def test_missing_fields_and_bad_values_are_rejected() -> None:
    with pytest.raises(ProviderContractError, match="eventId"):
        normalize_event({}, "fixture", FETCHED)
    with pytest.raises(ProviderContractError):
        parse_timestamp(12345)
    with pytest.raises(ProviderContractError):
        parse_timestamp("not a date")
    with pytest.raises(ProviderContractError, match="venue"):
        normalize_game_log(
            {
                "playerId": "p",
                "games": [
                    {
                        "eventId": "e",
                        "date": "2026-01-01T00:00:00Z",
                        "opp": "t",
                        "venue": "N",
                        "statLine": {},
                    }
                ],
            },
            "fixture",
            FETCHED,
        )
    with pytest.raises(ProviderContractError, match="stat key"):
        normalize_game_log(
            {
                "playerId": "p",
                "games": [
                    {
                        "eventId": "e",
                        "date": "2026-01-01T00:00:00Z",
                        "opp": "t",
                        "venue": "H",
                        "statLine": {"XYZ": 1},
                    }
                ],
            },
            "fixture",
            FETCHED,
        )
