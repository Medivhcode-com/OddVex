"""Reading the archive as of a time T.

``coverage_at`` says whether the archive covers an event at T. :class:`ArchiveView` is a
read-only :class:`SportsDataProvider` that answers from rows captured at or before T, so
the live :class:`Board` code computes best price and consensus as of T unchanged
(``board_at`` gives it the stale thresholds that were in force at capture, and judges an
archived ``upcoming`` event whose start time had passed at T by the live threshold). No
method ever returns a row captured after T.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from ..board import Board
from ..cache import InMemoryTTLCache
from ..config import Settings
from ..db import ArchivedEvent, ArchivedOdds, ArchivedProp, SnapshotRun
from ..providers import (
    Event,
    GameLogEntry,
    League,
    LineSeries,
    OddsOutcome,
    OddsSnapshot,
    Player,
    PropOffer,
    ProviderHealth,
    Score,
    Sportsbook,
    SportsDataProvider,
    Team,
)

CoverageStatus = Literal["captured", "not_captured", "archive_gap", "archive_pruned"]
#: Hours a game lasts at most, for the props look-back (:func:`prop_lookback`).
PROP_GAME_HOURS = 12


@dataclass(frozen=True)
class Coverage:
    """How the archive covers one event at T.

    Let R be the latest ``ok`` odds capture run at or before T (runs are kept 400 days).

    - ``captured``: R is at most ``snapshot_max_gap_seconds`` before T and the archive
      holds the event's row from R. Only then is anything priced.
    - ``archive_gap``: no ``ok`` odds capture within the limit before T.
    - ``archive_pruned``: R ran while the event was in scope, but its rows from R were
      pruned; or no run is left from before T and T is past the keep horizon.
    - ``not_captured``: before the first capture, or the event was not in scope at R.

    ``snapshot`` is the latest event row at or before T, whatever the status.
    """

    status: CoverageStatus
    snapshot: ArchivedEvent | None = None

    @property
    def captured_at(self) -> datetime | None:
        return self.snapshot.captured_at if self.snapshot is not None else None

    @property
    def run_id(self) -> int | None:
        return self.snapshot.run_id if self.snapshot is not None else None


def _latest_odds_run_at(session: Session, provider_name: str, as_of: datetime) -> datetime | None:
    return session.scalar(
        select(func.max(SnapshotRun.captured_at)).where(
            SnapshotRun.kind == "odds",
            SnapshotRun.provider == provider_name,
            SnapshotRun.status == "ok",
            SnapshotRun.captured_at <= as_of,
        )
    )


def _newest_prune(session: Session) -> tuple[datetime, datetime] | None:
    """(captured_at, prune_cutoff) of the newest successful prune run."""
    newest = session.execute(
        select(SnapshotRun.captured_at, SnapshotRun.prune_cutoff)
        .where(SnapshotRun.kind == "prune", SnapshotRun.status == "ok")
        .order_by(SnapshotRun.captured_at.desc())
        .limit(1)
    ).first()
    if newest is None or newest.prune_cutoff is None:
        return None
    return newest.captured_at, newest.prune_cutoff


def _runs_pruned(session: Session, as_of: datetime, settings: Settings) -> bool:
    """With no capture run left from before T: whether T is before the newest prune's keep
    horizon (the runs themselves were deleted) rather than before the first capture."""
    newest = _newest_prune(session)
    if newest is None:
        return False
    horizon = newest[0] - timedelta(
        days=max(settings.snapshot_keep_days, settings.snapshot_retention_days)
    )
    return as_of < horizon


def _pruned_while_in_scope(
    session: Session, provider_name: str, event_id: str, run_at: datetime, settings: Settings
) -> bool:
    """Whether the event's row from the run at ``run_at`` existed and was pruned.

    The prune handles an event only once all of its rows are older than the cutoff, and
    keeps its last capture, so the event was pruned exactly when its latest kept row is
    before the newest prune cutoff, and it was in scope at ``run_at`` when that run falls
    between ``snapshot_horizon_hours`` before its start and its last capture."""
    last = session.execute(
        select(ArchivedEvent.captured_at, ArchivedEvent.start_time)
        .where(ArchivedEvent.provider == provider_name, ArchivedEvent.event_id == event_id)
        .order_by(ArchivedEvent.captured_at.desc())
        .limit(1)
    ).first()
    if last is None or run_at > last.captured_at:
        return False
    if run_at < last.start_time - timedelta(hours=settings.snapshot_horizon_hours):
        return False
    newest = _newest_prune(session)
    return newest is not None and last.captured_at < newest[1]


def coverage_at(
    session: Session, provider_name: str, event_id: str, as_of: datetime, settings: Settings
) -> Coverage:
    snapshot = session.scalars(
        select(ArchivedEvent)
        .where(
            ArchivedEvent.provider == provider_name,
            ArchivedEvent.event_id == event_id,
            ArchivedEvent.captured_at <= as_of,
        )
        .order_by(ArchivedEvent.captured_at.desc())
        .limit(1)
    ).first()
    run_at = _latest_odds_run_at(session, provider_name, as_of)
    if run_at is None:
        pruned = _runs_pruned(session, as_of, settings)
        return Coverage("archive_pruned" if pruned else "not_captured", snapshot)
    if as_of - run_at > timedelta(seconds=settings.snapshot_max_gap_seconds):
        return Coverage("archive_gap", snapshot)
    # Captured only from the latest capture at or before T, never from an older row
    # (for example another bet's kept anchor) when that capture's row is gone.
    if snapshot is not None and snapshot.captured_at >= run_at:
        return Coverage("captured", snapshot)
    if _pruned_while_in_scope(session, provider_name, event_id, run_at, settings):
        return Coverage("archive_pruned", snapshot)
    return Coverage("not_captured", snapshot)


def latest_odds_rows(
    session: Session, provider_name: str, event_id: str, market: str, at_or_before: datetime
) -> list[ArchivedOdds]:
    """Per book, the latest row for one event and market captured at or before the time."""
    o = ArchivedOdds
    newest = (
        select(o.sportsbook_id, func.max(o.captured_at).label("at"))
        .where(
            o.provider == provider_name,
            o.event_id == event_id,
            o.market == market,
            o.captured_at <= at_or_before,
        )
        .group_by(o.sportsbook_id)
        .subquery()
    )
    return list(
        session.scalars(
            select(o).join(
                newest,
                and_(
                    o.provider == provider_name,
                    o.event_id == event_id,
                    o.market == market,
                    o.sportsbook_id == newest.c.sportsbook_id,
                    o.captured_at == newest.c.at,
                ),
            )
        )
    )


def prop_lookback(settings: Settings) -> timedelta:
    """How far back an offer can still be current: an unchanged offer is stored once, when
    its game enters scope (``snapshot_horizon_hours`` before the start), and stays valid
    until the game ends; ``PROP_GAME_HOURS`` covers the game itself."""
    return timedelta(hours=settings.snapshot_horizon_hours + PROP_GAME_HOURS)


def latest_prop_rows(
    session: Session,
    provider_name: str,
    player_id: str,
    market: str | None,
    as_of: datetime,
    settings: Settings,
) -> list[ArchivedProp]:
    """Per (event, market, book), the latest row captured at or before T, among the rows
    captured within :func:`prop_lookback` before T. A game whose latest rows are all
    tombstones (its offers were withdrawn, or it left scope) is left out, so a finished
    game's last offers are never shown as open. Ordered by event, market and book."""
    p = ArchivedProp
    conditions = [
        p.provider == provider_name,
        p.player_id == player_id,
        p.captured_at <= as_of,
        p.captured_at >= as_of - prop_lookback(settings),
    ]
    if market is not None:
        conditions.append(p.market == market)
    newest = (
        select(p.event_id, p.market, p.sportsbook_id, func.max(p.captured_at).label("at"))
        .where(*conditions)
        .group_by(p.event_id, p.market, p.sportsbook_id)
        .subquery()
    )
    rows = list(
        session.scalars(
            select(p)
            .join(
                newest,
                and_(
                    p.provider == provider_name,
                    p.player_id == player_id,
                    p.event_id == newest.c.event_id,
                    p.market == newest.c.market,
                    p.sportsbook_id == newest.c.sportsbook_id,
                    p.captured_at == newest.c.at,
                ),
            )
            .order_by(p.event_id, p.market, p.sportsbook_id)
        )
    )
    offered = {r.event_id for r in rows if r.status != "unavailable"}
    return [r for r in rows if r.event_id in offered]


