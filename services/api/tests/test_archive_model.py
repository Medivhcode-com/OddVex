"""The snapshot archive against a reference model (P0.1).

Each scenario drives the capture job over a small fictional schedule that it controls
completely (:class:`World`, on the synthetic :class:`ControlledProvider` and its
fictional books): quotes that change, stay unchanged for a long time, disappear and come
back; a player with two games inside the window; games that are delayed, moved, hidden
and shown again, live and final; missed and failed passes; the flag off and on; the
storage cap and the file ceiling reached and released; bets by three users with
different books, recorded at any moment with a placement time exactly at a capture, one
microsecond either side, in a gap or long after the last quote; the retention prune
and the keep horizon, both shortened so that a scenario crosses them several times; and
prunes that are cut short after any number of their deletes, by an error the pass
records or by the worker being killed, with a bet recorded late on a pruned game before
the next prune finishes the work. A second kind of scenario (``STAY_SEEDS``) has a keep
period longer than five props look-backs plus the retention, and one game that is listed
three times, each stay more than three look-backs after the one before: once the prune
has reduced the third stay nothing of the second is left, and the props read has to know
from the game's kept first and last captures that a time in the second stay is inside it
(review round 5 found the read answering ``captured`` there without the game's offers).

Beside the archive the scenario keeps a **truth log** that is never pruned: at every
capture pass, a frozen copy of what the provider showed (:class:`Shot`).

**Safety**, checked at many times T after every step, for all four read paths (odds as
of T, props as of T, status as of T, placement prices of every stored bet): whenever the
archive answers ``captured`` or ``priced``, the answer equals what the live ``Board``
computes on the truth log's frozen provider state for the latest successful capture at or
before T (same books, same line, staleness judged at T), and no row returned was
captured after T. Whenever it does not, it says so with a named reason and returns no
quotes; ``archive_gap`` and ``not_captured`` are given only when they are true.

**Liveness**, so that "always refuse" does not pass: right after a successful capture a
read at that time is ``captured`` and matches the truth; and for a game no prune has
started on, or a time after its last one, the answer is exactly the truth's. That is all
the model asks once a prune has reached a game: from then on ``archive_pruned`` is
accepted for any time up to that prune, and a game named in ``pruned_event_ids`` is not
compared. So the model would not notice a prune that kept nothing, or a read that
refused every kept capture of a pruned game; that the first, closing and last captures
and the bet anchors survive and are served is what the hand-written tests in
``test_archive_prune.py`` and ``test_archive_placement.py`` check.

The scenarios are random but deterministic: a fixed seed each, the provider's clock only
(no wall clock, no sleeps). The default run is the seeds in ``DEFAULT_SEEDS``; a longer
one:

    ODDVEX_ARCHIVE_MODEL_SCENARIOS=300 .venv/bin/python -m pytest tests/test_archive_model.py

``ODDVEX_ARCHIVE_MODEL_SEED`` sets the first seed (default 1), to replay one scenario.
"""

from __future__ import annotations

import os
import random
from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select

from oddvex_api.archive import prune as prune_module
from oddvex_api.archive.capture import PassReport, StatusRecord, capture_pass, capture_status
from oddvex_api.archive.placement import placement_prices
from oddvex_api.archive.service import archived_odds, archived_props, archived_status
from oddvex_api.board import Board
from oddvex_api.cache import InMemoryTTLCache
from oddvex_api.config import Settings
from oddvex_api.db import (
    ArchivedEvent,
    ArchivedProp,
    Bet,
    BetLeg,
    SnapshotRun,
    User,
    new_id,
)
from oddvex_api.flags import service as flags
from oddvex_api.providers import Event, OddsOutcome, OddsSnapshot, Player, PropOffer, Score
from oddvex_api.schemas import price_out

from .archive_support import ArchiveEnv, archive_env
from .fakes import ControlledProvider

__all__ = ["archive_env"]

#: The default run of the first kind: nine scenarios. What they catch, checked again on
#: the round-6 code with each defect made on purpose in a copy of the source
#: (docs/features/p0-1.md, "Tests"): 1, 12, 40 and 64 the prune of review round 4 (a
#: game's odds, prop and event rows deleted with a commit each, cut in between); 3 and 40
#: the props look-back that did not cover the daily refresh; 368 the props keep-horizon
#: check without the look-back (56 did, until the capture rule of round 6 changed what
#: that scenario stores); all but 614 reads that ignore a prune that has started but not
#: finished; most of them the props gap limit's boundary and a live game that never
#: leaves scope; 12, 322 and 614 a props capture that takes a game without the odds
#: capture of its pass. 322 and 368 are the two seeds at which review round 4 first saw
#: the look-back defect. 614 is where this model, in round 5, found the prune deleting
#: the fresh prop rows of a game that a props capture had back in scope before any odds
#: capture did. Three use the 36-hour horizon the product ships with: 12, 56 and 64.
DEFAULT_SEEDS = (1, 3, 12, 40, 56, 64, 322, 368, 614)
#: The default scenarios with a game listed three times (module docstring). 1 and 4 catch
#: the round-5 defect made on purpose in a copy of the source (the props read choosing
#: the games to check by a row near T). 21 is where this model, in round 6, found the
#: closing offers of a game's first stay served after the game had been reduced a second
#: time: on PostgreSQL only, where the file ceiling makes passes skip that capture on
#: SQLite; there it is one more scenario.
DEFAULT_STAY_SEEDS = (1, 4, 21)
SCENARIOS = int(os.environ.get("ODDVEX_ARCHIVE_MODEL_SCENARIOS", "0"))
FIRST_SEED = int(os.environ.get("ODDVEX_ARCHIVE_MODEL_SEED", "1"))
SEEDS = (
    tuple(range(FIRST_SEED, FIRST_SEED + SCENARIOS))
    if SCENARIOS or "ODDVEX_ARCHIVE_MODEL_SEED" in os.environ
    else DEFAULT_SEEDS
)
STAY_SEEDS = (
    tuple(range(FIRST_SEED, FIRST_SEED + SCENARIOS))
    if SCENARIOS or "ODDVEX_ARCHIVE_MODEL_SEED" in os.environ
    else DEFAULT_STAY_SEEDS
)

START = datetime(2026, 3, 14, 12, 0, tzinfo=UTC)
US = timedelta(microseconds=1)
TURN = timedelta(seconds=120)  # the worker loop
MARKETS = ("moneyline", "spread", "total")
PRICES = (-180, -160, -150, -140, -130, -125, -120, -115, -110, -105, 100, 105, 110, 120, 130, 150)
SPREADS = (-1.5, -2.5, 1.5)
TOTALS = (5.5, 6.0, 6.5)
#: Each user's books (provider sportsbook keys). The third holds none.
USER_BOOKS: tuple[tuple[str, ...], ...] = (
    ("northline", "summit"),
    ("cardinal", "blueharbor", "kestrel"),
    (),
)
REFUSALS = {"not_captured", "archive_gap", "archive_pruned"}
#: A status record's content: (status, source, reported_at, provider id).
type StatusValue = tuple[str, str, datetime | None, str]
#: The scope rule's grace for a game still ``upcoming`` after its start, in hours
#: (``capture.UPCOMING_GRACE_HOURS``), written out here so the model is its own statement.
GRACE_HOURS = 6
#: The same for a game still ``live`` after its start (``capture.LIVE_GRACE_HOURS``).
LIVE_GRACE_HOURS = 24
#: Hours the props read looks back beyond the capture horizon (``view.PROP_GAME_HOURS``).
PROP_GAME_HOURS = 12
#: An unchanged offer is stored again at the first props capture after its row is this
#: many hours old (``capture.PROP_REFRESH_HOURS``); the props read looks back at least
#: this far plus its gap limit.
PROP_REFRESH_HOURS = 24


class Divergence(AssertionError):
    """The archive answered something the reference model does not."""


class Killed(BaseException):
    """The worker is killed in the middle of a prune (a deploy replaces its container):
    no handler of the pass runs, nothing is recorded, open work is rolled back."""


