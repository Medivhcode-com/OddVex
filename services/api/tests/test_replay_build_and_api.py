"""Replay mode end to end: dataset builder, configuration guard and API labelling."""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from oddvex_api.config import Settings
from oddvex_api.main import build_provider
from oddvex_api.providers import ReplayProvider, SyntheticProvider

from .conftest import AppFactory
from .replay_support import SHIFT_DAYS, replay_dataset, shifted

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_replay_data.py"
_spec = importlib.util.spec_from_file_location("build_replay_data", _SCRIPT)
assert _spec and _spec.loader
builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(builder)


# ------------------------------------------------------------------ builder
def _schedule_row(**overrides: Any) -> dict[str, Any]:
    row = {
        "game_id": "2024_01_BAL_KC",
        "season": "2024",
        "game_type": "REG",
        "week": "1",
        "gameday": "2024-09-05",
        "gametime": "20:20",
        "away_team": "BAL",
        "home_team": "KC",
        "away_score": "20",
        "home_score": "27",
        "away_moneyline": "124",
        "home_moneyline": "-148",
        "spread_line": "3",
        "away_spread_odds": "-110",
        "home_spread_odds": "-110",
        "total_line": "46.5",
        "under_odds": "-110",
        "over_odds": "-110",
    }
    row.update(overrides)
    return row


def _stat_rows(player_id: str, group: str, games: int, **values: float) -> list[dict[str, Any]]:
    return [
        {
            "player_id": player_id,
            "player_display_name": f"Fictional {player_id}",
            "position": group,
            "position_group": group,
            "game_id": "2024_01_BAL_KC",
            "team": "KC",
            **values,
        }
        for _ in range(games)
    ]


def test_build_games_converts_time_zone_and_spread_sign() -> None:
    rows = [
        _schedule_row(),
        _schedule_row(game_id="2023_01_DET_KC", season="2023"),
        _schedule_row(game_id="2024_02_CIN_KC", home_score="", away_score=""),  # not played
        _schedule_row(
            game_id="2024_03_KC_ATL", gameday="2024-12-01", gametime="13:00", spread_line=""
        ),
    ]
    first, second = builder.build_games(rows, 2024)
    # 20:20 US Eastern in September is 00:20 UTC the next day (daylight time).
    assert first["kickoff"] == "2024-09-06T00:20:00Z"
    assert second["kickoff"] == "2024-12-01T18:00:00Z"  # standard time
    # nflverse: positive spread_line = home favoured. The dataset stores the home line.
    assert (first["home_spread"], first["home_moneyline"]) == (-3.0, -148)
    assert second["home_spread"] is None
    assert (first["home_score"], first["away_score"]) == (27, 20)


def test_build_games_rejects_an_unknown_team() -> None:
    with pytest.raises(ValueError, match="unknown team"):
        builder.build_games([_schedule_row(home_team="XXX")], 2024)


def test_build_players_keeps_only_players_with_volume() -> None:
    rows = (
        _stat_rows("qb", "QB", 8, passing_yards=250, rushing_yards=20)
        + _stat_rows("backup", "QB", 8, passing_yards=30)
        + _stat_rows("short", "WR", 3, receiving_yards=90, receptions=6)
        + _stat_rows("wr", "WR", 6, receiving_yards=60, receptions=1)
        + _stat_rows("kicker", "K", 10)
        + [{**_stat_rows("qb", "QB", 1, passing_yards=999)[0], "game_id": "2023_01_DET_KC"}]
    )
    players, stats = builder.build_players(rows, {"2024_01_BAL_KC"})
    assert [(p["id"], p["markets"]) for p in players] == [
        ("qb", ["passing_yards", "rushing_yards"]),
        ("wr", ["receiving_yards"]),
    ]
    assert len(stats) == 14
    assert stats[0]["values"] == {"passing_yards": 250.0, "rushing_yards": 20.0}