def event_from(snapshot: ArchivedEvent) -> Event:
    score = None
    if snapshot.score_home is not None and snapshot.score_away is not None:
        score = Score(home=snapshot.score_home, away=snapshot.score_away)
    return Event(
        provider=snapshot.provider,
        provider_id=snapshot.provider_id,
        fetched_at=snapshot.fetched_at,
        id=snapshot.event_id,
        league=snapshot.league,
        home_team_id=snapshot.home_team_id,
        away_team_id=snapshot.away_team_id,
        start_time=snapshot.start_time,
        status=snapshot.status,  # type: ignore[arg-type]
        score=score,
        period_text=snapshot.period_text,
        score_updated_at=snapshot.score_updated_at,
        markets=list(snapshot.markets),
    )


def odds_from(row: ArchivedOdds) -> OddsSnapshot:
    return OddsSnapshot(
        provider=row.provider,
        provider_id=row.provider_id,
        fetched_at=row.fetched_at,
        event_id=row.event_id,
        market=row.market,
        sportsbook_id=row.sportsbook_id,
        status=row.status,  # type: ignore[arg-type]
        last_updated=row.last_updated,
        outcomes=[
            OddsOutcome(key=key, name=name, line=line, price_american=price)
            for key, name, line, price in row.outcomes
        ],
    )