class Dropped(ConnectionError):
    """The prune's connection drops: an error the pass catches and records."""


# ------------------------------------------------------------------ the world
class World(ControlledProvider):
    """A fictional schedule the scenario controls completely. Teams, players and
    sportsbooks are the synthetic provider's; games, quotes and prop offers are the
    scenario's own."""

    def __init__(self, rng: random.Random) -> None:
        super().__init__(now=START)
        self.rng = rng
        self.book_ids = [book.id for book in super().list_sportsbooks()]
        teams = [team.id for team in super().list_teams("nba")][:4]
        self.teams = teams
        #: Three players; the first one's team plays two games inside the window.
        self.roster: list[Player] = [
            ControlledProvider.list_players(self, team_id=team)[0] for team in teams[:3]
        ]
        self.games: dict[str, Event] = {}
        self.hidden: set[str] = set()
        self.quotes: dict[tuple[str, str], dict[str, OddsSnapshot]] = {}
        self.offers: dict[str, dict[tuple[str, str, str], PropOffer]] = {
            player.id: {} for player in self.roster
        }
        #: Kinds whose provider calls fail on the next pass: "odds", "props".
        self.broken: set[str] = set()
        self.serial = 0

    # ---------------------------------------------------------- the provider
    def list_events(
        self, league: str | None = None, status: str | None = None, on_date: date | None = None
    ) -> list[Event]:
        return [
            event
            for event in self.games.values()
            if event.id not in self.hidden
            and (league is None or event.league == league)
            and (status is None or event.status == status)
            and (on_date is None or event.start_time.date() == on_date)
        ]

    def get_event(self, event_id: str) -> Event | None:
        return None if event_id in self.hidden else self.games.get(event_id)

    def get_odds(self, event_id: str, market: str) -> list[OddsSnapshot]:
        if "odds" in self.broken:
            raise ConnectionError("feed dropped")
        return self.shown_quotes(event_id, market)

    def shown_quotes(self, event_id: str, market: str) -> list[OddsSnapshot]:
        """In the provider's sportsbook order, as the synthetic provider lists them."""
        books = self.quotes.get((event_id, market), {})
        return [
            books[book].model_copy(update={"fetched_at": self.current})
            for book in self.book_ids
            if book in books
        ]

    def list_players(
        self, league: str | None = None, team_id: str | None = None, query: str | None = None
    ) -> list[Player]:
        return [
            player
            for player in self.roster
            if (league is None or player.league == league)
            and (team_id is None or player.team_id == team_id)
        ]

    def get_prop_offers(self, player_id: str, market: str | None = None) -> list[PropOffer]:
        if "props" in self.broken:
            raise ConnectionError("feed dropped")
        return self.shown_offers(player_id, market)

    def shown_offers(self, player_id: str, market: str | None = None) -> list[PropOffer]:
        offers = self.offers.get(player_id, {})
        order = {book: i for i, book in enumerate(self.book_ids)}
        return [
            offers[key].model_copy(update={"fetched_at": self.current})
            for key in sorted(offers, key=lambda k: (k[0], k[1], order[k[2]]))
            if market is None or key[1] == market
        ]

    # ------------------------------------------------------------- building
    def add_game(self, home: str, away: str, start: datetime) -> str:
        self.serial += 1
        event_id = f"model_game_{self.serial}"
        self.games[event_id] = Event(
            provider="test",
            provider_id=event_id,
            fetched_at=self.current,
            id=event_id,
            league="nba",
            home_team_id=home,
            away_team_id=away,
            start_time=start,
            status="upcoming",
            markets=list(MARKETS),
        )
        for market in MARKETS:
            self.quotes[(event_id, market)] = {}
            for book in self.rng.sample(self.book_ids, self.rng.randint(3, 5)):
                self.set_quote(event_id, market, book)
        for player in self.roster:
            if player.team_id in (home, away):
                for market in player.prop_markets[:2]:
                    for book in self.rng.sample(self.book_ids, 2):
                        self.set_offer(player.id, event_id, market, book)
        return event_id

    def set_quote(self, event_id: str, market: str, book: str, status: str = "open") -> None:
        rng = self.rng
        outcomes: list[tuple[str, float | None, int]]
        if market == "moneyline":
            outcomes = [("home", None, rng.choice(PRICES)), ("away", None, rng.choice(PRICES))]
        elif market == "spread":
            line = rng.choice(SPREADS)
            outcomes = [("home", line, rng.choice(PRICES)), ("away", -line, rng.choice(PRICES))]
        else:
            line = rng.choice(TOTALS)
            outcomes = [("over", line, rng.choice(PRICES)), ("under", line, rng.choice(PRICES))]
        self.quotes[(event_id, market)][book] = OddsSnapshot(
            provider="test",
            provider_id=f"{event_id}:{market}:{book}",
            fetched_at=self.current,
            event_id=event_id,
            market=market,
            sportsbook_id=book,
            status=status,  # type: ignore[arg-type]
            last_updated=self.current - timedelta(seconds=rng.randint(5, 40)),
            outcomes=[
                OddsOutcome(key=key, name=key.title(), line=line, price_american=price)
                for key, line, price in outcomes
            ],
        )

    def set_offer(self, player_id: str, event_id: str, market: str, book: str) -> None:
        rng = self.rng
        self.offers[player_id][(event_id, market, book)] = PropOffer(
            provider="test",
            provider_id=f"{player_id}:{event_id}:{market}:{book}",
            fetched_at=self.current,
            player_id=player_id,
            event_id=event_id,
            market=market,
            sportsbook_id=book,
            status=rng.choice(("open", "open", "open", "suspended")),  # type: ignore[arg-type]
            last_updated=self.current - timedelta(seconds=rng.randint(5, 40)),
            line=rng.choice((18.5, 19.5, 20.5, 21.5)),
            over_american=rng.choice(PRICES),
            under_american=rng.choice(PRICES),
        )

    # ------------------------------------------------------------- changing
    def mutate(self) -> None:
        """A few random changes: what a provider's feed does between two passes."""
        rng = self.rng
        now = self.current
        for event_id, event in list(self.games.items()):
            roll = rng.random()
            if event.status == "upcoming":
                if now >= event.start_time and roll < 0.5:
                    self.games[event_id] = event.model_copy(
                        update={
                            "status": "live",
                            "score": Score(home=0, away=0),
                            "score_updated_at": now,
                            "period_text": "Q1",
                        }
                    )
                elif roll < 0.03:  # delayed: still inside the window
                    later = event.start_time + timedelta(hours=rng.randint(1, 3))
                    self.games[event_id] = event.model_copy(update={"start_time": later})
                elif roll < 0.045:  # moved: out of the window, back in two days
                    later = event.start_time + timedelta(days=2)
                    self.games[event_id] = event.model_copy(update={"start_time": later})
            elif event.status == "live":
                if roll < 0.15 and event.score is not None:
                    self.games[event_id] = event.model_copy(
                        update={
                            "score": Score(home=event.score.home + 2, away=event.score.away),
                            "score_updated_at": now,
                        }
                    )
                elif roll < 0.25:
                    self.games[event_id] = event.model_copy(
                        update={"status": "final", "period_text": "Final", "score_updated_at": None}
                    )
            if rng.random() < 0.03:  # the provider forgets the game for a while
                self.hidden ^= {event_id}
        open_games = [e.id for e in self.games.values() if e.status != "final"]
        # Most books refresh a quote without moving it (a new ``last_updated``); the rest
        # leave it as it is, for minutes or for days, until it is stale.
        for event_id in open_games:
            for market in MARKETS:
                for book, snap in list(self.quotes[(event_id, market)].items()):
                    if rng.random() < 0.3:
                        self.quotes[(event_id, market)][book] = snap.model_copy(
                            update={"last_updated": now - timedelta(seconds=rng.randint(5, 40))}
                        )
        for _ in range(rng.randint(0, 3)):
            if not open_games:
                break
            event_id = rng.choice(open_games)
            market = rng.choice(MARKETS)
            books = self.quotes[(event_id, market)]
            roll = rng.random()
            if roll < 0.55:  # a book reprices, or first quotes, or comes back
                self.set_quote(event_id, market, rng.choice(self.book_ids))
            elif roll < 0.75 and books:  # a book stops quoting
                del books[rng.choice(sorted(books))]
            elif roll < 0.9 and books:  # a book suspends
                self.set_quote(event_id, market, rng.choice(sorted(books)), status="suspended")
            # else: nothing changes; the quote ages
        for player in self.roster:
            offers = self.offers[player.id]
            roll = rng.random()
            games = [
                e.id
                for e in self.games.values()
                if e.status != "final" and player.team_id in (e.home_team_id, e.away_team_id)
            ]
            if roll < 0.25 and games:
                self.set_offer(
                    player.id,
                    rng.choice(games),
                    rng.choice(player.prop_markets[:2]),
                    rng.choice(self.book_ids),
                )
            elif roll < 0.35 and offers:
                del offers[rng.choice(sorted(offers))]

    def freeze(self, settings: Settings) -> Shot:
        return Shot(
            at=self.current,
            games={e.id: e for e in self.list_events()},
            quotes={
                (event_id, market): self.shown_quotes(event_id, market)
                for (event_id, market) in self.quotes
            },
            offers={player.id: self.shown_offers(player.id) for player in self.roster},
            stale_pregame=settings.stale_pregame_seconds,
            stale_live=settings.stale_live_seconds,
            horizon=timedelta(hours=settings.snapshot_horizon_hours),
        )


