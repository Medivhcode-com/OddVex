"""Deterministic synthetic sports data.

Everything here is fabricated: the teams, players and sportsbooks do not
exist. Output is a pure function of ``(seed, current time)``:

* the schedule is keyed on the UTC calendar date, so event ids are stable and
  there are always completed, live and upcoming events around "now";
* every random-looking number is a hash of the seed and a stable key, so two
  processes with the same seed and clock return identical data.

The scoring model is intentionally simple and is the only source of both the
results and the prices. Each side scores as a Poisson process: its scoring
plays arrive at a constant rate through the game, independently of the other
side (one point per play, except football, where a play is worth 3 or 7). The
rates are fixed at the start from the two teams' ratings; before the start the
quoted expectation drifts around them and reaches them at the start, so the
closing price is the model's own probability. A game level after regulation in
a league without draws goes to the next score, which each side takes with a
chance proportional to its rate.

A fair price is the exact probability of the final result under that model,
given the score so far and the time left. Final scores are drawn from the same
model, so over many games every side of every market wins as often as its fair
price says. Book prices are the fair probabilities plus a margin and small
noise, so no book or prop has a real edge. A book stops quoting a market
(``suspended``) once one outcome is more than 98% likely.
"""

from __future__ import annotations

import hashlib
import math
import random
from bisect import bisect_right
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from statistics import NormalDist

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

PROVIDER_NAME = "synthetic"
_NORMAL = NormalDist()

#: Fair probabilities of one market: (outcome key, display name, line, probability).
type _Fair = list[tuple[str, str, float | None, float]]

#: Days of schedule exposed by ``list_events`` relative to today (UTC).
WINDOW_DAYS_BACK = 3
WINDOW_DAYS_AHEAD = 4
GAMES_PER_DAY = 4
GAME_LOG_GAMES = 40
HISTORY_HOURS = 48

#: A book suspends a market once one outcome's fair probability passes this. Above it the
#: price grid (which ends near -6600) could no longer keep the price at or below fair.
_DECIDED_PROBABILITY = 0.98
#: Probability mass a truncated score distribution may leave out.
_PMF_TAIL = 1e-13


@dataclass(frozen=True)
class _PropSpec:
    mean: float
    #: Spread of the per-player mean, as a fraction of ``mean``.
    player_sd: float
    #: Game-to-game standard deviation.
    game_sd: float


@dataclass(frozen=True)
class _LeagueCfg:
    key: str
    name: str
    sport: str
    index: int
    duration_hours: float
    #: How far the quoted expected margin drifts before the start, in points.
    margin_drift: float
    home_advantage: float
    rating_sd: float
    total_mean: float
    total_team_sd: float
    #: How far the quoted expected total drifts before the start, in points.
    total_drift: float
    has_draw: bool = False
    has_spread: bool = True
    fixed_spread: float | None = None
    #: Size of the occasional per-book line offset (0 = books share the line).
    line_step: float = 0.0
    #: Kinds of scoring play: (points, share of all scoring plays).
    scoring: tuple[tuple[int, float], ...] = ((1, 1.0),)
    #: Points the next score is worth when a game without draws is level after regulation.
    overtime_points: int = 1
    roster: tuple[tuple[str, dict[str, _PropSpec]], ...] = ()

    @property
    def points_per_play(self) -> float:
        return sum(points * share for points, share in self.scoring)

    @property
    def markets(self) -> list[str]:
        return ["moneyline", "spread", "total"] if self.has_spread else ["moneyline", "total"]

    @property
    def prop_markets(self) -> list[str]:
        seen: list[str] = []
        for _, specs in self.roster:
            for market in specs:
                if market not in seen:
                    seen.append(market)
        return seen


def _p(mean: float, player_sd: float, game_sd: float) -> _PropSpec:
    return _PropSpec(mean, player_sd, game_sd)