def prop_from(row: ArchivedProp) -> PropOffer:
    return PropOffer(
        provider=row.provider,
        provider_id=row.provider_id,
        fetched_at=row.fetched_at,
        player_id=row.player_id,
        event_id=row.event_id,
        market=row.market,
        sportsbook_id=row.sportsbook_id,
        status=row.status,  # type: ignore[arg-type]
        last_updated=row.last_updated,
        line=None if row.line is None else float(row.line),
        over_american=row.over_american,
        under_american=row.under_american,
    )


class ArchiveView:
    """A :class:`SportsDataProvider` that answers as of ``as_of`` from the archive.

    Reference data (leagues, sportsbooks, teams, players) comes from the running provider:
    it is static. Events, odds and prop offers come only from rows captured at or before
    ``as_of``. Line history, game logs and next events return nothing: they must never
    reveal data from after T, and their as-of reads belong to later items (F17, F34).
    """

    def __init__(
        self, session: Session, base: SportsDataProvider, as_of: datetime, settings: Settings
    ) -> None:
        self.session = session
        self.base = base
        self.as_of = as_of
        self.settings = settings
        self.name = base.name
        self.data_mode = base.data_mode
        self._coverage: dict[str, Coverage] = {}
        self._book_order = {b.id: i for i, b in enumerate(base.list_sportsbooks())}
        #: (event id, market, sportsbook id) -> the archived row last served for it.
        self.served: dict[tuple[str, str, str], ArchivedOdds] = {}

    # ------------------------------------------------------------ the clock
    def now(self) -> datetime:
        return self.as_of

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            data_mode=self.data_mode,
            status="ok",
            checked_at=self.as_of,
            detail=f"archive as of {self.as_of.isoformat()}",
        )

    # ------------------------------------------------------ reference data
    def list_leagues(self) -> list[League]:
        return self.base.list_leagues()

    def list_sportsbooks(self) -> list[Sportsbook]:
        return self.base.list_sportsbooks()

    def list_teams(self, league: str | None = None) -> list[Team]:
        return self.base.list_teams(league)

    def get_team(self, team_id: str) -> Team | None:
        return self.base.get_team(team_id)

    def list_players(
        self, league: str | None = None, team_id: str | None = None, query: str | None = None
    ) -> list[Player]:
        return self.base.list_players(league=league, team_id=team_id, query=query)

    def get_player(self, player_id: str) -> Player | None:
        return self.base.get_player(player_id)

    # ------------------------------------------------------------- archive
    def coverage(self, event_id: str) -> Coverage:
        found = self._coverage.get(event_id)
        if found is None:
            found = coverage_at(self.session, self.name, event_id, self.as_of, self.settings)
            self._coverage[event_id] = found
        return found

    def get_event(self, event_id: str) -> Event | None:
        coverage = self.coverage(event_id)
        if coverage.status != "captured" or coverage.snapshot is None:
            return None
        return event_from(coverage.snapshot)

    def list_events(
        self, league: str | None = None, status: str | None = None, on_date: date | None = None
    ) -> list[Event]:
        """The events of the latest odds capture at or before T, unless T is in a gap."""
        run_at = _latest_odds_run_at(self.session, self.name, self.as_of)
        if (
            run_at is None
            or (self.as_of - run_at).total_seconds() > self.settings.snapshot_max_gap_seconds
        ):
            return []
        rows = self.session.scalars(
            select(ArchivedEvent)
            .where(ArchivedEvent.provider == self.name, ArchivedEvent.captured_at == run_at)
            .order_by(ArchivedEvent.start_time, ArchivedEvent.event_id)
        )
        events = [event_from(row) for row in rows]
        return [
            e
            for e in events
            if (league is None or e.league == league)
            and (status is None or e.status == status)
            and (on_date is None or e.start_time.date() == on_date)
        ]

    def get_odds(self, event_id: str, market: str) -> list[OddsSnapshot]:
        """Per book, the latest quote at or before the event's coverage row (so never after
        T), in the running provider's book order. Empty without a coverage row."""
        captured_at = self.coverage(event_id).captured_at
        if captured_at is None:
            return []
        rows = latest_odds_rows(self.session, self.name, event_id, market, captured_at)
        rows.sort(
            key=lambda r: (
                self._book_order.get(r.sportsbook_id, len(self._book_order)),
                r.sportsbook_id,
            )
        )
        for row in rows:
            self.served[(row.event_id, row.market, row.sportsbook_id)] = row
        return [odds_from(row) for row in rows]

    def get_prop_offers(self, player_id: str, market: str | None = None) -> list[PropOffer]:
        return [
            prop_from(r)
            for r in latest_prop_rows(
                self.session, self.name, player_id, market, self.as_of, self.settings
            )
        ]

    def get_line_history(self, event_id: str, market: str) -> list[LineSeries]:
        return []

    def get_player_game_log(self, player_id: str, limit: int | None = None) -> list[GameLogEntry]:
        return []

    def next_event_for_team(self, team_id: str) -> Event | None:
        return None