# ------------------------------------------------------------- the truth log
@dataclass(frozen=True)
class Shot:
    """What the provider showed at one capture pass, frozen."""

    at: datetime
    games: dict[str, Event]
    quotes: dict[tuple[str, str], list[OddsSnapshot]]
    offers: dict[str, list[PropOffer]]
    stale_pregame: int
    stale_live: int
    horizon: timedelta

    def in_scope(self, event_id: str) -> Event | None:
        """The capture's scope rule, stated here on its own: a live game that started at
        most a day ago, or an upcoming one that starts within the horizon and started at
        most six hours ago."""
        event = self.games.get(event_id)
        if event is None:
            return None
        if event.status == "live":
            started = self.at - timedelta(hours=LIVE_GRACE_HOURS) <= event.start_time
            return event if started else None
        if event.status == "upcoming" and (
            self.at - timedelta(hours=GRACE_HOURS) <= event.start_time <= self.at + self.horizon
        ):
            return event
        return None


class Frozen:
    """A provider that shows one :class:`Shot` and tells the time it is asked about."""

    def __init__(self, world: World, shot: Shot, now: datetime) -> None:
        self.world, self.shot, self._now = world, shot, now
        self.name, self.data_mode = world.name, world.data_mode

    def now(self) -> datetime:
        return self._now

    def get_odds(self, event_id: str, market: str) -> list[OddsSnapshot]:
        return self.shot.quotes.get((event_id, market), [])

    def get_event(self, event_id: str) -> Event | None:
        return self.shot.games.get(event_id)

    def __getattr__(self, name: str) -> Any:  # reference data: teams, sportsbooks, leagues
        if name in ("list_sportsbooks", "list_leagues", "list_teams", "get_team", "get_player"):
            return getattr(self.world, name)
        raise AttributeError(name)


class TruthBoard(Board):
    """The live board on a frozen shot, judged at T. The one documented difference of the
    archive's board, written here independently: a game captured as ``upcoming`` whose
    start time has passed at T is judged by the live stale threshold."""

    def freshness_status(self, event: Event) -> str:
        if event.status == "upcoming" and self.now >= event.start_time:
            return "live"
        return event.status


@dataclass
class Truth:
    """Every successful capture's shot, never pruned, and what the prunes have reached."""

    odds: list[Shot] = field(default_factory=list)
    props: list[Shot] = field(default_factory=list)
    #: Status records as the provider reported them, per (event, team, player, kind):
    #: each time the record changed, when and to what. An unchanged record is no news.
    status: dict[tuple[str, str | None, str | None, str], list[tuple[datetime, StatusValue]]] = (
        field(default_factory=dict)
    )
    status_times: list[datetime] = field(default_factory=list)
    prune_cutoff: datetime | None = None
    keep_cutoff: datetime | None = None
    #: Per game a prune has started on: when the last one did. From then on the game's
    #: rows captured up to that time may be only the kept ones (they are, once a prune
    #: has finished the game; a prune that was cut short may not have reached it); rows
    #: captured later (it came back) are all there.
    reduced: dict[str, datetime] = field(default_factory=dict)

    @staticmethod
    def latest(shots: list[Shot], as_of: datetime) -> Shot | None:
        index = bisect_right([shot.at for shot in shots], as_of)
        return shots[index - 1] if index else None

    def odds_coverage(
        self, event_id: str, as_of: datetime, max_gap: int
    ) -> tuple[str, Shot | None, Event | None]:
        shot = self.latest(self.odds, as_of)
        if shot is None:
            return "not_captured", None, None
        if (as_of - shot.at).total_seconds() > max_gap:
            return "archive_gap", shot, None
        event = shot.in_scope(event_id)
        return ("captured" if event is not None else "not_captured"), shot, event

    def last_capture_of(self, event_id: str) -> datetime | None:
        for shot in reversed(self.odds):
            if shot.in_scope(event_id) is not None:
                return shot.at
        return None

    def pruned(self, now: datetime, settings: Settings, event_ids: list[str]) -> None:
        """A prune started at ``now``, whether or not it got to the end. Its cutoffs never
        move back; it handles every game whose last capture is before the cutoff."""
        cutoff = now - timedelta(days=settings.snapshot_retention_days)
        keep = now - timedelta(days=settings.snapshot_keep_days)
        self.prune_cutoff = max(cutoff, self.prune_cutoff or cutoff)
        self.keep_cutoff = max(keep, self.keep_cutoff or keep)
        for event_id in event_ids:
            last = self.last_capture_of(event_id)
            if last is not None and last < self.prune_cutoff:
                self.reduced[event_id] = now

    def board(self, world: World, shot: Shot, as_of: datetime, settings: Settings) -> TruthBoard:
        thresholds = settings.model_copy(
            update={
                "stale_pregame_seconds": shot.stale_pregame,
                "stale_live_seconds": shot.stale_live,
            }
        )
        return TruthBoard(Frozen(world, shot, as_of), thresholds, InMemoryTTLCache())  # type: ignore[arg-type]

    def reported(self, at: datetime, batch: list[StatusRecord]) -> None:
        self.status_times.append(at)
        for record in batch:
            assert record.event_id is not None
            key = (record.event_id, record.team_id, record.player_id, record.kind)
            value = (record.status, record.source, record.reported_at, record.provider_id)
            changes = self.status.setdefault(key, [])
            if not changes or changes[-1][1] != value:
                changes.append((at, value))

    def status_entries(
        self, event_id: str, as_of: datetime
    ) -> dict[tuple[str | None, str | None, str], tuple[datetime, StatusValue]]:
        """Per (team, player, kind) of the event: the latest change at or before T."""
        found: dict[tuple[str | None, str | None, str], tuple[datetime, StatusValue]] = {}
        for (event, team, player, kind), changes in self.status.items():
            if event != event_id:
                continue
            earlier = [change for change in changes if change[0] <= as_of]
            if earlier:
                found[(team, player, kind)] = earlier[-1]
        return found


# -------------------------------------------------------------- the scenario
@dataclass
class StoredBet:
    bet_id: str
    user: int
    placed_at: datetime