_LEAGUES: tuple[_LeagueCfg, ...] = (
    _LeagueCfg(
        key="nba",
        name="Pro Basketball (synthetic)",
        sport="basketball",
        index=0,
        duration_hours=2.5,
        margin_drift=0.6,
        home_advantage=2.5,
        rating_sd=4.0,
        total_mean=224.0,
        total_team_sd=4.0,
        total_drift=0.72,
        line_step=1.0,
        roster=(
            (
                "G",
                {
                    "points": _p(24.0, 0.15, 6.5),
                    "rebounds": _p(4.5, 0.2, 2.2),
                    "assists": _p(7.0, 0.2, 2.6),
                    "threes": _p(2.8, 0.2, 1.5),
                },
            ),
            (
                "G",
                {
                    "points": _p(17.0, 0.15, 5.5),
                    "rebounds": _p(3.5, 0.2, 1.9),
                    "assists": _p(4.5, 0.2, 2.1),
                    "threes": _p(2.2, 0.2, 1.4),
                },
            ),
            (
                "F",
                {
                    "points": _p(20.0, 0.15, 6.0),
                    "rebounds": _p(8.0, 0.15, 3.0),
                    "assists": _p(3.5, 0.2, 1.9),
                    "threes": _p(1.6, 0.25, 1.2),
                },
            ),
            (
                "C",
                {
                    "points": _p(15.0, 0.15, 5.0),
                    "rebounds": _p(11.0, 0.12, 3.4),
                    "assists": _p(2.5, 0.25, 1.6),
                    "threes": _p(0.6, 0.3, 0.8),
                },
            ),
        ),
    ),
    _LeagueCfg(
        key="nfl",
        name="Pro Football (synthetic)",
        sport="american_football",
        index=1,
        duration_hours=3.0,
        margin_drift=0.675,
        home_advantage=1.8,
        rating_sd=4.0,
        total_mean=44.5,
        total_team_sd=2.0,
        total_drift=0.52,
        line_step=1.0,
        scoring=((3, 0.4), (7, 0.6)),
        overtime_points=3,
        roster=(
            ("QB", {"passing_yards": _p(245.0, 0.1, 55.0), "rushing_yards": _p(18.0, 0.4, 14.0)}),
            ("RB", {"rushing_yards": _p(72.0, 0.18, 28.0), "receptions": _p(2.8, 0.2, 1.5)}),
            ("WR", {"receptions": _p(5.6, 0.15, 2.1)}),
            ("WR", {"receptions": _p(4.2, 0.15, 1.9)}),
        ),
    ),
    _LeagueCfg(
        key="mlb",
        name="Pro Baseball (synthetic)",
        sport="baseball",
        index=2,
        duration_hours=3.0,
        margin_drift=0.21,
        home_advantage=0.15,
        rating_sd=0.6,
        total_mean=8.6,
        total_team_sd=0.5,
        total_drift=0.168,
        fixed_spread=1.5,
        roster=(
            ("OF", {"hits": _p(1.05, 0.12, 0.85)}),
            ("IF", {"hits": _p(0.95, 0.12, 0.85)}),
            ("C", {"hits": _p(0.85, 0.12, 0.8)}),
            ("SP", {"strikeouts": _p(6.0, 0.14, 2.1)}),
        ),
    ),
    _LeagueCfg(
        key="nhl",
        name="Pro Hockey (synthetic)",
        sport="ice_hockey",
        index=3,
        duration_hours=2.5,
        margin_drift=0.12,
        home_advantage=0.15,
        rating_sd=0.35,
        total_mean=6.1,
        total_team_sd=0.3,
        total_drift=0.092,
        fixed_spread=1.5,
        roster=(
            ("C", {"shots": _p(3.1, 0.14, 1.5), "points": _p(0.95, 0.16, 0.85)}),
            ("LW", {"shots": _p(2.7, 0.14, 1.4), "points": _p(0.75, 0.16, 0.8)}),
            ("RW", {"shots": _p(2.5, 0.14, 1.4), "points": _p(0.7, 0.16, 0.8)}),
            ("D", {"shots": _p(2.1, 0.14, 1.3), "points": _p(0.5, 0.16, 0.7)}),
        ),
    ),
    _LeagueCfg(
        key="soccer",
        name="Premier Soccer (synthetic)",
        sport="soccer",
        index=4,
        duration_hours=2.0,
        margin_drift=0.085,
        home_advantage=0.3,
        rating_sd=0.5,
        total_mean=2.7,
        total_team_sd=0.2,
        total_drift=0.064,
        has_draw=True,
        has_spread=False,
        roster=(
            ("FW", {"shots": _p(3.0, 0.14, 1.5)}),
            ("FW", {"shots": _p(2.4, 0.14, 1.4)}),
            ("MF", {"shots": _p(1.7, 0.16, 1.2)}),
            ("MF", {"shots": _p(1.3, 0.16, 1.1)}),
        ),
    ),
)

# (city, nickname, abbreviation). All invented.
_TEAM_NAMES: dict[str, tuple[tuple[str, str, str], ...]] = {
    "nba": (
        ("Harbor City", "Tides", "HCT"),
        ("Ironvale", "Anvils", "IRV"),
        ("Port Sable", "Lanterns", "PSL"),
        ("Emberton", "Cinders", "EMB"),
        ("Larkspur Bay", "Herons", "LKB"),
        ("Northgate", "Gales", "NGT"),
        ("Copper Ridge", "Kestrels", "CPR"),
        ("Saltmarsh", "Drifters", "SLT"),
    ),
    "nfl": (
        ("Granite Falls", "Boulders", "GRF"),
        ("Westmere", "Wardens", "WMR"),
        ("Thornfield", "Stags", "THF"),
        ("Cinder Lake", "Voyagers", "CLK"),
        ("Brackwater", "Ferrymen", "BRW"),
        ("Highmoor", "Harriers", "HMR"),
        ("Dunmarrow", "Quarrymen", "DNM"),
        ("Ashgrove", "Thunderheads", "ASG"),
    ),
    "mlb": (
        ("Millbrook", "Millwrights", "MLB"),
        ("Sunhaven", "Skylarks", "SNH"),
        ("Pinecrest", "Lamplighters", "PNC"),
        ("Fairwind", "Halyards", "FWD"),
        ("Oakhollow", "Bellringers", "OKH"),
        ("Marrow Point", "Beacons", "MRP"),
        ("Tallgrass", "Windmills", "TLG"),
        ("Redwater", "Clockmakers", "RDW"),
    ),
    "nhl": (
        ("Frostholm", "Glaciers", "FRH"),
        ("Coldspring", "Ospreys", "CSP"),
        ("Winterbourne", "Lodestars", "WTB"),
        ("Icefall", "Marmots", "ICF"),
        ("Stonewick", "Gantries", "STW"),
        ("Borealis Bay", "Starlings", "BRB"),
        ("Kettle Harbor", "Tinkers", "KTH"),
        ("Snowmere", "Sextants", "SNM"),
    ),
    "soccer": (
        ("Aldermoor", "Athletic", "ALD"),
        ("Brightwater", "Rovers", "BWR"),
        ("Castlereach", "United", "CSR"),
        ("Dunhallow", "Town", "DNH"),
        ("Eastmarch", "Wanderers", "EMW"),
        ("Fenwick Vale", "Albion", "FWV"),
        ("Greyhaven", "Borough", "GRH"),
        ("Hollowbrook", "Rangers", "HBR"),
    ),
}

_FIRST_NAMES = (
    "Dax", "Tobin", "Marek", "Quill", "Osric", "Levan", "Corwin", "Idris", "Jorah", "Kellan",
    "Brannock", "Soren", "Tavish", "Emeric", "Lucan", "Rafferty", "Zeph", "Alaric", "Cormac",
    "Nico", "Wystan", "Evander", "Fenn", "Garrick", "Hollis", "Ivo", "Jessup", "Kasimir",
    "Lorcan", "Maddox", "Oren", "Piers",
)  # fmt: skip
_LAST_NAMES = (
    "Varrow", "Quillfeather", "Brakewater", "Thornbury", "Ashdown", "Vantreese", "Okonwell",
    "Marlowick", "Stennard", "Halloway", "Drummick", "Pellgrave", "Castellane", "Rookwood",
    "Faircloth", "Underhay", "Windermoor", "Blackmere", "Tanglewood", "Harrowgate", "Sablecourt",
    "Lindqvale", "Mossgrove", "Emberlyn", "Kingsmoor", "Dovehollow", "Starkweather", "Greenhalgh",
    "Ravensworth", "Tidewell", "Flintlock", "Merriweather", "Coldbrook", "Ironsides", "Wexcombe",
    "Yarrowby", "Zennor", "Oakenshaw", "Peverell", "Quartermain",
)  # fmt: skip