def test_build_dataset_is_readable_by_the_provider() -> None:
    dataset = builder.build_dataset(
        [_schedule_row()], _stat_rows("qb", "QB", 6, passing_yards=250), 2024
    )
    assert dataset["format_version"] == 1
    assert "CC BY 4.0" in dataset["attribution"]
    assert [t["abbr"] for t in dataset["teams"]] == ["BAL", "KC"]
    provider = ReplayProvider(json.loads(json.dumps(dataset)))
    assert len(provider.list_teams()) == 2
    with pytest.raises(ValueError, match="no completed games"):
        builder.build_dataset([_schedule_row()], [], 1990)


# ------------------------------------------------------------ configuration
def test_replay_needs_a_dataset_path_and_is_refused_in_production(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="ODDVEX_REPLAY_DATA_PATH"):
        Settings(data_provider="replay").validate_for_startup()
    with pytest.raises(RuntimeError, match="internal previews only"):
        Settings(
            env="production",
            jwt_secret="x" * 40,
            data_provider="replay",
            replay_data_path="somewhere.json",
        ).validate_for_startup()

    path = tmp_path / "replay.json"
    path.write_text(json.dumps(replay_dataset()), encoding="utf-8")
    provider = build_provider(Settings(data_provider="replay", replay_data_path=str(path)))
    assert isinstance(provider, ReplayProvider)
    assert isinstance(build_provider(Settings()), SyntheticProvider)


# ---------------------------------------------------------------------- API
@pytest.fixture
def client(make_app: AppFactory) -> Iterator[TestClient]:
    provider = ReplayProvider(replay_dataset(), shift_days=SHIFT_DAYS, clock=lambda: shifted(4, -2))
    with TestClient(make_app(provider=provider)) as test_client:
        yield test_client


def test_meta_and_health_report_replay_with_attribution(client: TestClient) -> None:
    meta = client.get("/v1/meta").json()
    assert (meta["data_mode"], meta["provider"]) == ("replay", "replay")
    assert "simulated" in meta["notice"]
    assert meta["attribution"] == "Test fixture: fictional teams and players."
    assert client.get("/health").json()["data_mode"] == "replay"


def test_synthetic_meta_has_no_attribution(make_app: AppFactory) -> None:
    with TestClient(make_app()) as synthetic:
        meta = synthetic.get("/v1/meta").json()
    assert (meta["data_mode"], meta["attribution"]) == ("synthetic", None)
    assert "synthetic" in meta["notice"]


def test_board_routes_work_and_carry_the_replay_label(client: TestClient) -> None:
    events = client.get("/v1/events", params={"league": "nfl"})
    assert events.status_code == 200, events.text
    body = events.json()
    items = body["items"] if isinstance(body, dict) else body
    assert [e["status"] for e in items] == ["upcoming"] * 4
    event_id = items[0]["id"]

    detail = client.get(f"/v1/events/{event_id}").json()
    assert detail["data_mode"] == "replay"
    assert {p["name"] for p in detail["players"]} >= {"Dax Varrow", "Tobin Ashdown"}

    odds = client.get(f"/v1/events/{event_id}/odds", params={"market": "spread"})
    assert odds.status_code == 200, odds.text
    assert odds.json()["data_mode"] == "replay"
    history = client.get(f"/v1/events/{event_id}/line-history", params={"market": "moneyline"})
    assert history.status_code == 200, history.text

    props = client.get("/v1/players/plr_nfl_pqb/props", params={"market": "passing_yards"})
    assert props.status_code == 200, props.text
    assert props.json()["data_mode"] == "replay"
    board = client.get("/v1/props", params={"league": "nfl"})
    assert board.status_code == 200, board.text
    rows = board.json()["items"] if isinstance(board.json(), dict) else board.json()
    # The rookie has no earlier games, so no book lists him and he is not on the board.
    assert {row["player"]["name"] for row in rows} == {"Dax Varrow", "Tobin Ashdown"}
    assert all(row["consensus_line"] is not None for row in rows)
    assert client.get("/v1/value", params={"league": "nfl"}).status_code == 200


def test_assistant_says_replay_not_synthetic(client: TestClient) -> None:
    reply = client.post("/v1/assistant/query", json={"message": "help"})
    assert reply.status_code == 200, reply.text
    body = reply.json()
    assert "replay of past results" in body["disclaimer"]
    assert "synthetic" not in body["disclaimer"]
    assert "replay of past results" in body["answer"]
