"""Build the compact replay dataset read by ``ReplayProvider`` from raw nflverse files.

Input (both published by nflverse under CC BY 4.0, see ``data/external/LICENSES.md``):

* ``schedules_games.csv``: one row per NFL game with the final score and one consensus
  closing line (no sportsbook is named in the source);
* ``stats_player_week_<season>.parquet``: one row per player per game.

Output is one JSON file. It contains REAL team and player names, so it is written under
``data/external/`` (git-ignored) and must never be committed. Reading Parquet needs
``pyarrow``, which is not a runtime dependency: ``uv pip install -e ".[replay]"``.

Usage, from ``services/api``::

    python scripts/build_replay_data.py \
        --schedule ../../data/external/nflverse/schedules_games.csv \
        --stats ../../data/external/nflverse/stats_player_week_2024.parquet \
        --season 2024 --out ../../data/external/replay/nfl_2024.json
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

FORMAT_VERSION = 1
ATTRIBUTION = (
    "Game results, closing lines and player statistics: nflverse (nflverse-data), "
    "CC BY 4.0, https://creativecommons.org/licenses/by/4.0/. Reformatted by OddVex; "
    "sportsbook names and per-book prices are simulated and are not part of that data."
)
_EASTERN = ZoneInfo("America/New_York")

#: Abbreviations as used by nflverse for the 2024 season.
NFL_TEAMS: dict[str, tuple[str, str]] = {
    "ARI": ("Arizona", "Cardinals"),
    "ATL": ("Atlanta", "Falcons"),
    "BAL": ("Baltimore", "Ravens"),
    "BUF": ("Buffalo", "Bills"),
    "CAR": ("Carolina", "Panthers"),
    "CHI": ("Chicago", "Bears"),
    "CIN": ("Cincinnati", "Bengals"),
    "CLE": ("Cleveland", "Browns"),
    "DAL": ("Dallas", "Cowboys"),
    "DEN": ("Denver", "Broncos"),
    "DET": ("Detroit", "Lions"),
    "GB": ("Green Bay", "Packers"),
    "HOU": ("Houston", "Texans"),
    "IND": ("Indianapolis", "Colts"),
    "JAX": ("Jacksonville", "Jaguars"),
    "KC": ("Kansas City", "Chiefs"),
    "LA": ("Los Angeles", "Rams"),
    "LAC": ("Los Angeles", "Chargers"),
    "LV": ("Las Vegas", "Raiders"),
    "MIA": ("Miami", "Dolphins"),
    "MIN": ("Minnesota", "Vikings"),
    "NE": ("New England", "Patriots"),
    "NO": ("New Orleans", "Saints"),
    "NYG": ("New York", "Giants"),
    "NYJ": ("New York", "Jets"),
    "PHI": ("Philadelphia", "Eagles"),
    "PIT": ("Pittsburgh", "Steelers"),
    "SEA": ("Seattle", "Seahawks"),
    "SF": ("San Francisco", "49ers"),
    "TB": ("Tampa Bay", "Buccaneers"),
    "TEN": ("Tennessee", "Titans"),
    "WAS": ("Washington", "Commanders"),
}

#: position group -> (primary market, minimum per-game average to be listed at all).
_PRIMARY: dict[str, tuple[str, float]] = {
    "QB": ("passing_yards", 120.0),
    "RB": ("rushing_yards", 25.0),
    "WR": ("receiving_yards", 25.0),
    "TE": ("receiving_yards", 20.0),
}
#: Extra markets a listed player gets when their per-game average reaches the minimum.
_SECONDARY: dict[str, tuple[tuple[str, float], ...]] = {
    "QB": (("rushing_yards", 15.0),),
    "RB": (("receptions", 1.5), ("receiving_yards", 12.0)),
    "WR": (("receptions", 2.0),),
    "TE": (("receptions", 2.0),),
}
MIN_GAMES = 6


def _int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(float(value))


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _kickoff(gameday: str, gametime: str) -> str:
    """nflverse stores kickoff as US Eastern wall time; the dataset stores UTC."""
    local = datetime.strptime(f"{gameday} {gametime or '13:00'}", "%Y-%m-%d %H:%M")
    return local.replace(tzinfo=_EASTERN).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_games(rows: Iterable[Mapping[str, Any]], season: int) -> list[dict[str, Any]]:
    """Completed games of one season. ``spread_line`` is positive when the home side is favoured."""
    games: list[dict[str, Any]] = []
    for row in rows:
        if _int(row.get("season")) != season:
            continue
        home_score, away_score = _int(row.get("home_score")), _int(row.get("away_score"))
        if home_score is None or away_score is None:
            continue
        home, away = str(row["home_team"]), str(row["away_team"])
        if home not in NFL_TEAMS or away not in NFL_TEAMS:
            raise ValueError(f"unknown team abbreviation in game {row['game_id']}")
        spread = _float(row.get("spread_line"))
        games.append(
            {
                "id": str(row["game_id"]),
                "week": _int(row.get("week")),
                "game_type": str(row.get("game_type") or "REG"),
                "kickoff": _kickoff(str(row["gameday"]), str(row.get("gametime") or "")),
                "home": home,
                "away": away,
                "home_score": home_score,
                "away_score": away_score,
                "home_moneyline": _int(row.get("home_moneyline")),
                "away_moneyline": _int(row.get("away_moneyline")),
                "home_spread": None if spread is None else -spread,
                "home_spread_odds": _int(row.get("home_spread_odds")),
                "away_spread_odds": _int(row.get("away_spread_odds")),
                "total": _float(row.get("total_line")),
                "over_odds": _int(row.get("over_odds")),
                "under_odds": _int(row.get("under_odds")),
            }
        )
    games.sort(key=lambda g: (g["kickoff"], g["id"]))
    return games


def build_players(
    rows: Iterable[Mapping[str, Any]], game_ids: set[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Players with enough volume to carry a prop market, and their per-game lines."""
    by_player: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("game_id") in game_ids and row.get("position_group") in _PRIMARY:
            by_player[str(row["player_id"])].append(row)

    players: list[dict[str, Any]] = []
    stats: list[dict[str, Any]] = []
    for player_id, lines in sorted(by_player.items()):
        if len(lines) < MIN_GAMES:
            continue
        group = str(lines[0]["position_group"])

        def average(market: str, lines: list[Mapping[str, Any]] = lines) -> float:
            return sum(float(line.get(market) or 0) for line in lines) / len(lines)

        primary, minimum = _PRIMARY[group]
        if average(primary) < minimum:
            continue
        markets = [primary] + [m for m, floor in _SECONDARY[group] if average(m) >= floor]
        latest = max(lines, key=lambda line: str(line["game_id"]))
        players.append(
            {
                "id": player_id,
                "name": str(latest["player_display_name"]),
                "position": str(latest.get("position") or group),
                "markets": markets,
            }
        )
        for line in lines:
            stats.append(
                {
                    "player": player_id,
                    "game": str(line["game_id"]),
                    "team": str(line["team"]),
                    "values": {m: float(line.get(m) or 0) for m in markets},
                }
            )
    return players, stats