@dataclass(frozen=True)
class _Book:
    key: str
    name: str
    hold: float
    update_interval: int
    stale: bool = False


_BOOKS: tuple[_Book, ...] = (
    _Book("northline", "Northline", 0.040, 20),
    _Book("cardinal", "Cardinal Sports", 0.048, 30),
    _Book("summit", "Summit Wager", 0.045, 25),
    _Book("blueharbor", "BlueHarbor Book", 0.052, 45),
    _Book("kestrel", "Kestrel Bets", 0.035, 15),
    # Intentionally stale feed so freshness handling is always exercised.
    _Book("oldmill", "Old Mill Sportsbook", 0.060, 1800, stale=True),
)


@dataclass
class _Timeline:
    """Every scoring play of regulation, in order, with the score after each one."""

    #: Played fraction of the game (0 to 1) at which each play happens.
    times: list[float]
    home_after: list[int]
    away_after: list[int]


@dataclass
class _EventCore:
    id: str
    cfg: _LeagueCfg
    day: date
    slot: int
    home: Team
    away: Team
    start: datetime
    end: datetime
    #: Expected margin and total from the ratings, before the pre-start drift is added.
    margin_pre: float
    total_pre: float
    #: Points each side is expected to score in regulation: the rates the game is played at
    #: and the expectation the closing price quotes.
    home_mean: float
    away_mean: float
    #: Scoring plays of each side in regulation, per kind of play (same order as
    #: ``cfg.scoring``).
    home_plays: tuple[int, ...]
    away_plays: tuple[int, ...]
    final_home: int
    final_away: int
    timeline: _Timeline | None = None

    @property
    def home_share(self) -> float:
        """Chance that the home side gets the next score."""
        return self.home_mean / (self.home_mean + self.away_mean)


@dataclass(frozen=True)
class _State:
    status: str
    fraction: float
    home_score: int
    away_score: int
    #: Points each side is still expected to score in regulation.
    home_mean: float
    away_mean: float
    #: When the score last changed (the start counts). Only set while the game is live.
    score_updated_at: datetime | None = None

    @property
    def margin(self) -> float:
        """Expected margin at the end of regulation, home minus away."""
        return self.home_score - self.away_score + self.home_mean - self.away_mean

    @property
    def total(self) -> float:
        """Expected total at the end of regulation."""
        return self.home_score + self.away_score + self.home_mean + self.away_mean


@dataclass(frozen=True)
class _Priced:
    """One book's prices for one market at one moment."""

    outcomes: list[OddsOutcome]
    #: One outcome was more than ``_DECIDED_PROBABILITY`` likely.
    decided: bool


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _half_line(value: float) -> float:
    """Nearest line ending in .5 (so synthetic spreads and totals never push)."""
    return math.floor(value) + 0.5


def _poisson_pmf(mean: float) -> list[float]:
    """P(N = 0), P(N = 1), ... for a Poisson count, cut once the rest is negligible.

    The terms fall faster than geometrically past the mean, so stopping at the first term
    below ``_PMF_TAIL`` leaves out about that much. The means used here are at most a few
    hundred, far from where ``exp(-mean)`` underflows.
    """
    if mean <= 0:
        return [1.0]
    probability = math.exp(-mean)
    pmf = [probability]
    count = 0
    while count < mean or probability > _PMF_TAIL:
        count += 1
        probability *= mean / count
        pmf.append(probability)
    return pmf


def _points_pmf(cfg: _LeagueCfg, mean_points: float) -> list[float]:
    """Distribution of the points one side adds when ``mean_points`` are expected."""
    plays = mean_points / cfg.points_per_play
    pmf = [1.0]
    for points, share in cfg.scoring:
        counts = _poisson_pmf(plays * share)
        if points == 1 and len(pmf) == 1:
            pmf = counts
            continue
        combined = [0.0] * (len(pmf) + points * (len(counts) - 1))
        for have, p in enumerate(pmf):
            if p:
                for count, q in enumerate(counts):
                    combined[have + points * count] += p * q
        pmf = combined
    return pmf


def _at_least(pmf: list[float]) -> list[float]:
    """``result[n]`` = P(X >= n) for n = 0 .. len(pmf); the last entry is 0."""
    tail = [0.0] * (len(pmf) + 1)
    running = 0.0
    for n in range(len(pmf) - 1, -1, -1):
        running += pmf[n]
        tail[n] = running
    tail[0] = 1.0
    return tail