class Scenario:
    def __init__(self, seed: int, env: ArchiveEnv, *, stays: bool = False) -> None:
        self.seed = seed
        #: The second kind of scenario: one game listed three times (``run_stays``).
        self.stays = stays
        self.rng = random.Random(f"stays of {seed}" if stays else seed)
        rng = self.rng
        self.env = env
        #: A second stream, for everything about cutting prunes short: the first one's
        #: draws, and so the world of every seed, are the same with and without it.
        self.cuts = random.Random(f"cuts of {seed}")
        self.world = World(rng)
        env.provider = self.world
        keep_days = rng.choice((2, 3))
        props_interval = rng.choice((360, 720, 3600))
        horizon_hours = rng.choice((12, 36))
        if horizon_hours == 36:
            # The props read looks back 48 hours and answers nothing once that reaches
            # past the keep horizon: a day more, so that it answers at all, and for
            # pruned games too.
            keep_days += 1
        if stays:
            # The shortest look-back (a day and the props gap limit), and a keep period
            # of nine days: longer than five look-backs plus the retention, and longer
            # than the scenario, so the game's first capture is never swept.
            horizon_hours, keep_days = 12, 9
        self.base = env.settings.model_copy(
            update={
                "snapshot_retention_days": 1,
                "snapshot_keep_days": keep_days,
                "snapshot_props_interval_seconds": props_interval,
                "snapshot_horizon_hours": horizon_hours,
            }
        )
        assert self.base.snapshot_settings_problem() is None
        self.settings = self.base
        self.truth = Truth()
        self.flag_on = True
        self.bets: list[StoredBet] = []
        self.users: list[str] = []
        self.checks = {"captured": 0, "refused": 0, "priced": 0, "cannot_price": 0}
        self.reports: list[PassReport] = []
        self.step = 0
        #: Prunes cut short, by kind, and whether one still waits for a prune to finish.
        self.cut_short = {"dropped": 0, "killed": 0}
        self.unfinished = False
        #: ``run_stays``: per stay of the game listed three times, the props captures that
        #: had an offer of its first player on it; and what the reads of those moments
        #: answered about the game after the last prune ("exact" or "named").
        self.stay_captures: list[list[datetime]] = []
        self.stay_answers: list[set[str]] = []
        with env.session_factory() as db:
            for i in range(len(USER_BOOKS)):
                user = User(
                    email=f"user{i}@example.test",
                    password_hash="x",
                    display_name=f"User {i}",
                    age_confirmed_at=START,
                )
                db.add(user)
                db.flush()
                self.users.append(user.id)
            db.commit()

    # ------------------------------------------------------------ the clock
    @property
    def now(self) -> datetime:
        return self.world.current

    @property
    def props_gap(self) -> timedelta:
        """A props capture covers this long: two props intervals and one worker turn."""
        return timedelta(seconds=2 * self.settings.snapshot_props_interval_seconds + 120)

    @property
    def reach(self) -> timedelta:
        """How far the props read looks back, stated here on its own: as far as an open
        offer's latest row can be, which is the horizon and the game, and never less
        than the age at which an unchanged offer is stored again plus the gap limit."""
        return max(
            timedelta(hours=self.settings.snapshot_horizon_hours + PROP_GAME_HOURS),
            timedelta(hours=PROP_REFRESH_HOURS) + self.props_gap,
        )

    def fail(self, where: str, as_of: datetime, message: str) -> Divergence:
        kind = "stays seed" if self.stays else "seed"
        return Divergence(
            f"{kind} {self.seed}, step {self.step}, now {self.now.isoformat()}, "
            f"{where} as of {as_of.isoformat()}: {message}"
        )

    # ---------------------------------------------------------------- steps
    def run(self) -> None:
        rng = self.rng
        world = self.world
        teams = world.teams
        # The first player's team has two games inside the window from the start.
        world.add_game(teams[0], teams[1], self.now + timedelta(hours=rng.randint(1, 4)))
        world.add_game(teams[0], teams[2], self.now + timedelta(hours=rng.randint(6, 11)))
        for burst in range(rng.randint(5, 7)):
            if burst:
                home, away = rng.sample(teams, 2)
                world.add_game(home, away, self.now + timedelta(hours=rng.randint(1, 30)))
            for _ in range(rng.randint(6, 12)):
                self.turn()
            self.sweep()
            # Capture is down for a while (a deploy, a crash, the flag off): the clock
            # crosses the retention and keep horizons.
            later = self.now + timedelta(hours=rng.choice((3, 9, 20, 26, 31, 47)))
            if self.truth.props and rng.random() < 0.35:
                # Or it comes back a few minutes before the offers one of the last props
                # captures stored are a day old: an unchanged offer is stored again only
                # at the first props capture after that, so the next burst reads rows
                # that are as old as a row gets.
                stored = rng.choice(self.truth.props[-8:]).at
                day_on = stored + timedelta(
                    hours=PROP_REFRESH_HOURS, seconds=-rng.randint(120, 900)
                )
                if day_on > self.now:
                    later = day_on
            world.current = later
        self.turn()
        self.sweep(last=True)

    def run_stays(self) -> None:
        """One game is listed three times: postponed twice and listed again under the
        same id, the second stay more than three look-backs after the first and the
        third more than two after the second, with capture down in between. Around it
        the feed, the passes, the bets and the cut-short prunes go on as in ``run``.

        The prune of the first pass back reduces the stay before; a day after the third
        stay the game is reduced a last time and holds its first capture (first stay)
        and its closing and last captures (third stay) only. After every stay, and at
        the end, the props of the game's player are asked at the captures of every stay
        so far, and the odds of the game around them."""
        rng = self.rng
        world = self.world
        teams = world.teams
        player = world.roster[0]
        game = world.add_game(teams[0], teams[1], self.now + timedelta(hours=rng.randint(2, 4)))
        world.add_game(teams[0], teams[2], self.now + timedelta(hours=rng.randint(6, 11)))

        def list_again() -> None:
            """The provider lists the game as upcoming, for a start a few hours on."""
            world.hidden.discard(game)
            world.games[game] = world.games[game].model_copy(
                update={
                    "start_time": self.now + timedelta(hours=rng.randint(2, 4)),
                    "status": "upcoming",
                    "score": None,
                    "score_updated_at": None,
                    "period_text": None,
                }
            )

        for stay in range(3):
            if stay:
                # Listed again: a new start time a few hours on, and offers on it.
                list_again()
                for market in player.prop_markets[:2]:
                    for book in rng.sample(world.book_ids, 2):
                        world.set_offer(player.id, game, market, book)
                home, away = rng.sample(teams, 2)
                world.add_game(home, away, self.now + timedelta(hours=rng.randint(1, 30)))
            began = self.now

            def with_the_game(began: datetime = began) -> list[datetime]:
                """This stay's props captures that had an offer of the player on the game."""
                return [
                    shot.at
                    for shot in self.truth.props
                    if shot.at > began
                    and shot.in_scope(game) is not None
                    and any(offer.event_id == game for offer in shot.offers[player.id])
                ]

            for _ in range(rng.randint(6, 12)):
                self.turn()
            # The feed may have hidden the game or withdrawn the offers, or the passes
            # were missed or skipped at a limit: the stay lasts until one props capture
            # has had them (hourly props get five more chances at most).
            for _ in range(150):
                if with_the_game():
                    break
                if world.freeze(self.settings).in_scope(game) is None:
                    list_again()  # the feed had hidden, moved or finished it
                if not any(key[0] == game for key in world.offers[player.id]):
                    world.set_offer(player.id, game, player.prop_markets[0], world.book_ids[0])
                self.turn()
            # Postponed: a start a month on is outside the window, listed or not.
            world.games[game] = world.games[game].model_copy(
                update={"start_time": self.now + timedelta(days=30)}
            )
            for _ in range(rng.randint(2, 4)):
                self.turn()
            self.stay_captures.append(with_the_game())
            assert self.stay_captures[-1], f"stays seed {self.seed}: stay {stay} was not captured"
            self.sweep()
            self.ask_the_stays(game, player.id)
            # Capture is down until the game is listed again (or, after the third stay,
            # until its rows have aged out).
            away_for = (3, 2, 1)[stay] * self.reach + timedelta(hours=rng.randint(2, 8))
            world.current = self.now + away_for
        for _ in range(rng.randint(2, 4)):
            self.turn()
        # Until a prune has run since (passes are missed, the flag is off for a while).
        for _ in range(45):
            if self.truth.reduced.get(game, START) > self.stay_captures[-1][-1]:
                break
            self.turn()
        self.sweep(last=True)
        self.stay_answers = self.ask_the_stays(game, player.id)

    def ask_the_stays(self, game: str, player_id: str) -> list[set[str]]:
        """The props of the game's player at the props captures of each stay (the capture
        itself, a minute and a few minutes after it), and the game's odds then. Per stay,
        what the props answers said about the game: "exact" (compared with the truth)
        or "named" (as pruned)."""
        said: list[set[str]] = []
        for captures in self.stay_captures:
            said.append(set())
            for at in captures[:2] + captures[-1:]:
                for seconds in (0, 60, 400):
                    as_of = min(at + timedelta(seconds=seconds), self.now)
                    with self.env.session_factory() as db:
                        answer = archived_props(
                            db, self.world, self.settings, player_id, None, as_of
                        )
                    if self.check_props(player_id, as_of) == "captured":
                        named = game in answer.pruned_event_ids
                        said[-1].add("named" if named else "exact")
                    self.check_odds(game, self.rng.choice(MARKETS), as_of)
        return said

    def turn(self) -> None:
        """One turn of the worker loop: the feed moves, sometimes something else happens,
        then the capture script runs (or is missed)."""
        rng = self.rng
        self.step += 1
        self.world.current += TURN
        self.world.mutate()
        roll = rng.random()
        if roll < 0.04:
            self.set_flag(not self.flag_on)
        elif roll < 0.08:
            self.world.broken = {rng.choice(("odds", "props"))}
        elif roll < 0.11:
            self.settings = self.base.model_copy(update={"snapshot_max_bytes": 1})
        elif roll < 0.14:
            self.settings = self.base.model_copy(update={"snapshot_max_disk_bytes": 1})
        elif roll < 0.17:
            pregame = rng.choice((300, 900, 1800))
            self.base = self.base.model_copy(update={"stale_pregame_seconds": pregame})
            self.settings = self.base
        if rng.random() < 0.3:
            self.place_bet()
        if rng.random() < 0.2:
            self.capture_status()
        if rng.random() < 0.1:
            return  # a missed pass
        self.capture()
        self.settings = self.base  # the cap and the ceiling are released
        if not self.flag_on and rng.random() < 0.5:
            self.set_flag(True)
        self.spot_check()

    def set_flag(self, enabled: bool) -> None:
        with self.env.session_factory() as db:
            flags.set_flag(db, "snapshot_archive", enabled)
            db.commit()
        self.flag_on = enabled

    def capture(self) -> None:
        env, world = self.env, self.world
        shot = world.freeze(self.settings)
        # Now and then the pass's prune, if one is due, is cut short after some of its
        # deletes: by an error the pass records, or by the worker being killed.
        cut_after = self.cuts.randint(0, 14) if self.cuts.random() < 0.4 else None
        kill = self.cuts.random() < 0.5
        deletes = 0
        real_delete = prune_module._delete_ids

        def delete_or_stop(session: Any, model: Any, ids: Any) -> int:
            nonlocal deletes
            if cut_after is not None and deletes == cut_after:
                raise Killed() if kill else Dropped("connection lost")
            deletes += 1
            return real_delete(session, model, ids)

        prune_module._delete_ids = delete_or_stop  # type: ignore[assignment]
        report: PassReport | None = None
        try:
            report = capture_pass(env.engine, world, self.settings)
        except Killed:
            pass
        finally:
            prune_module._delete_ids = real_delete
        broken, world.broken = world.broken, set()
        # What the pass recorded, read from its runs: a killed pass returns nothing.
        with env.session_factory() as db:
            ran: dict[str, list[str]] = {}
            for kind, status in db.execute(
                select(SnapshotRun.kind, SnapshotRun.status)
                .where(SnapshotRun.captured_at == self.now, SnapshotRun.provider == world.name)
                .order_by(SnapshotRun.id)
            ):
                ran.setdefault(kind, []).append(status)
        if not self.flag_on:
            assert report is not None and report.enabled is False
            assert report.odds is None and report.prune is None
            assert not {"odds", "props", "prune"} & set(ran)
            return
        if report is not None:
            self.reports.append(report)
            for kind in ("odds", "props"):
                summary = getattr(report, kind)
                assert ran.get(kind, []) == ([] if summary is None else [summary.status])
                if summary is None:
                    continue
                if report.full:
                    assert summary.status == "skipped_full", (kind, summary)
                elif kind == "props" and kind in broken:
                    assert summary.status == "failed", (kind, summary)
                if summary.status == "ok":
                    assert summary.captured_at == shot.at
            # The capture rule, stated here on its own: a props capture never runs
            # without the odds capture of its pass, so both froze the same list of games.
            if report.props is not None:
                assert report.odds is not None, "a props capture without an odds capture"
                assert report.odds.status == report.props.status or (
                    report.props.status == "failed" and report.odds.status == "ok"
                ), (report.odds, report.props)
        for kind, shots in (("odds", self.truth.odds), ("props", self.truth.props)):
            if ran.get(kind) == ["ok"]:
                shots.append(shot)
        # A prune says how far it will go before it deletes anything (its ``started``
        # run). From then on the truth counts every game it may reach as reduced.
        prune = ran.get("prune", [])
        if prune:
            assert prune[0] == "started", prune
            self.truth.pruned(self.now, self.settings, sorted(world.games))
            if prune == ["started", "ok"]:
                assert report is not None and report.prune is not None
                finished_a_cut, self.unfinished = self.unfinished, False
                if finished_a_cut:
                    self.audit()  # the prune after a cut one: every answer again
            else:
                # Cut short: recorded as failed, or (killed) not at all.
                assert prune == (["started"] if report is None else ["started", "failed"]), prune
                self.cut_short["killed" if report is None else "dropped"] += 1
                self.unfinished = True
                self.place_late_bet()
                self.audit()
        elif report is None:
            raise AssertionError("the pass was killed outside a prune")
        # Liveness: right after a successful capture, a read at that time is captured.
        if ran.get("odds") == ["ok"]:
            scope = [event_id for event_id in shot.games if shot.in_scope(event_id) is not None]
            for event_id in self.rng.sample(scope, min(len(scope), 2)):
                answer = self.check_odds(event_id, self.rng.choice(MARKETS), self.now)
                if answer != "captured":
                    raise self.fail(
                        f"odds of {event_id}", self.now, f"just captured, answered {answer}"
                    )
        if ran.get("props") == ["ok"]:
            player = self.rng.choice(world.roster)
            answer = self.check_props(player.id, self.now)
            if answer != "captured":
                raise self.fail(
                    f"props of {player.id}", self.now, f"just captured, answered {answer}"
                )

    def audit(self) -> None:
        """Right after a prune was cut short, and again after the prune that finishes its
        work: every game around its own captures, every player, every stored bet. Drawn
        from the second stream."""
        rng = self.cuts
        world = self.world
        asked = self.times(3, rng)
        for event_id in sorted(world.games):
            mine = [shot.at for shot in self.truth.odds if shot.in_scope(event_id) is not None]
            around = mine[:1] + mine[-1:] + rng.sample(mine, min(len(mine), 3))
            around = [at + timedelta(seconds=rng.choice((0, 0, 60, 700))) for at in around]
            for as_of in asked[:1] + around:
                self.check_odds(event_id, rng.choice(MARKETS), min(as_of, self.now))
        for player in world.roster:
            for as_of in asked:
                self.check_props(player.id, as_of)
        for bet in self.bets:
            self.check_bet(bet)

    def place_late_bet(self) -> None:
        """A bet recorded late (an import), between a prune that was cut short and the one
        that finishes its work: on a game that prune had started on, placed a moment
        after one of the game's captures."""
        rng = self.cuts
        reduced = sorted(self.truth.reduced)
        if not reduced:
            return
        event_id = rng.choice(reduced)
        shots = [shot for shot in self.truth.odds if shot.in_scope(event_id) is not None]
        if not shots:
            return
        shot = rng.choice(shots)
        market = rng.choice(MARKETS)
        quoted = [
            (outcome.key, outcome.line)
            for snap in shot.quotes.get((event_id, market), [])
            for outcome in snap.outcomes
        ]
        if not quoted:
            return
        side, line = rng.choice(quoted)
        placed_at = min(shot.at + timedelta(seconds=rng.choice((0, 10, 130, 700))), self.now)
        self.store_bet(
            rng.randrange(len(USER_BOOKS)), placed_at, [(0, event_id, market, side, line)]
        )

    def capture_status(self) -> None:
        rng = self.rng
        world = self.world
        games = [e for e in world.games.values() if e.status != "final"]
        if not games:
            return
        batch = []
        for event in rng.sample(games, min(len(games), rng.randint(1, 2))):
            for player in world.roster:
                if player.team_id not in (event.home_team_id, event.away_team_id):
                    continue
                if rng.random() < 0.3:
                    continue  # not every record is in every batch
                for kind, values in (
                    ("lineup", ("expected", "confirmed")),
                    ("injury", ("questionable", "doubtful", "out", "probable")),
                ):
                    batch.append(
                        StatusRecord(
                            provider=world.name,
                            provider_id=f"{kind}:{player.id}:{event.id}",
                            fetched_at=self.now,
                            event_id=event.id,
                            player_id=player.id,
                            kind=kind,  # type: ignore[arg-type]
                            status=rng.choice(values),  # type: ignore[arg-type]
                            source="Fictional Lineup Desk",
                            # Often the same report as before: then it is no news.
                            reported_at=rng.choice(
                                (event.start_time - timedelta(hours=2), self.now - TURN)
                            ),
                        )
                    )
        if not batch:
            return
        with self.env.session_factory() as db:
            run = capture_status(db, world, self.settings, batch)
        if not self.flag_on:
            assert run is None
            return
        assert run is not None and run.status == "ok"
        self.truth.reported(self.now, batch)
        for event_id in {record.event_id for record in batch if record.event_id}:
            if self.check_status(event_id, self.now) != "captured":
                raise self.fail(f"status of {event_id}", self.now, "just captured, not captured")

    def place_bet(self) -> None:
        """A bet is recorded now, with a placement time at or before now: exactly at a
        capture, one microsecond either side, a while after one, in a gap or long after
        the last quote."""
        rng = self.rng
        world = self.world
        runs = [shot.at for shot in self.truth.odds]
        choices = [self.now, self.now - timedelta(seconds=rng.randint(1, 100_000))]
        if runs:
            at = rng.choice(runs[-40:])
            choices += [
                at,
                at - US,
                at + US,
                at + timedelta(seconds=rng.randint(1, 120)),
                at + timedelta(seconds=rng.randint(1, 120)),
                at + timedelta(seconds=rng.randint(1, 839)),
                at + timedelta(seconds=840),
                at + timedelta(seconds=840) + US,
                runs[-1] + timedelta(seconds=rng.randint(841, 5000)),
            ]
        placed_at = min(rng.choice(choices), self.now)
        user = rng.randrange(len(USER_BOOKS))
        legs: list[tuple[int, str, str, str | None, float | None]] = []
        for position in range(rng.choice((1, 1, 1, 2))):
            event_id = rng.choice(sorted(world.games))
            market = rng.choice(MARKETS)
            if rng.random() < 0.1:
                legs.append((position, event_id, "player_points", None, None))
                continue
            # Usually an outcome and a line some book quotes now; sometimes any line.
            quoted = [
                (outcome.key, outcome.line)
                for snap in world.shown_quotes(event_id, market)
                for outcome in snap.outcomes
            ]
            if quoted and rng.random() < 0.8:
                side, line = rng.choice(quoted)
            elif market == "moneyline":
                side, line = rng.choice(("home", "away")), None
            elif market == "spread":
                side, line = rng.choice(("home", "away")), rng.choice(SPREADS)
            else:
                side, line = rng.choice(("over", "under")), rng.choice(TOTALS)
            legs.append((position, event_id, market, side, line))
        self.store_bet(user, placed_at, legs)

    def store_bet(
        self,
        user: int,
        placed_at: datetime,
        legs: list[tuple[int, str, str, str | None, float | None]],
    ) -> None:
        with self.env.session_factory() as db:
            bet = Bet(
                id=new_id(),
                user_id=self.users[user],
                bet_type="straight" if len(legs) == 1 else "parlay",
                sportsbook="Northline",
                stake=Decimal("10.00"),
                odds_decimal=Decimal("1.909091"),
                placed_at=placed_at,
            )
            for position, event_id, market, outcome, line in legs:
                bet.legs.append(
                    BetLeg(
                        position=position,
                        selection=f"{outcome} {line}",
                        market=market,
                        event_id=event_id,
                        outcome_key=outcome,
                        line=None if line is None else Decimal(str(line)),
                        odds_decimal=Decimal("1.909091"),
                    )
                )
            db.add(bet)
            db.commit()
            self.bets.append(StoredBet(bet.id, user, placed_at))

    # --------------------------------------------------------------- checks
    def times(self, count: int, rng: random.Random | None = None) -> list[datetime]:
        """Times worth asking about: captures and the microsecond either side, the edge of
        the gap limit, the prune cutoffs, placement times, and anywhere at all."""
        rng = rng or self.rng
        truth = self.truth
        pool: list[datetime] = [self.now, START - timedelta(hours=1)]
        for shots in (truth.odds, truth.props):
            for shot in rng.sample(shots, min(len(shots), 6)):
                pool += [shot.at, shot.at - US, shot.at + US]
                pool.append(shot.at + timedelta(seconds=rng.randint(1, 840)))
                pool += [shot.at + timedelta(seconds=840), shot.at + timedelta(seconds=841)]
        # The last moment a props capture covers, and the first it does not: where an
        # offer's stored row is oldest when it is read.
        for shot in rng.sample(truth.props, min(len(truth.props), 4)):
            pool += [shot.at + self.props_gap, shot.at + self.props_gap + US]
        for at in rng.sample(truth.status_times, min(len(truth.status_times), 3)):
            pool += [at, at - US]
        for cutoff in (truth.prune_cutoff, truth.keep_cutoff):
            if cutoff is not None:
                pool += [cutoff, cutoff - US, cutoff + timedelta(seconds=rng.randint(0, 5000))]
        pool += [bet.placed_at for bet in rng.sample(self.bets, min(len(self.bets), 3))]
        span = int((self.now - START).total_seconds())
        pool += [START + timedelta(seconds=rng.randint(0, max(span, 1))) for _ in range(3)]
        return [min(at, self.now) for at in rng.sample(pool, min(len(pool), count))]

    def spot_check(self) -> None:
        """After every step: each read path once, at a time worth asking about."""
        rng = self.rng
        world = self.world
        (as_of,) = self.times(1)
        self.check_odds(rng.choice(sorted(world.games)), rng.choice(MARKETS), as_of)
        self.check_props(rng.choice(world.roster).id, as_of)
        self.check_status(rng.choice(sorted(world.games)), as_of)
        if self.bets:
            self.check_bet(rng.choice(self.bets))

    def sweep(self, *, last: bool = False) -> None:
        """After every burst: every game around its own first, last and one other capture
        (the first and the last are among those the prune keeps), every game, player and
        status at a few more times, and the stored bets (all of them at the end)."""
        rng = self.rng
        world = self.world
        self.offers_stand_beside_event_rows()
        asked = self.times(3)
        for event_id in sorted(world.games):
            mine = [shot.at for shot in self.truth.odds if shot.in_scope(event_id) is not None]
            around = mine[:1] + mine[-1:] + rng.sample(mine, min(len(mine), 1))
            around = [at + timedelta(seconds=rng.choice((0, 0, 60, 700))) for at in around]
            for as_of in asked[:2] + around:
                self.check_odds(event_id, rng.choice(MARKETS), min(as_of, self.now))
            self.check_status(event_id, asked[0])
        edges = [
            min(shot.at + self.props_gap, self.now)
            for shot in self.truth.props[-1:]
            + rng.sample(self.truth.props, min(len(self.truth.props), 2))
        ]
        for player in world.roster:
            for as_of in asked + edges:
                self.check_props(player.id, as_of)
        bets = self.bets if last else rng.sample(self.bets, min(len(self.bets), 6))
        for bet in bets:
            self.check_bet(bet)

    def offers_stand_beside_event_rows(self) -> None:
        """What the prune and the reads rely on: every stored open offer has its game's
        event row of the same capture time (a props capture takes a game only together
        with the odds capture of its pass)."""
        with self.env.session_factory() as db:
            held = set(db.execute(select(ArchivedEvent.event_id, ArchivedEvent.captured_at)))
            alone = [
                (event_id, at)
                for event_id, at in db.execute(
                    select(ArchivedProp.event_id, ArchivedProp.captured_at)
                    .where(ArchivedProp.status != "unavailable")
                    .distinct()
                )
                if (event_id, at) not in held and event_id not in self.truth.reduced
            ]
        if alone:
            raise self.fail(
                "stored offers", self.now, f"open offers with no event row beside them: {alone}"
            )

    def may_say_pruned(self, event_id: str, shot: Shot | None, as_of: datetime) -> bool:
        """Whether ``archive_pruned`` is an honest answer for the event at T: T is within
        the gap limit of the keep horizon or before it (capture runs are thinned there),
        or a prune has started on the game and the latest capture at or before T is not
        later than that. Anywhere else the archive must answer exactly what the truth
        says."""
        keep = self.truth.keep_cutoff
        limit = timedelta(seconds=self.settings.snapshot_max_gap_seconds)
        if keep is not None and as_of - limit < keep:
            return True
        reduced = self.truth.reduced.get(event_id)
        return reduced is not None and shot is not None and shot.at <= reduced

    def check_odds(self, event_id: str, market: str, as_of: datetime) -> str:
        where = f"odds of {event_id} {market}"
        with self.env.session_factory() as db:
            answer = archived_odds(db, self.world, self.settings, event_id, market, as_of)
        status = answer.coverage.status
        expected, shot, event = self.truth.odds_coverage(
            event_id, as_of, self.settings.snapshot_max_gap_seconds
        )
        if answer.requested_as_of != as_of:
            raise self.fail(where, as_of, "answered for another time")
        if status != "captured":
            if status not in REFUSALS or answer.quotes or answer.odds is not None:
                raise self.fail(where, as_of, f"refusal {status} with quotes or no named reason")
            if status != expected and not (
                status == "archive_pruned" and self.may_say_pruned(event_id, shot, as_of)
            ):
                raise self.fail(where, as_of, f"answered {status}, the truth is {expected}")
            self.checks["refused"] += 1
            return status
        if expected != "captured" or shot is None or event is None:
            raise self.fail(where, as_of, f"answered captured, the truth is {expected}")
        if answer.coverage.captured_at != shot.at:
            raise self.fail(where, as_of, f"captured from {answer.coverage.captured_at}")
        found = [
            (
                quote.sportsbook.key,
                quote.status,
                quote.last_updated,
                [(o.key, o.line, o.price.american) for o in quote.outcomes],
            )
            for quote in answer.quotes
            # A book that stopped quoting is kept as an ``unavailable`` row without
            # outcomes; the provider simply no longer lists it.
            if not (quote.status == "unavailable" and not quote.outcomes)
        ]
        if any(quote.captured_at > as_of for quote in answer.quotes):
            raise self.fail(where, as_of, "a quote captured after T")
        truth_quotes = [
            (
                snap.sportsbook_id,
                snap.status,
                snap.last_updated,
                [(o.key, o.line, o.price_american) for o in snap.outcomes],
            )
            for snap in shot.quotes.get((event_id, market), [])
        ]
        if found != truth_quotes:
            raise self.fail(where, as_of, f"quotes {found}, the provider showed {truth_quotes}")
        board = self.truth.board(self.world, shot, as_of, self.settings)
        truth_odds = _without_gone_books(board.event_odds(event, market).model_dump(mode="json"))
        if answer.odds is None:
            raise self.fail(where, as_of, "captured without the comparison")
        mine = _without_gone_books(answer.odds.model_dump(mode="json"))
        if mine != truth_odds:
            raise self.fail(where, as_of, f"comparison {mine}, the live board gives {truth_odds}")
        self.checks["captured"] += 1
        return status

    def check_props(self, player_id: str, as_of: datetime) -> str:
        where = f"props of {player_id}"
        settings = self.settings
        with self.env.session_factory() as db:
            answer = archived_props(db, self.world, settings, player_id, None, as_of)
        status = answer.coverage.status
        gap = int(self.props_gap.total_seconds())
        shot = Truth.latest(self.truth.props, as_of)
        if shot is None:
            expected = "not_captured"
        elif (as_of - shot.at).total_seconds() > gap:
            expected = "archive_gap"
        else:
            expected = "captured"
        keep = self.truth.keep_cutoff
        reach = self.reach
        if status != "captured":
            if status not in REFUSALS or answer.offers or answer.pruned_event_ids:
                raise self.fail(where, as_of, f"refusal {status} with offers or no named reason")
            # ``archive_pruned`` only where the look-back reaches past the keep horizon.
            horizon = keep is not None and as_of - reach < keep
            if status != expected and not (status == "archive_pruned" and horizon):
                raise self.fail(where, as_of, f"answered {status}, the truth is {expected}")
            self.checks["refused"] += 1
            return status
        if expected != "captured" or shot is None:
            raise self.fail(where, as_of, f"answered captured, the truth is {expected}")
        if answer.coverage.captured_at != shot.at:
            raise self.fail(where, as_of, f"captured from {answer.coverage.captured_at}")
        if any(offer.captured_at > as_of for offer in answer.offers):
            raise self.fail(where, as_of, "an offer captured after T")
        named = set(answer.pruned_event_ids)
        found: dict[str, set[tuple[Any, ...]]] = {}
        for offer in answer.offers:
            if offer.status == "unavailable" and offer.line is None:
                continue  # a withdrawn offer of a game that still has others
            found.setdefault(offer.event_id, set()).add(
                (
                    offer.sportsbook.key,
                    offer.market,
                    offer.status,
                    offer.last_updated,
                    offer.line,
                    offer.over.american if offer.over else None,
                    offer.under.american if offer.under else None,
                )
            )
        truth_offers: dict[str, set[tuple[Any, ...]]] = {}
        for offer in shot.offers.get(player_id, []):
            if shot.in_scope(offer.event_id) is None:
                continue
            truth_offers.setdefault(offer.event_id, set()).add(
                (
                    offer.sportsbook_id,
                    offer.market,
                    offer.status,
                    offer.last_updated,
                    offer.line,
                    offer.over_american,
                    offer.under_american,
                )
            )
        if named & set(found):
            raise self.fail(where, as_of, f"offers of a game named as pruned: {named & set(found)}")
        for event_id in named:
            # A game is named only once a prune has started on it.
            if event_id not in self.truth.reduced:
                raise self.fail(where, as_of, f"{event_id} named as pruned, but it was not pruned")
        for event_id in (set(found) | set(truth_offers)) - named:
            if found.get(event_id, set()) != truth_offers.get(event_id, set()):
                raise self.fail(
                    where,
                    as_of,
                    f"offers of {event_id}: {sorted(found.get(event_id, set()), key=str)}, the "
                    f"provider showed {sorted(truth_offers.get(event_id, set()), key=str)}",
                )
        self.checks["captured"] += 1
        return status

    def check_status(self, event_id: str, as_of: datetime) -> str:
        """Each record stands alone and is kept for the keep period: an entry is the
        record's latest change at or before T; a record whose latest change is older than
        the keep horizon may be missing, and no other."""
        where = f"status of {event_id}"
        with self.env.session_factory() as db:
            answer = archived_status(db, self.world, self.settings, event_id, as_of)
        status = answer.coverage.status
        truth = self.truth.status_entries(event_id, as_of)
        keep = self.truth.keep_cutoff
        kept = {key: change for key, change in truth.items() if keep is None or change[0] >= keep}
        if answer.coverage.kept_from != keep:
            raise self.fail(where, as_of, f"kept_from {answer.coverage.kept_from}, not {keep}")
        if status != "captured":
            expected = "archive_pruned" if keep is not None and as_of < keep else "not_captured"
            if answer.entries or status != expected:
                raise self.fail(where, as_of, f"answered {status}, expected {expected}")
            if kept:
                raise self.fail(where, as_of, f"answered {status}, the truth has {kept}")
            self.checks["refused"] += 1
            return status
        found = {
            (entry.team_id, entry.player_id, entry.kind): (
                entry.captured_at,
                (entry.status, entry.source, entry.reported_at, entry.provider_id),
            )
            for entry in answer.entries
        }
        if any(entry.captured_at > as_of for entry in answer.entries):
            raise self.fail(where, as_of, "an entry captured after T")
        # The stored row is the change itself, or, once that row has passed the keep
        # horizon and gone, the same record stored again at a later capture.
        wrong = {
            key: value
            for key, value in found.items()
            if key not in truth or truth[key][1] != value[1] or value[0] < truth[key][0]
        }
        missing = {key: change for key, change in kept.items() if key not in found}
        if wrong or missing or not found:
            raise self.fail(
                where, as_of, f"entries {found}, the provider reported {truth} (kept from {keep})"
            )
        self.checks["captured"] += 1
        return status

    def check_bet(self, stored: StoredBet) -> None:
        books = list(USER_BOOKS[stored.user])
        settings = self.settings
        as_of = stored.placed_at
        with self.env.session_factory() as db:
            bet = db.get(Bet, stored.bet_id)
            assert bet is not None
            legs = placement_prices(db, self.world, settings, bet, books)
            wanted = [
                (leg.event_id, leg.market, leg.outcome_key, leg.line)
                for leg in db.scalars(
                    select(BetLeg).where(BetLeg.bet_id == bet.id).order_by(BetLeg.position)
                )
            ]
        if len(legs) != len(wanted):
            raise self.fail(f"bet {stored.bet_id}", as_of, "a leg was left unanswered")
        for leg, (event_id, market, outcome, line) in zip(legs, wanted, strict=True):
            where = f"bet leg {event_id} {market} {outcome} {line} (books {books})"
            if market not in MARKETS or outcome is None:
                if (leg.status, leg.reason) != ("cannot_price", "leg_not_structured"):
                    raise self.fail(where, as_of, f"unstructured leg answered {leg.reason}")
                continue
            assert event_id is not None
            expected, shot, event = self.truth.odds_coverage(
                event_id, as_of, settings.snapshot_max_gap_seconds
            )
            answered = leg.status == "priced" or leg.best_overall is not None
            if leg.reason in REFUSALS:
                if answered or leg.best_at_your_books is not None:
                    raise self.fail(where, as_of, f"refusal {leg.reason} with a price")
                if leg.reason != expected and not (
                    leg.reason == "archive_pruned" and self.may_say_pruned(event_id, shot, as_of)
                ):
                    raise self.fail(where, as_of, f"answered {leg.reason}, truth {expected}")
                self.checks["cannot_price"] += 1
                continue
            if expected != "captured" or shot is None or event is None:
                raise self.fail(
                    where, as_of, f"answered {leg.status} {leg.reason}, the truth is {expected}"
                )
            board = self.truth.board(self.world, shot, as_of, settings)
            market_line = (
                None if market == "moneyline" else float(line) if line is not None else None
            )
            overall = board.best_price(event, market, outcome, line=market_line)
            yours = (
                board.best_price(event, market, outcome, line=market_line, books=set(books))
                if books
                else None
            )
            quotes = {snap.sportsbook_id: snap for snap in shot.quotes.get((event_id, market), [])}
            for name, mine, theirs in (
                ("best_overall", leg.best_overall, overall),
                ("best_at_your_books", leg.best_at_your_books, yours),
            ):
                if (mine is None) != (theirs is None):
                    raise self.fail(where, as_of, f"{name}: {mine}, the live board gives {theirs}")
                if mine is None or theirs is None:
                    continue
                if (
                    mine.price != price_out(theirs.price)
                    or mine.sportsbook.key != theirs.sportsbook.key
                    or mine.line != theirs.line
                    or mine.last_updated != quotes[theirs.sportsbook.key].last_updated
                    or mine.captured_at > as_of
                ):
                    raise self.fail(where, as_of, f"{name}: {mine}, the live board gives {theirs}")
            if yours is not None:
                reason = None
            elif overall is not None:
                reason = "none_at_your_books" if books else "books_unknown"
            else:
                # Open, fully priced quotes for the outcome on the leg's line existed, but
                # every one was stale at the placement time; or none existed.
                stale = any(
                    status == "open"
                    and len(prices) >= 2
                    and is_stale
                    and any(
                        o.key == outcome and (market == "moneyline" or o.line == market_line)
                        for o in snap.outcomes
                    )
                    for snap, status, is_stale, prices in board.quote_rows(event, market)
                )
                reason = "stale_at_placement" if stale else "no_usable_quote"
            expected_status = "priced" if yours is not None else "cannot_price"
            if (leg.status, leg.reason) != (expected_status, reason):
                raise self.fail(
                    where,
                    as_of,
                    f"answered {leg.status} {leg.reason}, the live board gives "
                    f"{expected_status} {reason}",
                )
            self.checks["priced" if yours is not None else "cannot_price"] += 1