def build_dataset(
    schedule_rows: Iterable[Mapping[str, Any]],
    stat_rows: Iterable[Mapping[str, Any]],
    season: int,
) -> dict[str, Any]:
    games = build_games(schedule_rows, season)
    if not games:
        raise ValueError(f"no completed games found for season {season}")
    players, stats = build_players(stat_rows, {g["id"] for g in games})
    used = sorted({g["home"] for g in games} | {g["away"] for g in games})
    return {
        "format_version": FORMAT_VERSION,
        "league": {"key": "nfl", "name": f"NFL {season} season (replay)", "sport": "football"},
        "season": season,
        "attribution": ATTRIBUTION,
        "teams": [
            {"abbr": abbr, "city": NFL_TEAMS[abbr][0], "nickname": NFL_TEAMS[abbr][1]}
            for abbr in used
        ],
        "games": games,
        "players": players,
        "stats": stats,
    }


def _read_parquet(path: Path) -> list[dict[str, Any]]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - depends on the local environment
        raise SystemExit('pyarrow is required: uv pip install -e ".[replay]"') from exc
    columns = [
        "player_id",
        "player_display_name",
        "position",
        "position_group",
        "game_id",
        "team",
        "passing_yards",
        "rushing_yards",
        "receiving_yards",
        "receptions",
    ]
    rows: list[dict[str, Any]] = pq.read_table(path, columns=columns).to_pylist()
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--stats", type=Path, required=True)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    with args.schedule.open(newline="", encoding="utf-8") as handle:
        schedule_rows = list(csv.DictReader(handle))
    dataset = build_dataset(schedule_rows, _read_parquet(args.stats), args.season)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(dataset, separators=(",", ":")), encoding="utf-8")
    print(
        f"wrote {args.out}: {len(dataset['games'])} games, {len(dataset['players'])} players, "
        f"{len(dataset['stats'])} stat lines"
    )


if __name__ == "__main__":
    main()
