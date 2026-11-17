"""Replay of one completed season, shifted in time so it plays out "now".

What is real and what is simulated is the whole point of this provider:

* REAL (read from the dataset file): teams, players, the schedule, final scores, the
  player statistics of every game, and one consensus closing line per game.
* SIMULATED: the sportsbooks (the same fictional books as the synthetic provider), each
  book's price (the closing line plus a margin and small noise), the price movement before
  kickoff, and every player prop line (the player's own trailing average at that point of
  the season). No prop line or per-book price was ever offered by a real sportsbook.

Every game is moved forward by a whole number of weeks (``shift_days``), so weekdays
line up and the season unfolds against the real clock. The provider never reveals a
result or a statistic before the shifted game has ended.

In-play data does not exist in the source, so a game in progress has no score and no
open prices.
"""

from __future__ import annotations

import hashlib
import json
import math
from bisect import bisect_right
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from statistics import NormalDist, pstdev
from typing import Any

from .base import (
    Event,
    GameLogEntry,
    League,
    LinePoint,
    LineSeries,
    OddsOutcome,
    OddsSnapshot,
    Player,
    PropOffer,
    ProviderHealth,
    Score,
    Sportsbook,
    Team,
)
from .synthetic import _BOOKS, _american_from_implied, _Book, _half_line

PROVIDER_NAME = "replay"
FORMAT_VERSION = 1
DEFAULT_SHIFT_DAYS = 728  # 104 weeks: weekdays line up with the recorded season
GAME_HOURS = 3.25
WINDOW_DAYS_BACK = 4
WINDOW_DAYS_AHEAD = 7
NEXT_EVENT_DAYS = 10
HISTORY_HOURS = 48
GAME_LOG_GAMES = 40
PROP_LOOKBACK_GAMES = 6
PROP_MIN_PRIOR_GAMES = 2
_NORMAL = NormalDist()

REPLAY_NOTICE = (
    "Replay of past games. Teams, players, schedules, final scores, player statistics and "
    "the closing line of each game are real historical data, moved forward in time. The "
    "sportsbooks are fictional, and their prices, the price movement and every player prop "
    "line are simulated. Nothing shown is a live price or a current game."
)

#: Fair pair: (outcome key, display name, line, no-vig probability).
type _Fair = list[tuple[str, str, float | None, float]]


class ReplayDataError(ValueError):
    """The replay dataset file is missing, unreadable or malformed."""


@dataclass(frozen=True)
class _Game:
    id: str
    source_id: str
    home: str
    away: str
    start: datetime
    end: datetime
    home_score: int
    away_score: int
    closing: dict[str, _Fair]
    markets: list[str]


@dataclass
class _PlayerData:
    player: Player
    #: (shifted kickoff, game id, team id, stats), oldest first.
    lines: list[tuple[datetime, str, str, dict[str, float]]] = field(default_factory=list)


def _implied(american: int) -> float:
    return -american / (-american + 100) if american < 0 else 100 / (american + 100)


def _no_vig_pair(first: Any, second: Any) -> tuple[float, float] | None:
    if not isinstance(first, int) or not isinstance(second, int) or 0 in (first, second):
        return None
    a, b = _implied(first), _implied(second)
    return a / (a + b), b / (a + b)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _slug(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum() or ch == "_")