class ArchiveBoard(Board):
    """The live :class:`Board` over an :class:`ArchiveView`, with one difference: an event
    archived as ``upcoming`` whose start time had passed at T is judged by the live stale
    threshold. Its last capture was before the start; by T the game may be in play, and
    a pregame quote must not pass as an in-play price. The event keeps the status it was
    captured with in every response; only the threshold changes."""

    def freshness_status(self, event: Event) -> str:
        if event.status == "upcoming" and self.now >= event.start_time:
            return "live"
        return event.status


def board_at(view: ArchiveView, coverage: Coverage) -> Board:
    """An :class:`ArchiveBoard` over the view, judging staleness at T with the stale
    thresholds in force when the covering capture ran: a later change of setting never
    rewrites history."""
    settings = view.settings
    run = view.session.get(SnapshotRun, coverage.run_id) if coverage.run_id is not None else None
    if run is not None:
        settings = settings.model_copy(
            update={
                "stale_pregame_seconds": run.stale_pregame_seconds,
                "stale_live_seconds": run.stale_live_seconds,
            }
        )
    return ArchiveBoard(view, settings, InMemoryTTLCache())


__all__ = [
    "PROP_GAME_HOURS",
    "ArchiveBoard",
    "ArchiveView",
    "Coverage",
    "CoverageStatus",
    "board_at",
    "coverage_at",
    "event_from",
    "latest_odds_rows",
    "latest_prop_rows",
    "prop_lookback",
]
