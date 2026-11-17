"""A small, entirely fictional replay dataset in the format of ``build_replay_data.py``."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

#: Kickoff of the first recorded week (a Sunday, 18:00 UTC).
FIRST_KICKOFF = datetime(2024, 9, 8, 18, 0, tzinfo=UTC)
SHIFT_DAYS = 728
WEEKS = 6
QB = "p-qb"  # plays every week for HCT
WR = "p-wr"  # traded: HCT for weeks 1-3, RVR from week 4
ROOKIE = "p-rookie"  # first appears in week 5


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def replay_dataset() -> dict[str, Any]:
    games: list[dict[str, Any]] = []
    stats: list[dict[str, Any]] = []
    for week in range(1, WEEKS + 1):
        kickoff = FIRST_KICKOFF + timedelta(weeks=week - 1)
        swap = week % 2 == 0
        pairs = [("HCT", "RVR"), ("MSA", "GLD")] if not swap else [("RVR", "HCT"), ("GLD", "MSA")]
        for slot, (home, away) in enumerate(pairs):
            game_id = f"2024_{week:02d}_{away}_{home}"
            games.append(
                {
                    "id": game_id,
                    "week": week,
                    "game_type": "REG",
                    "kickoff": _iso(kickoff + timedelta(hours=3 * slot)),
                    "home": home,
                    "away": away,
                    "home_score": 20 + week + slot,
                    "away_score": 17 + slot,
                    "home_moneyline": -150,
                    "away_moneyline": 130,
                    "home_spread": -3.0,
                    "home_spread_odds": -110,
                    "away_spread_odds": -110,
                    # The last week has no total, to exercise a missing market.
                    "total": None if week == WEEKS else 44.5,
                    "over_odds": None if week == WEEKS else -105,
                    "under_odds": None if week == WEEKS else -115,
                }
            )
        first = f"2024_{week:02d}_{pairs[0][1]}_{pairs[0][0]}"
        stats.append(
            {
                "player": QB,
                "game": first,
                "team": "HCT",
                "values": {"passing_yards": 200.0 + 10 * week, "rushing_yards": 10.0 + week},
            }
        )
        stats.append(
            {
                "player": WR,
                "game": first,
                "team": "HCT" if week <= 3 else "RVR",
                "values": {"receiving_yards": 50.0 + 5 * week, "receptions": float(3 + week % 3)},
            }
        )
        if week >= 5:
            stats.append(
                {
                    "player": ROOKIE,
                    "game": first,
                    "team": "RVR",
                    "values": {"rushing_yards": 40.0},
                }
            )
    return {
        "format_version": 1,
        "league": {"key": "nfl", "name": "Fictional League 2024 (replay)", "sport": "football"},
        "season": 2024,
        "attribution": "Test fixture: fictional teams and players.",
        "teams": [
            {"abbr": "HCT", "city": "Harbor City", "nickname": "Tides"},
            {"abbr": "RVR", "city": "Riverton", "nickname": "Rapids"},
            {"abbr": "MSA", "city": "Mesa Alta", "nickname": "Scorpions"},
            {"abbr": "GLD", "city": "Glendower", "nickname": "Stags"},
        ],
        "games": games,
        "players": [
            {
                "id": QB,
                "name": "Dax Varrow",
                "position": "QB",
                "markets": ["passing_yards", "rushing_yards"],
            },
            {
                "id": WR,
                "name": "Tobin Ashdown",
                "position": "WR",
                "markets": ["receiving_yards", "receptions"],
            },
            {
                "id": ROOKIE,
                "name": "Quill Rookwood",
                "position": "RB",
                "markets": ["rushing_yards"],
            },
            # No stat lines: must not be listed.
            {
                "id": "p-ghost",
                "name": "Idris Flintlock",
                "position": "TE",
                "markets": ["receptions"],
            },
        ],
        "stats": stats,
    }


def shifted(week: int, hours: float = 0.0) -> datetime:
    """Replay time of the first game of ``week``, plus ``hours``."""
    return (
        FIRST_KICKOFF
        + timedelta(weeks=week - 1)
        + timedelta(days=SHIFT_DAYS)
        + timedelta(hours=hours)
    )