def _without_gone_books(odds: dict[str, Any]) -> dict[str, Any]:
    """The comparison without books that stopped quoting: the archive lists such a book as
    ``unavailable`` with no outcomes, the provider no longer lists it. Neither counts
    toward best price, consensus or hold."""
    odds["books"] = [
        book
        for book in odds["books"]
        if not (book["status"] == "unavailable" and not book["outcomes"])
    ]
    return odds


# ------------------------------------------------------------------- the tests
@pytest.mark.parametrize("seed", STAY_SEEDS)
def test_a_game_listed_three_times_agrees_with_the_reference_model(
    archive_env: ArchiveEnv, seed: int
) -> None:
    scenario = Scenario(seed, archive_env, stays=True)
    scenario.run_stays()
    first, second, third = scenario.stay_captures
    print(
        f"stays seed {seed}: props captures with the game per stay "
        f"{[len(stay) for stay in scenario.stay_captures]}, answers about the game after "
        f"the last prune {[sorted(said) for said in scenario.stay_answers]}, "
        f"prunes cut short {scenario.cut_short}, checks {scenario.checks}"
    )
    # The scenario reached its class: three stays captured with the player's offers, the
    # second more than three look-backs after the first and more than two before the
    # third, inside the keep period, and the prune has reduced the game after the third.
    settings, truth = scenario.settings, scenario.truth
    assert first and second and third
    reach = scenario.reach
    assert second[0] - first[-1] > 3 * reach and third[0] - second[-1] > 2 * reach
    keep = timedelta(days=settings.snapshot_keep_days)
    assert keep > 5 * reach + timedelta(days=settings.snapshot_retention_days)
    assert truth.keep_cutoff is not None and truth.keep_cutoff + reach < first[0]
    assert truth.reduced["model_game_1"] > third[-1]
    # And the read answered ``captured`` for the second stay's captures, so the game's
    # offers there were either compared with the truth or named as pruned.
    assert scenario.stay_answers[1], scenario.stay_answers


@pytest.mark.parametrize("seed", SEEDS)
def test_the_archive_agrees_with_the_reference_model(archive_env: ArchiveEnv, seed: int) -> None:
    scenario = Scenario(seed, archive_env)
    scenario.run()
    print(f"seed {seed}: prunes cut short {scenario.cut_short}, checks {scenario.checks}")
    # The scenario did something: captures, prunes, and answers of both kinds.
    assert len(scenario.truth.odds) >= 5
    with archive_env.session_factory() as db:
        kinds = set(db.scalars(select(SnapshotRun.kind).distinct()))
    assert {"odds", "props", "prune"} <= kinds
    assert scenario.checks["captured"] > 20 and scenario.checks["refused"] > 20, scenario.checks