def load_replay_dataset(path: str | Path) -> dict[str, Any]:
    """Read and minimally validate a dataset written by ``scripts/build_replay_data.py``."""
    file = Path(path)
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReplayDataError(
            f"replay dataset not found at {file}. Build it with "
            "services/api/scripts/build_replay_data.py (see data/external/README.md)."
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ReplayDataError(f"replay dataset at {file} could not be read: {exc}") from exc
    if not isinstance(data, dict) or data.get("format_version") != FORMAT_VERSION:
        raise ReplayDataError(
            f"replay dataset at {file} has an unsupported format_version "
            f"(expected {FORMAT_VERSION})"
        )
    for key in ("league", "teams", "games", "players", "stats"):
        if key not in data:
            raise ReplayDataError(f"replay dataset at {file} is missing {key!r}")
    return data


class ReplayProvider:
    """Time-shifted historical implementation of :class:`SportsDataProvider`."""

    name = PROVIDER_NAME
    data_mode = "replay"
    notice = REPLAY_NOTICE

    def __init__(
        self,
        dataset: dict[str, Any],
        shift_days: int = DEFAULT_SHIFT_DAYS,
        clock: Callable[[], datetime] | None = None,
        seed: int = 20260101,
    ) -> None:
        if shift_days % 7:
            raise ReplayDataError("replay shift must be a whole number of weeks")
        self.seed = seed
        self.shift = timedelta(days=shift_days)
        self._clock = clock or _utc_now
        self.attribution: str | None = dataset.get("attribution")
        try:
            self._build(dataset)
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, ReplayDataError):
                raise
            raise ReplayDataError(f"replay dataset is malformed: {exc!r}") from exc

    # ------------------------------------------------------------------ build
    def _build(self, dataset: dict[str, Any]) -> None:
        league = dataset["league"]
        self._league_key = str(league["key"])
        self._league_name = str(league["name"])
        self._sport = str(league["sport"])
        key = self._league_key
        self._loaded_at = datetime(2026, 1, 1, tzinfo=UTC)

        self._teams: dict[str, Team] = {}
        team_ids: dict[str, str] = {}
        for row in dataset["teams"]:
            abbr = str(row["abbr"])
            team_id = f"team_{key}_{_slug(abbr)}"
            team_ids[abbr] = team_id
            self._teams[team_id] = Team(
                id=team_id,
                league=key,
                name=f"{row['city']} {row['nickname']}",
                city=str(row["city"]),
                nickname=str(row["nickname"]),
                abbreviation=abbr,
                **self._prov(team_id, self._loaded_at),
            )

        self._games: dict[str, _Game] = {}
        by_source: dict[str, _Game] = {}
        self._team_games: dict[str, list[_Game]] = {team_id: [] for team_id in self._teams}
        for row in dataset["games"]:
            source_id = str(row["id"])
            home, away = team_ids[str(row["home"])], team_ids[str(row["away"])]
            start = datetime.fromisoformat(str(row["kickoff"]).replace("Z", "+00:00")) + self.shift
            closing = self._closing(row, self._teams[home].name, self._teams[away].name)
            game = _Game(
                id=f"evt_{key}_{_slug(source_id)}",
                source_id=source_id,
                home=home,
                away=away,
                start=start,
                end=start + timedelta(hours=GAME_HOURS),
                home_score=int(row["home_score"]),
                away_score=int(row["away_score"]),
                closing=closing,
                markets=[m for m in ("moneyline", "spread", "total") if m in closing],
            )
            self._games[game.id] = game
            by_source[source_id] = game
            self._team_games[home].append(game)
            self._team_games[away].append(game)
        self._ordered = sorted(self._games.values(), key=lambda g: (g.start, g.id))
        for games in self._team_games.values():
            games.sort(key=lambda g: g.start)

        self._players: dict[str, _PlayerData] = {}
        by_source_player: dict[str, _PlayerData] = {}
        prop_markets: list[str] = []
        for row in dataset["players"]:
            player_id = f"plr_{key}_{_slug(str(row['id']))}"
            markets = [str(m) for m in row["markets"]]
            prop_markets.extend(m for m in markets if m not in prop_markets)
            data = _PlayerData(
                Player(
                    id=player_id,
                    league=key,
                    team_id="",
                    name=str(row["name"]),
                    position=str(row["position"]),
                    jersey_number=int(row.get("jersey") or 0),
                    prop_markets=markets,
                    **self._prov(player_id, self._loaded_at),
                )
            )
            self._players[player_id] = data
            by_source_player[str(row["id"])] = data
        for row in dataset["stats"]:
            owner = by_source_player.get(str(row["player"]))
            played = by_source.get(str(row["game"]))
            if owner is None or played is None:
                continue
            owner.lines.append(
                (
                    played.start,
                    played.id,
                    team_ids[str(row["team"])],
                    {str(m): float(v) for m, v in row["values"].items()},
                )
            )
        for data in self._players.values():
            data.lines.sort(key=lambda line: line[0])
        self._players = {pid: data for pid, data in self._players.items() if data.lines}
        self._prop_markets = prop_markets
        self._markets = [
            m
            for m in ("moneyline", "spread", "total")
            if any(m in g.markets for g in self._ordered)
        ]

    @staticmethod
    def _closing(row: dict[str, Any], home_name: str, away_name: str) -> dict[str, _Fair]:
        closing: dict[str, _Fair] = {}
        moneyline = _no_vig_pair(row.get("home_moneyline"), row.get("away_moneyline"))
        if moneyline:
            closing["moneyline"] = [
                ("home", home_name, None, moneyline[0]),
                ("away", away_name, None, moneyline[1]),
            ]
        spread = _no_vig_pair(row.get("home_spread_odds"), row.get("away_spread_odds"))
        if spread and row.get("home_spread") is not None:
            line = float(row["home_spread"])
            closing["spread"] = [
                ("home", home_name, line, spread[0]),
                ("away", away_name, -line, spread[1]),
            ]
        total = _no_vig_pair(row.get("over_odds"), row.get("under_odds"))
        if total and row.get("total") is not None:
            line = float(row["total"])
            closing["total"] = [
                ("over", "Over", line, total[0]),
                ("under", "Under", line, total[1]),
            ]
        return closing

    # ------------------------------------------------------------------ utils
    def now(self) -> datetime:
        now = self._clock()
        return now if now.tzinfo else now.replace(tzinfo=UTC)

    def _u(self, *keys: object) -> float:
        text = "|".join(str(k) for k in (self.seed, *keys))
        digest = hashlib.blake2b(text.encode(), digest_size=8).digest()
        return int.from_bytes(digest, "big") / 2**64

    def _z(self, *keys: object) -> float:
        return _NORMAL.inv_cdf(min(max(self._u(*keys), 1e-9), 1 - 1e-9))

    def _prov(self, record_id: str, fetched_at: datetime) -> dict[str, Any]:
        return {"provider": self.name, "provider_id": f"rpl:{record_id}", "fetched_at": fetched_at}

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            data_mode=self.data_mode,
            status="ok",
            checked_at=self.now(),
            detail=(
                f"{self._league_name}: {len(self._ordered)} games, {len(self._players)} players, "
                f"shifted {self.shift.days} days. Sportsbook prices and prop lines are simulated."
            ),
        )

    # ----------------------------------------------------------- static data
    def list_leagues(self) -> list[League]:
        return [
            League(
                id=f"league_{self._league_key}",
                key=self._league_key,
                name=self._league_name,
                sport=self._sport,
                has_draw=False,
                markets=self._markets,
                prop_markets=self._prop_markets,
                **self._prov(f"league_{self._league_key}", self.now()),
            )
        ]

    def list_sportsbooks(self) -> list[Sportsbook]:
        now = self.now()
        return [
            Sportsbook(id=book.key, key=book.key, name=book.name, **self._prov(book.key, now))
            for book in _BOOKS
        ]

    def list_teams(self, league: str | None = None) -> list[Team]:
        if league and league != self._league_key:
            return []
        return list(self._teams.values())

    def get_team(self, team_id: str) -> Team | None:
        return self._teams.get(team_id)

    def _player_at(self, data: _PlayerData, now: datetime) -> Player:
        """The player on the team of their latest game that has kicked off (else their first)."""
        index = bisect_right([line[0] for line in data.lines], now)
        team_id = data.lines[max(index - 1, 0)][2]
        return data.player.model_copy(update={"team_id": team_id})

    def list_players(
        self, league: str | None = None, team_id: str | None = None, query: str | None = None
    ) -> list[Player]:
        if league and league != self._league_key:
            return []
        now = self.now()
        needle = query.strip().lower() if query else None
        result: list[Player] = []
        for data in self._players.values():
            player = self._player_at(data, now)
            if team_id and player.team_id != team_id:
                continue
            if needle and needle not in player.name.lower():
                continue
            result.append(player)
        return result

    def get_player(self, player_id: str) -> Player | None:
        data = self._players.get(player_id)
        return self._player_at(data, self.now()) if data else None

    # ----------------------------------------------------------------- events
    @staticmethod
    def _status(game: _Game, now: datetime) -> str:
        return "upcoming" if now < game.start else "live" if now < game.end else "final"

    def _event(self, game: _Game, now: datetime) -> Event:
        status = self._status(game, now)
        return Event(
            id=game.id,
            league=self._league_key,
            home_team_id=game.home,
            away_team_id=game.away,
            start_time=game.start,
            status=status,  # type: ignore[arg-type]
            score=Score(home=game.home_score, away=game.away_score) if status == "final" else None,
            period_text={"live": "In progress", "final": "Final"}.get(status),
            markets=game.markets,
            **self._prov(game.id, now),
        )

    def list_events(
        self,
        league: str | None = None,
        status: str | None = None,
        on_date: date | None = None,
    ) -> list[Event]:
        if league and league != self._league_key:
            return []
        now = self.now()
        today = now.date()
        first = on_date or today - timedelta(days=WINDOW_DAYS_BACK)
        last = on_date or today + timedelta(days=WINDOW_DAYS_AHEAD)
        events = [
            self._event(game, now) for game in self._ordered if first <= game.start.date() <= last
        ]
        return [event for event in events if not status or event.status == status]

    def get_event(self, event_id: str) -> Event | None:
        game = self._games.get(event_id)
        return self._event(game, self.now()) if game else None

    def _next_game(self, team_id: str, now: datetime) -> _Game | None:
        horizon = now + timedelta(days=NEXT_EVENT_DAYS)
        for game in self._team_games.get(team_id, []):
            if game.end > now:
                return game if game.start <= horizon else None
        return None

    def next_event_for_team(self, team_id: str) -> Event | None:
        now = self.now()
        game = self._next_game(team_id, now)
        return self._event(game, now) if game else None

    # ------------------------------------------------------------------- odds
    def _fair(self, game: _Game, market: str, at: datetime) -> _Fair:
        """Closing no-vig probabilities, with a simulated drift that fades out at kickoff."""
        closing = game.closing[market]
        hours = max((game.start - at).total_seconds() / 3600, 0.0)
        phase = 2 * math.pi * self._u("phase", game.id, market)
        wave = math.sin(2 * math.pi * hours / 31 + phase) + 0.5 * math.sin(
            2 * math.pi * hours / 11 + 2 * phase
        )
        shift = 0.10 * min(hours / 12, 1.0) * wave
        first = closing[0][3]
        moved = 1 / (1 + math.exp(-(math.log(first / (1 - first)) + shift)))
        return [(*closing[0][:3], moved), (*closing[1][:3], 1 - moved)]

    def _prices(
        self, fair: _Fair, book: _Book, scope: str, market: str, bucket: int
    ) -> list[OddsOutcome]:
        """Fair probabilities -> book prices: a stable per-book lean, tick noise, then margin."""
        noisy = [
            min(max(p, 0.02), 0.98)
            * math.exp(
                0.012 * self._z("lean", book.key, i, scope, market)
                + 0.005 * self._z("tick", book.key, i, scope, market, bucket)
            )
            for i, (*_, p) in enumerate(fair)
        ]
        norm = sum(noisy)
        return [
            OddsOutcome(
                key=key,
                name=name,
                line=line,
                price_american=_american_from_implied(q / norm * (1 + book.hold)),
            )
            for (key, name, line, _), q in zip(fair, noisy, strict=True)
        ]

    def _quote(self, game: _Game, market: str, book: _Book, at: datetime) -> list[OddsOutcome]:
        bucket = int(at.timestamp() // book.update_interval)
        return self._prices(self._fair(game, market, at), book, game.id, market, bucket)

    def _offer_status(self, scope: str, market: str, book: _Book, event_status: str) -> str:
        if self._u("avail", scope, market, book.key) < 0.05:
            return "unavailable"
        if event_status != "upcoming":
            return "closed"
        if self._u("susp", scope, market, book.key) < 0.05:
            return "suspended"
        return "open"

    def _last_updated(
        self, scope: str, market: str, book: _Book, game: _Game, now: datetime
    ) -> datetime:
        if now >= game.start:
            return game.start
        jitter = self._u("age", scope, market, book.key, int(now.timestamp() // 15))
        age = 1500 + 1500 * jitter if book.stale else 20 + 400 * jitter
        return now - timedelta(seconds=age)

    def get_odds(self, event_id: str, market: str) -> list[OddsSnapshot]:
        game = self._games.get(event_id)
        if game is None or market not in game.markets:
            return []
        now = self.now()
        event_status = self._status(game, now)
        closing_at = game.start - timedelta(seconds=1)
        snapshots: list[OddsSnapshot] = []
        for book in _BOOKS:
            status = self._offer_status(game.id, market, book, event_status)
            record = self._prov(f"odds:{game.id}:{market}:{book.key}", now)
            if status == "unavailable":
                snapshots.append(
                    OddsSnapshot(
                        event_id=game.id,
                        market=market,
                        sportsbook_id=book.key,
                        status="unavailable",
                        last_updated=None,
                        outcomes=[],
                        **record,
                    )
                )
                continue
            updated = self._last_updated(game.id, market, book, game, now)
            snapshots.append(
                OddsSnapshot(
                    event_id=game.id,
                    market=market,
                    sportsbook_id=book.key,
                    status=status,  # type: ignore[arg-type]
                    last_updated=updated,
                    outcomes=self._quote(
                        game, market, book, closing_at if status == "closed" else updated
                    ),
                    **record,
                )
            )
        return snapshots

    def get_line_history(self, event_id: str, market: str) -> list[LineSeries]:
        game = self._games.get(event_id)
        if game is None or market not in game.markets:
            return []
        now = self.now()
        event_status = self._status(game, now)
        closing_at = game.start - timedelta(seconds=1)
        horizon = now if event_status == "upcoming" else closing_at
        first = (horizon - timedelta(hours=HISTORY_HOURS)).replace(
            minute=0, second=0, microsecond=0
        ) + timedelta(hours=1)
        series: list[LineSeries] = []
        for book in _BOOKS:
            if self._offer_status(game.id, market, book, event_status) == "unavailable":
                continue
            last = (
                self._last_updated(game.id, market, book, game, now)
                if event_status == "upcoming"
                else closing_at
            )
            stamps: list[datetime] = []
            cursor = first
            while cursor < last:
                stamps.append(cursor)
                cursor += timedelta(hours=1)
            stamps.append(last)
            per_outcome: dict[str, tuple[str, list[LinePoint]]] = {}
            for stamp in stamps:
                for outcome in self._quote(game, market, book, stamp):
                    _, points = per_outcome.setdefault(outcome.key, (outcome.name, []))
                    points.append(
                        LinePoint(
                            timestamp=stamp,
                            price_american=outcome.price_american,
                            line=outcome.line,
                        )
                    )
            for outcome_key, (name, points) in per_outcome.items():
                series.append(
                    LineSeries(
                        event_id=game.id,
                        market=market,
                        sportsbook_id=book.key,
                        outcome_key=outcome_key,
                        outcome_name=name,
                        points=points,
                        **self._prov(f"hist:{game.id}:{market}:{book.key}:{outcome_key}", now),
                    )
                )
        return series

    # ---------------------------------------------------------------- players
    def get_player_game_log(self, player_id: str, limit: int | None = None) -> list[GameLogEntry]:
        data = self._players.get(player_id)
        if data is None:
            return []
        now = self.now()
        wanted = GAME_LOG_GAMES if limit is None else min(limit, GAME_LOG_GAMES)
        entries: list[GameLogEntry] = []
        for _, game_id, team_id, stats in reversed(data.lines):
            game = self._games[game_id]
            if game.end > now:
                continue
            if len(entries) >= wanted:
                break
            is_home = game.home == team_id
            entries.append(
                GameLogEntry(
                    player_id=player_id,
                    event_id=game.id,
                    game_time=game.start,
                    opponent_team_id=game.away if is_home else game.home,
                    is_home=is_home,
                    stats=dict(stats),
                    **self._prov(f"log:{player_id}:{game.id}", now),
                )
            )
        return entries

    def get_prop_offers(self, player_id: str, market: str | None = None) -> list[PropOffer]:
        data = self._players.get(player_id)
        if data is None:
            return []
        now = self.now()
        player = self._player_at(data, now)
        game = self._next_game(player.team_id, now)
        # Only players who appeared in that game are listed, as a real book lists active players.
        if game is None or all(line[1] != game.id for line in data.lines):
            return []
        prior = [line[3] for line in data.lines if line[0] < game.start][-PROP_LOOKBACK_GAMES:]
        if len(prior) < PROP_MIN_PRIOR_GAMES:
            return []
        event_status = self._status(game, now)
        offers: list[PropOffer] = []
        for prop_market in player.prop_markets:
            if market and prop_market != market:
                continue
            values = [stats.get(prop_market, 0.0) for stats in prior]
            mean = sum(values) / len(values)
            deviation = max(pstdev(values), 0.25 * mean, 1.0)
            scope = f"{game.id}:{player_id}"
            for book in _BOOKS:
                status = self._offer_status(scope, prop_market, book, event_status)
                record = self._prov(f"prop:{scope}:{prop_market}:{book.key}", now)
                if status == "unavailable":
                    offers.append(
                        PropOffer(
                            player_id=player_id,
                            event_id=game.id,
                            market=prop_market,
                            sportsbook_id=book.key,
                            status="unavailable",
                            last_updated=None,
                            **record,
                        )
                    )
                    continue
                line = _half_line(mean)
                if mean >= 12:
                    pick = self._u("propoff", scope, prop_market, book.key)
                    line += -1.0 if pick < 0.15 else 1.0 if pick > 0.85 else 0.0
                p_over = _NORMAL.cdf((mean - line) / deviation)
                updated = self._last_updated(scope, prop_market, book, game, now)
                bucket = int(updated.timestamp() // book.update_interval)
                over, under = self._prices(
                    [("over", "Over", line, p_over), ("under", "Under", line, 1 - p_over)],
                    book,
                    scope,
                    prop_market,
                    bucket,
                )
                offers.append(
                    PropOffer(
                        player_id=player_id,
                        event_id=game.id,
                        market=prop_market,
                        sportsbook_id=book.key,
                        status=status,  # type: ignore[arg-type]
                        last_updated=updated,
                        line=line,
                        over_american=over.price_american,
                        under_american=under.price_american,
                        **record,
                    )
                )
        return offers