class _Outlook:
    """Exact distribution of the final score, given the score so far and what is expected.

    ``home_pmf`` and ``away_pmf`` are the distributions of the points each side still adds
    in regulation. With ``overtime_points`` set, a game level after regulation is decided
    by one more score of that size, taken by the home side with chance ``home_share``.
    """

    def __init__(
        self,
        home_score: int,
        away_score: int,
        home_pmf: list[float],
        away_pmf: list[float],
        home_share: float,
        overtime_points: int | None,
    ) -> None:
        self._lead = home_score - away_score
        self._points = home_score + away_score
        self._home = home_pmf
        self._away = away_pmf
        self._home_at_least = _at_least(home_pmf)
        self._away_at_least = _at_least(away_pmf)
        self._home_share = home_share
        self._overtime = overtime_points
        self.level = self._margin_is(0)

    def _margin_at_least(self, margin: int) -> float:
        """P(regulation margin >= ``margin``), home minus away."""
        need = margin - self._lead  # home must add at least ``need`` more than away adds
        tail = self._home_at_least
        size = len(self._home)
        total = 0.0
        for added, p in enumerate(self._away):
            index = need + added
            total += p if index <= 0 else p * tail[index] if index <= size else 0.0
        return total

    def _margin_is(self, margin: int) -> float:
        need = margin - self._lead
        size = len(self._home)
        total = 0.0
        for added, p in enumerate(self._away):
            index = need + added
            if 0 <= index < size:
                total += p * self._home[index]
        return total

    def _total_at_least(self, points: int) -> float:
        need = points - self._points
        tail = self._away_at_least
        size = len(self._away)
        total = 0.0
        for added, p in enumerate(self._home):
            index = need - added
            total += p if index <= 0 else p * tail[index] if index <= size else 0.0
        return total

    def _level_with_total_between(self, low: int, high: int) -> float:
        """P(level after regulation with ``low`` <= regulation total <= ``high``)."""
        size = len(self._away)
        total = 0.0
        for added, p in enumerate(self._home):
            index = added + self._lead  # what away must add to be level
            if 0 <= index < size and low <= self._points + added + index <= high:
                total += p * self._away[index]
        return total

    def home_win(self) -> float:
        ahead = self._margin_at_least(1)
        return ahead if self._overtime is None else ahead + self.level * self._home_share

    def draw(self) -> float:
        return self.level if self._overtime is None else 0.0

    def home_covers(self, home_line: float) -> float:
        """P(final margin + ``home_line`` > 0) for a line ending in .5."""
        need = math.floor(-home_line) + 1  # smallest final margin that covers
        covered = self._margin_at_least(need)
        if self._overtime is None:
            return covered
        if need <= 0:
            covered -= self.level  # a level game is not final: the next score decides it
        if self._overtime >= need:
            covered += self.level * self._home_share
        if -self._overtime >= need:
            covered += self.level * (1 - self._home_share)
        return covered

    def over(self, line: float) -> float:
        """P(final total > ``line``) for a line ending in .5."""
        need = math.floor(line) + 1
        above = self._total_at_least(need)
        if self._overtime is None:
            return above
        return above + self._level_with_total_between(need - self._overtime, need - 1)


def _american_from_implied(implied: float) -> int:
    implied = min(max(implied, 0.012), 0.985)
    raw = -100.0 * implied / (1.0 - implied) if implied >= 0.5 else 100.0 * (1 - implied) / implied
    magnitude = abs(raw)
    step = 1 if magnitude < 250 else 5 if magnitude < 1000 else 25
    rounded = int(round(raw / step) * step)
    if -100 <= rounded < 100:
        rounded = 100 if raw > 0 or rounded > -100 else -100
    if rounded == -100:
        rounded = 100
    return rounded


class SyntheticProvider:
    """Seeded, clock-relative implementation of :class:`SportsDataProvider`."""

    name = PROVIDER_NAME
    data_mode = "synthetic"

    def __init__(self, seed: int = 20260101, clock: Callable[[], datetime] | None = None) -> None:
        self.seed = seed
        self._clock = clock or _utc_now
        self._cfg = {cfg.key: cfg for cfg in _LEAGUES}
        self._books = {book.key: book for book in _BOOKS}
        self._teams: dict[str, Team] = {}
        self._teams_by_league: dict[str, list[Team]] = {}
        self._players: dict[str, Player] = {}
        self._players_by_team: dict[str, list[Player]] = {}
        self._player_specs: dict[str, dict[str, _PropSpec]] = {}
        self._core_cache: dict[str, _EventCore] = {}
        self._matchup_cache: dict[tuple[str, int], list[tuple[Team, Team]]] = {}
        #: Fair probabilities already worked out, keyed on everything they depend on:
        #: (event id, market, the book's line offset, score, expected points still to come).
        self._fair_cache: dict[tuple[str, str, float, int, int, float, float], _Fair] = {}
        self._build_static()

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

    def _prov(self, record_id: str, fetched_at: datetime) -> dict[str, object]:
        return {"provider": self.name, "provider_id": f"syn:{record_id}", "fetched_at": fetched_at}

    # ----------------------------------------------------------- static data
    def _build_static(self) -> None:
        epoch = datetime(2026, 1, 1, tzinfo=UTC)
        names = [(f, last) for f in _FIRST_NAMES for last in _LAST_NAMES]
        random.Random(f"{self.seed}|names").shuffle(names)
        name_iter = iter(names)
        for cfg in _LEAGUES:
            teams: list[Team] = []
            for city, nickname, abbr in _TEAM_NAMES[cfg.key]:
                team_id = f"team_{cfg.key}_{abbr.lower()}"
                team = Team(
                    id=team_id,
                    league=cfg.key,
                    name=f"{city} {nickname}",
                    city=city,
                    nickname=nickname,
                    abbreviation=abbr,
                    **self._prov(team_id, epoch),
                )
                teams.append(team)
                self._teams[team_id] = team
                roster: list[Player] = []
                for n, (position, specs) in enumerate(cfg.roster, start=1):
                    first, last = next(name_iter)
                    player_id = f"plr_{cfg.key}_{abbr.lower()}_{n}"
                    player = Player(
                        id=player_id,
                        league=cfg.key,
                        team_id=team_id,
                        name=f"{first} {last}",
                        position=position,
                        jersey_number=1 + int(self._u("jersey", player_id) * 98),
                        prop_markets=list(specs),
                        **self._prov(player_id, epoch),
                    )
                    roster.append(player)
                    self._players[player_id] = player
                    self._player_specs[player_id] = {
                        market: _PropSpec(
                            mean=max(
                                0.3,
                                spec.mean
                                * (1 + spec.player_sd * self._z("pmean", player_id, market)),
                            ),
                            player_sd=spec.player_sd,
                            game_sd=spec.game_sd,
                        )
                        for market, spec in specs.items()
                    }
                self._players_by_team[team_id] = roster
            self._teams_by_league[cfg.key] = teams

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            data_mode=self.data_mode,
            status="ok",
            checked_at=self.now(),
            detail="Deterministic synthetic data generator; no external dependency.",
        )

    def list_leagues(self) -> list[League]:
        now = self.now()
        return [
            League(
                id=cfg.key,
                key=cfg.key,
                name=cfg.name,
                sport=cfg.sport,
                has_draw=cfg.has_draw,
                markets=cfg.markets,
                prop_markets=cfg.prop_markets,
                **self._prov(f"league:{cfg.key}", now),
            )
            for cfg in _LEAGUES
        ]

    def list_sportsbooks(self) -> list[Sportsbook]:
        now = self.now()
        return [
            Sportsbook(id=b.key, key=b.key, name=b.name, **self._prov(f"book:{b.key}", now))
            for b in _BOOKS
        ]

    def list_teams(self, league: str | None = None) -> list[Team]:
        if league is None:
            return list(self._teams.values())
        return list(self._teams_by_league.get(league, []))

    def get_team(self, team_id: str) -> Team | None:
        return self._teams.get(team_id)

    def list_players(
        self, league: str | None = None, team_id: str | None = None, query: str | None = None
    ) -> list[Player]:
        needle = (query or "").strip().lower()
        result = []
        for player in self._players.values():
            if league and player.league != league:
                continue
            if team_id and player.team_id != team_id:
                continue
            if needle and needle not in player.name.lower():
                continue
            result.append(player)
        return result

    def get_player(self, player_id: str) -> Player | None:
        return self._players.get(player_id)

    # --------------------------------------------------------------- schedule
    def _matchups(self, cfg: _LeagueCfg, day: date) -> list[tuple[Team, Team]]:
        key = (cfg.key, day.toordinal())
        cached = self._matchup_cache.get(key)
        if cached is None:
            teams = list(self._teams_by_league[cfg.key])
            random.Random(f"{self.seed}|sched|{cfg.key}|{day.toordinal()}").shuffle(teams)
            cached = [(teams[2 * i], teams[2 * i + 1]) for i in range(GAMES_PER_DAY)]
            if len(self._matchup_cache) > 4000:
                self._matchup_cache.clear()
            self._matchup_cache[key] = cached
        return cached

    def _rating(self, team: Team) -> float:
        return self._cfg[team.league].rating_sd * self._z("rating", team.id)

    def _core(self, cfg: _LeagueCfg, day: date, slot: int) -> _EventCore:
        event_id = f"evt_{cfg.key}_{day:%Y%m%d}_{slot}"
        cached = self._core_cache.get(event_id)
        if cached is not None:
            return cached
        home, away = self._matchups(cfg, day)[slot]
        start = datetime(day.year, day.month, day.day, (cfg.index + 6 * slot) % 24, tzinfo=UTC)
        end = start + timedelta(hours=cfg.duration_hours)
        margin_pre = self._rating(home) - self._rating(away) + cfg.home_advantage
        total_pre = cfg.total_mean + cfg.total_team_sd * (
            self._z("pace", home.id) + self._z("pace", away.id)
        )
        # The game is played at the expectation quoted at the start (the closing price).
        home_mean, away_mean = self._expected_points(cfg, event_id, margin_pre, total_pre, 0.0)
        home_plays = self._play_counts(cfg, event_id, "h", home_mean)
        away_plays = self._play_counts(cfg, event_id, "a", away_mean)
        final_home = sum(n * points for n, (points, _) in zip(home_plays, cfg.scoring, strict=True))
        final_away = sum(n * points for n, (points, _) in zip(away_plays, cfg.scoring, strict=True))
        if not cfg.has_draw and final_home == final_away:
            # Level after regulation: the next score wins it.
            if self._u("ot", event_id) < home_mean / (home_mean + away_mean):
                final_home += cfg.overtime_points
            else:
                final_away += cfg.overtime_points
        core = _EventCore(
            id=event_id,
            cfg=cfg,
            day=day,
            slot=slot,
            home=home,
            away=away,
            start=start,
            end=end,
            margin_pre=margin_pre,
            total_pre=total_pre,
            home_mean=home_mean,
            away_mean=away_mean,
            home_plays=home_plays,
            away_plays=away_plays,
            final_home=final_home,
            final_away=final_away,
        )
        if len(self._core_cache) > 5000:
            self._core_cache.clear()
        self._core_cache[event_id] = core
        return core

    def _expected_points(
        self,
        cfg: _LeagueCfg,
        event_id: str,
        margin_pre: float,
        total_pre: float,
        hours_to_start: float,
    ) -> tuple[float, float]:
        """Expected regulation points (home, away) as quoted ``hours_to_start`` before the start.

        The quoted margin and total drift on two slow waves; the values at the start are the
        ones the game is played at.
        """
        phase_a = 2 * math.pi * self._u("ph1", event_id)
        phase_b = 2 * math.pi * self._u("ph2", event_id)
        wave = math.sin(2 * math.pi * hours_to_start / 31 + phase_a) + 0.5 * math.sin(
            2 * math.pi * hours_to_start / 11 + phase_b
        )
        margin = margin_pre + cfg.margin_drift * wave
        total = total_pre + cfg.total_drift * math.cos(phase_a + wave)
        floor = 0.1 * cfg.points_per_play
        return max((total + margin) / 2, floor), max((total - margin) / 2, floor)

    def _play_counts(
        self, cfg: _LeagueCfg, event_id: str, side: str, mean_points: float
    ) -> tuple[int, ...]:
        """Scoring plays of one side in regulation, per kind of play: Poisson draws."""
        plays = mean_points / cfg.points_per_play
        counts: list[int] = []
        for points, share in cfg.scoring:
            pmf = _poisson_pmf(plays * share)
            pick = self._u("plays", event_id, side, points)
            count = 0
            covered = pmf[0]
            while covered <= pick and count < len(pmf) - 1:
                count += 1
                covered += pmf[count]
            counts.append(count)
        return tuple(counts)

    def _timeline(self, core: _EventCore) -> _Timeline:
        """When each scoring play happens. Given their number, the plays of a Poisson
        process fall independently and uniformly over the game."""
        if core.timeline is None:
            plays: list[tuple[float, int, int]] = []
            for side, counts in (("h", core.home_plays), ("a", core.away_plays)):
                for count, (points, _) in zip(counts, core.cfg.scoring, strict=True):
                    for k in range(count):
                        at = self._u("gt", core.id, side, points, k)
                        plays.append(
                            (at, points if side == "h" else 0, points if side == "a" else 0)
                        )
            plays.sort()
            home = away = 0
            timeline = _Timeline([], [], [])
            for at, home_points, away_points in plays:
                home += home_points
                away += away_points
                timeline.times.append(at)
                timeline.home_after.append(home)
                timeline.away_after.append(away)
            core.timeline = timeline
        return core.timeline

    def _core_by_id(self, event_id: str) -> _EventCore | None:
        parts = event_id.split("_")
        if len(parts) != 4 or parts[0] != "evt" or parts[1] not in self._cfg:
            return None
        try:
            day = datetime.strptime(parts[2], "%Y%m%d").date()
            slot = int(parts[3])
        except ValueError:
            return None
        if not 0 <= slot < GAMES_PER_DAY or parts[3] != str(slot):
            return None
        if abs((day - self.now().date()).days) > 400:
            return None
        return self._core(self._cfg[parts[1]], day, slot)

    def _state(self, core: _EventCore, at: datetime) -> _State:
        if at < core.start:
            # The quoted expectation moves once a minute; in the last minute it is the one
            # the game is played at.
            minutes_to_start = (core.start - at).total_seconds() // 60
            home_mean, away_mean = self._expected_points(
                core.cfg, core.id, core.margin_pre, core.total_pre, minutes_to_start / 60
            )
            return _State("upcoming", 0.0, 0, 0, home_mean, away_mean)
        if at >= core.end:
            return _State("final", 1.0, core.final_home, core.final_away, 0.0, 0.0)
        length = core.end - core.start
        fraction = (at - core.start).total_seconds() / length.total_seconds()
        timeline = self._timeline(core)
        played = bisect_right(timeline.times, fraction)
        remaining = 1.0 - fraction
        return _State(
            status="live",
            fraction=fraction,
            home_score=timeline.home_after[played - 1] if played else 0,
            away_score=timeline.away_after[played - 1] if played else 0,
            # A Poisson process has no memory: what is still to come does not depend on
            # the score so far.
            home_mean=core.home_mean * remaining,
            away_mean=core.away_mean * remaining,
            # ``min``: rounding to a whole microsecond must not put the change after ``at``.
            score_updated_at=min(at, core.start + length * timeline.times[played - 1])
            if played
            else core.start,
        )

    @staticmethod
    def _period_text(cfg: _LeagueCfg, fraction: float) -> str:
        def clock(periods: int, minutes: int, label: str) -> str:
            position = min(fraction, 0.9999) * periods
            period = int(position) + 1
            remaining = (1 - (position - int(position))) * minutes * 60
            mm, ss = divmod(int(remaining), 60)
            return f"{label}{period} {mm:02d}:{ss:02d}"

        if cfg.key == "nba":
            return clock(4, 12, "Q")
        if cfg.key == "nfl":
            return clock(4, 15, "Q")
        if cfg.key == "nhl":
            return clock(3, 20, "P")
        if cfg.key == "mlb":
            half_innings = int(min(fraction, 0.9999) * 18)
            inning = half_innings // 2 + 1
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(inning, "th")
            return f"{'Top' if half_innings % 2 == 0 else 'Bot'} {inning}{suffix}"
        minute = int(min(fraction, 0.9999) * 90) + 1
        return f"{minute}'"

    def _event(self, core: _EventCore, now: datetime) -> Event:
        state = self._state(core, now)
        return Event(
            id=core.id,
            league=core.cfg.key,
            home_team_id=core.home.id,
            away_team_id=core.away.id,
            start_time=core.start,
            status=state.status,  # type: ignore[arg-type]
            score=None
            if state.status == "upcoming"
            else Score(home=state.home_score, away=state.away_score),
            period_text=self._period_text(core.cfg, state.fraction)
            if state.status == "live"
            else ("Final" if state.status == "final" else None),
            score_updated_at=state.score_updated_at,
            markets=core.cfg.markets,
            **self._prov(core.id, now),
        )

    def list_events(
        self,
        league: str | None = None,
        status: str | None = None,
        on_date: date | None = None,
    ) -> list[Event]:
        now = self.now()
        today = now.date()
        if on_date is not None:
            if abs((on_date - today).days) > 60:
                return []
            days = [on_date]
        else:
            days = [
                today + timedelta(days=offset)
                for offset in range(-WINDOW_DAYS_BACK, WINDOW_DAYS_AHEAD + 1)
            ]
        events: list[Event] = []
        for cfg in _LEAGUES:
            if league and cfg.key != league:
                continue
            for day in days:
                for slot in range(GAMES_PER_DAY):
                    event = self._event(self._core(cfg, day, slot), now)
                    if status and event.status != status:
                        continue
                    events.append(event)
        events.sort(key=lambda e: (e.start_time, e.id))
        return events

    def get_event(self, event_id: str) -> Event | None:
        core = self._core_by_id(event_id)
        return self._event(core, self.now()) if core else None

    def next_event_for_team(self, team_id: str) -> Event | None:
        core = self._next_core_for_team(team_id, self.now())
        return self._event(core, self.now()) if core else None

    def _team_core_on(self, team: Team, day: date) -> _EventCore:
        cfg = self._cfg[team.league]
        for slot, (home, away) in enumerate(self._matchups(cfg, day)):
            if team.id in (home.id, away.id):
                return self._core(cfg, day, slot)
        raise AssertionError("every team plays every day in the synthetic schedule")

    def _next_core_for_team(self, team_id: str, now: datetime) -> _EventCore | None:
        team = self._teams.get(team_id)
        if team is None:
            return None
        for offset in range(0, 3):
            core = self._team_core_on(team, now.date() + timedelta(days=offset))
            if core.end > now:
                return core
        return None

    # ------------------------------------------------------------------- odds
    def _fair(self, core: _EventCore, market: str, book: _Book, state: _State) -> _Fair:
        """Fair probability of each outcome: exact under the scoring model, given ``state``."""
        cfg = core.cfg
        offset = 0.0
        if cfg.line_step:
            pick = self._u("lineoff", core.id, market, book.key)
            offset = -cfg.line_step if pick < 0.15 else cfg.line_step if pick > 0.85 else 0.0
        key = (
            core.id,
            market,
            offset,
            state.home_score,
            state.away_score,
            state.home_mean,
            state.away_mean,
        )
        hit = self._fair_cache.get(key)
        if hit is None:
            hit = self._fair_at(core, market, offset, state)
            if len(self._fair_cache) > 20000:
                self._fair_cache.clear()
            self._fair_cache[key] = hit
        return hit

    def _fair_at(self, core: _EventCore, market: str, offset: float, state: _State) -> _Fair:
        cfg = core.cfg
        outlook = _Outlook(
            state.home_score,
            state.away_score,
            _points_pmf(cfg, state.home_mean),
            _points_pmf(cfg, state.away_mean),
            core.home_share,
            None if cfg.has_draw else cfg.overtime_points,
        )
        if market == "moneyline":
            p_home = min(max(outlook.home_win(), 0.0), 1.0)
            if cfg.has_draw:
                p_draw = min(outlook.draw(), 1.0 - p_home)
                return [
                    ("home", core.home.name, None, p_home),
                    ("draw", "Draw", None, p_draw),
                    ("away", core.away.name, None, max(1.0 - p_home - p_draw, 0.0)),
                ]
            return [
                ("home", core.home.name, None, p_home),
                ("away", core.away.name, None, 1 - p_home),
            ]
        if market == "spread":
            if cfg.fixed_spread is not None:
                favoured = core.home_mean >= core.away_mean
                home_line = -cfg.fixed_spread if favoured else cfg.fixed_spread
            else:
                home_line = _half_line(-state.margin + offset)
            p_home = min(max(outlook.home_covers(home_line), 0.0), 1.0)
            return [
                ("home", core.home.name, home_line, p_home),
                ("away", core.away.name, -home_line, 1 - p_home),
            ]
        # A total is never quoted below what has already been scored.
        line = max(state.home_score + state.away_score + 0.5, _half_line(state.total + offset))
        p_over = min(max(outlook.over(line), 0.0), 1.0)
        return [("over", "Over", line, p_over), ("under", "Under", line, 1 - p_over)]

    def _prices(
        self,
        fair: _Fair,
        book: _Book,
        scope: str,
        market: str,
        bucket: int,
    ) -> list[OddsOutcome]:
        """Fair probabilities -> book prices: a stable per-book lean, tick noise, then margin."""
        clipped = [min(max(p, 0.02), 0.98) for *_, p in fair]
        noisy = [
            p
            * math.exp(
                0.012 * self._z("lean", book.key, i, scope, market)
                + 0.005 * self._z("tick", book.key, i, scope, market, bucket)
            )
            for i, p in enumerate(clipped)
        ]
        norm = sum(noisy)
        hold = book.hold * (1.5 if len(fair) == 3 else 1.0)
        return [
            OddsOutcome(
                key=key,
                name=name,
                line=line,
                price_american=_american_from_implied(q / norm * (1 + hold)),
            )
            for (key, name, line, _), q in zip(fair, noisy, strict=True)
        ]

    def _priced(self, core: _EventCore, market: str, book: _Book, at: datetime) -> _Priced:
        """The book's prices at ``at`` and whether the market was already decided then."""
        fair = self._fair(core, market, book, self._state(core, at))
        bucket = int(at.timestamp() // book.update_interval)
        return _Priced(
            outcomes=self._prices(fair, book, core.id, market, bucket),
            decided=max(p for *_, p in fair) > _DECIDED_PROBABILITY,
        )

    def _quote(self, core: _EventCore, market: str, book: _Book, at: datetime) -> list[OddsOutcome]:
        return self._priced(core, market, book, at).outcomes

    def _offer_status(
        self, scope: str, market: str, book: _Book, status: str, now: datetime
    ) -> str:
        if self._u("avail", scope, market, book.key) < 0.05:
            return "unavailable"
        if status == "final":
            return "closed"
        if status == "live":
            window = int(now.timestamp() // 300)
            if self._u("susp-live", scope, market, book.key, window) < 0.15:
                return "suspended"
        elif self._u("susp", scope, market, book.key) < 0.05:
            return "suspended"
        return "open"

    def _last_updated(
        self, scope: str, market: str, book: _Book, core: _EventCore, now: datetime
    ) -> datetime:
        if now >= core.end:
            return core.start
        jitter = self._u("age", scope, market, book.key, int(now.timestamp() // 15))
        if book.stale:
            return now - timedelta(seconds=1500 + 1500 * jitter)
        if now < core.start:
            return now - timedelta(seconds=20 + 400 * jitter)
        # In play a book's pricing model requotes every few seconds, so an in-play price
        # is at most a few seconds behind the game.
        lag = timedelta(seconds=0.5 + 2.5 * jitter)
        changed = self._state(core, now).score_updated_at or core.start
        # After the score changes (the start counts) a book needs a moment to requote.
        # Until it has, its quote is its last one from before the change.
        reaction = timedelta(
            seconds=1 + 5 * self._u("react", scope, market, book.key, changed.timestamp())
        )
        if now < changed + reaction:
            return changed - lag
        return max(now - lag, changed + reaction)

    def get_odds(self, event_id: str, market: str) -> list[OddsSnapshot]:
        core = self._core_by_id(event_id)
        if core is None or market not in core.cfg.markets:
            return []
        now = self.now()
        event_status = self._state(core, now).status
        snapshots: list[OddsSnapshot] = []
        for book in _BOOKS:
            status = self._offer_status(core.id, market, book, event_status, now)
            record_id = f"odds:{core.id}:{market}:{book.key}"
            if status == "unavailable":
                snapshots.append(
                    OddsSnapshot(
                        event_id=core.id,
                        market=market,
                        sportsbook_id=book.key,
                        status="unavailable",
                        last_updated=None,
                        outcomes=[],
                        **self._prov(record_id, now),
                    )
                )
                continue
            updated = self._last_updated(core.id, market, book, core, now)
            quote_at = core.start - timedelta(seconds=1) if status == "closed" else updated
            priced = self._priced(core, market, book, quote_at)
            if status == "open" and priced.decided:
                # The book has taken the market down: the result is all but settled.
                status = "suspended"
            snapshots.append(
                OddsSnapshot(
                    event_id=core.id,
                    market=market,
                    sportsbook_id=book.key,
                    status=status,  # type: ignore[arg-type]
                    last_updated=updated,
                    outcomes=priced.outcomes,
                    **self._prov(record_id, now),
                )
            )
        return snapshots

    def get_line_history(self, event_id: str, market: str) -> list[LineSeries]:
        core = self._core_by_id(event_id)
        if core is None or market not in core.cfg.markets:
            return []
        now = self.now()
        event_status = self._state(core, now).status
        closing = core.start - timedelta(seconds=1)
        horizon = closing if event_status == "final" else now
        first = (horizon - timedelta(hours=HISTORY_HOURS)).replace(
            minute=0, second=0, microsecond=0
        ) + timedelta(hours=1)
        series: list[LineSeries] = []
        for book in _BOOKS:
            status = self._offer_status(core.id, market, book, event_status, now)
            if status == "unavailable":
                continue
            last = (
                closing
                if event_status == "final"
                else self._last_updated(core.id, market, book, core, now)
            )
            stamps: list[datetime] = []
            cursor = first
            while cursor < last:
                stamps.append(cursor)
                cursor += timedelta(hours=1)
            stamps.append(last)
            per_outcome: dict[str, tuple[str, list[LinePoint]]] = {}
            for stamp in stamps:
                for outcome in self._quote(core, market, book, stamp):
                    name, points = per_outcome.setdefault(outcome.key, (outcome.name, []))
                    points.append(
                        LinePoint(
                            timestamp=stamp,
                            price_american=outcome.price_american,
                            line=outcome.line,
                        )
                    )
            for key, (name, points) in per_outcome.items():
                series.append(
                    LineSeries(
                        event_id=core.id,
                        market=market,
                        sportsbook_id=book.key,
                        outcome_key=key,
                        outcome_name=name,
                        points=points,
                        **self._prov(f"hist:{core.id}:{market}:{book.key}:{key}", now),
                    )
                )
        return series

    # ---------------------------------------------------------------- players
    def _adjusted_mean(self, player: Player, market: str, core: _EventCore) -> float:
        spec = self._player_specs[player.id][market]
        is_home = core.home.id == player.team_id
        opponent = core.away if is_home else core.home
        defence = min(max(1 + 0.07 * self._z("def", opponent.id, market), 0.85), 1.15)
        return spec.mean * defence * (1.03 if is_home else 0.97)

    def _stat_value(self, player: Player, market: str, core: _EventCore) -> float:
        spec = self._player_specs[player.id][market]
        mean = self._adjusted_mean(player, market, core)
        return float(
            max(0, round(mean + spec.game_sd * self._z("stat", player.id, core.id, market)))
        )

    def get_player_game_log(self, player_id: str, limit: int | None = None) -> list[GameLogEntry]:
        player = self._players.get(player_id)
        if player is None:
            return []
        now = self.now()
        team = self._teams[player.team_id]
        wanted = GAME_LOG_GAMES if limit is None else min(limit, GAME_LOG_GAMES)
        entries: list[GameLogEntry] = []
        offset = 0
        while len(entries) < wanted and offset < GAME_LOG_GAMES + 5:
            core = self._team_core_on(team, now.date() - timedelta(days=offset))
            offset += 1
            if core.end > now:
                continue
            is_home = core.home.id == team.id
            entries.append(
                GameLogEntry(
                    player_id=player.id,
                    event_id=core.id,
                    game_time=core.start,
                    opponent_team_id=(core.away if is_home else core.home).id,
                    is_home=is_home,
                    stats={m: self._stat_value(player, m, core) for m in player.prop_markets},
                    **self._prov(f"log:{player.id}:{core.id}", now),
                )
            )
        return entries

    def get_prop_offers(self, player_id: str, market: str | None = None) -> list[PropOffer]:
        player = self._players.get(player_id)
        if player is None:
            return []
        now = self.now()
        core = self._next_core_for_team(player.team_id, now)
        if core is None:
            return []
        event_status = self._state(core, now).status
        offers: list[PropOffer] = []
        for prop_market in player.prop_markets:
            if market and prop_market != market:
                continue
            spec = self._player_specs[player.id][prop_market]
            mean = self._adjusted_mean(player, prop_market, core)
            scope = f"{core.id}:{player.id}"
            for book in _BOOKS:
                status = self._offer_status(scope, prop_market, book, event_status, now)
                record_id = f"prop:{scope}:{prop_market}:{book.key}"
                if status == "unavailable":
                    offers.append(
                        PropOffer(
                            player_id=player.id,
                            event_id=core.id,
                            market=prop_market,
                            sportsbook_id=book.key,
                            status="unavailable",
                            last_updated=None,
                            **self._prov(record_id, now),
                        )
                    )
                    continue
                line = _half_line(mean)
                if mean >= 12:
                    pick = self._u("propoff", scope, prop_market, book.key)
                    line += -1.0 if pick < 0.15 else 1.0 if pick > 0.85 else 0.0
                p_over = _NORMAL.cdf((mean - line) / spec.game_sd)
                updated = self._last_updated(scope, prop_market, book, core, now)
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
                        player_id=player.id,
                        event_id=core.id,
                        market=prop_market,
                        sportsbook_id=book.key,
                        status=status,  # type: ignore[arg-type]
                        last_updated=updated,
                        line=line,
                        over_american=over.price_american,
                        under_american=under.price_american,
                        **self._prov(record_id, now),
                    )
                )
        return offers
