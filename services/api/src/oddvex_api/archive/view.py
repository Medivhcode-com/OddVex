"""Reading the archive as of a time T.

``coverage_at`` says whether the archive covers an event at T. :class:`ArchiveView` is a
read-only :class:`SportsDataProvider` that answers from rows captured at or before T, so
the live :class:`Board` code computes best price and consensus as of T unchanged
(``board_at`` gives it the stale thresholds that were in force at capture, and judges an
archived ``upcoming`` event whose start time had passed at T by the live threshold). No
method ever returns a row captured after T.

Two cutoffs recorded by the prune (``prune_cutoffs``) bound what a read may trust. Games
whose last capture is before ``prune_cutoff`` hold only their kept captures. Before
``keep_cutoff`` (the keep horizon) capture runs are thinned, so a read that would have to
rely on a run from before it answers ``archive_pruned`` and returns nothing.

**Reading beside a running prune.** A prune records how far it will go (a ``started``
prune run with both cutoffs, committed before it deletes anything) and then removes each
game's rows in one transaction, so no committed state holds a capture's event row without
its quotes. A read is several statements, though, and on PostgreSQL each sees what was
committed when it began, so a game's transaction can land between two of them. Every read
therefore checks, after its last statement, that no prune has started since its first
(:func:`prune_marker`) and that every capture it answered from is still held; if not it
reads again (``READ_ATTEMPTS`` times at most, then :class:`ArchiveBusy`). An answer that
passes was built from rows that were all there together.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from itertools import pairwise
from typing import Any, Literal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from ..board import Board
from ..cache import InMemoryTTLCache
from ..config import (
    SNAPSHOT_PROP_GAME_HOURS,
    SNAPSHOT_WORKER_TURN_SECONDS,
    Settings,
)
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
PROP_GAME_HOURS = SNAPSHOT_PROP_GAME_HOURS
#: The worker loop's period: the gap limits allow two missed intervals plus one turn.
WORKER_TURN_SECONDS = SNAPSHOT_WORKER_TURN_SECONDS
#: Statuses of a prune run that tell how far a prune reaches: ``started`` is written and
#: committed before the prune deletes anything, ``ok`` when it has finished. A read
#: trusts neither a game nor a time that a started prune may already have reduced.
PRUNE_REACH = ("started", "ok")
#: Times a read is made again when a prune changed the archive under it.
READ_ATTEMPTS = 4


class ArchiveBusy(RuntimeError):
    """A read was made ``READ_ATTEMPTS`` times and a prune changed the rows under it
    every time. One prune can do that three times at most (it starts, it reduces the
    game, the keep horizon removes the game), and two prunes are at least a worker turn
    (120 s) apart."""


def prune_marker(session: Session) -> int | None:
    """The id of the newest prune start. A prune writes one, committed, before it deletes
    anything, so two equal readings mean no prune began in between."""
    return session.scalar(
        select(func.max(SnapshotRun.id)).where(
            SnapshotRun.kind == "prune", SnapshotRun.status == "started"
        )
    )


def still_held(session: Session, snapshot_ids: set[int]) -> bool:
    """Whether every one of these event rows is still in the archive."""
    if not snapshot_ids:
        return True
    held = session.scalar(
        select(func.count()).select_from(ArchivedEvent).where(ArchivedEvent.id.in_(snapshot_ids))
    )
    return int(held or 0) == len(snapshot_ids)


def settled[T](session: Session, read: Callable[[], tuple[T, set[int]]]) -> T:
    """``read()`` gives an answer and the ids of the event rows (captures) it was built
    from. The answer is returned once no prune started while it was being read and those
    captures are still held afterwards: the rows it read were then all there together
    (module docstring). Otherwise it is read again."""
    for _ in range(READ_ATTEMPTS):
        marker = prune_marker(session)
        answer, snapshot_ids = read()
        if prune_marker(session) == marker and still_held(session, snapshot_ids):
            return answer
    raise ArchiveBusy("the prune kept changing the rows this read needs")


@dataclass(frozen=True)
class Coverage:
    """How the archive covers one event at T.

    Let R be the latest ``ok`` odds capture run at or before T (runs are kept 400 days).

    - ``captured``: R is at most ``snapshot_max_gap_seconds`` before T and the archive
      holds the event's row from R. Only then is anything priced.
    - ``archive_gap``: no ``ok`` odds capture within the limit before T.
    - ``archive_pruned``: R ran while the event was in scope (between its first and its
      last capture), but its rows from R were pruned; or T is within the gap limit of
      the keep horizon or before it, where capture runs are no longer all kept.
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


def prune_cutoffs(session: Session) -> tuple[datetime | None, datetime | None]:
    """(prune_cutoff, keep_cutoff) reached by the prunes so far: the largest recorded, so
    a later change of the retention settings never makes a read trust what an earlier
    prune removed. A prune that has started counts, finished or not: it records both
    cutoffs before it deletes anything, so a prune that is running, or was cut short, is
    never trusted less than one that ended. ``None`` before the first prune."""
    row = session.execute(
        select(func.max(SnapshotRun.prune_cutoff), func.max(SnapshotRun.keep_cutoff)).where(
            SnapshotRun.kind == "prune", SnapshotRun.status.in_(PRUNE_REACH)
        )
    ).one()
    return row[0], row[1]


def _event_bounds(
    session: Session, provider_name: str, event_id: str
) -> tuple[datetime | None, datetime | None]:
    """When the event's first and last remaining event rows were captured. The prune
    keeps both captures, so they are when the event entered and left scope."""
    row = session.execute(
        select(func.min(ArchivedEvent.captured_at), func.max(ArchivedEvent.captured_at)).where(
            ArchivedEvent.provider == provider_name, ArchivedEvent.event_id == event_id
        )
    ).one()
    return row[0], row[1]


def open_offer_stored(
    session: Session, provider_name: str, event_id: str, start: datetime, end: datetime
) -> datetime | None:
    """When the event's earliest open prop offer (any row that is not a tombstone)
    captured from ``start`` to ``end`` was stored, or ``None``. The prune leaves an event
    alone while one is stored at or after its cutoff: a props capture then has the event
    in scope, whatever its event rows say (they are written by the odds capture, which
    can run in another pass)."""
    return session.scalar(
        select(func.min(ArchivedProp.captured_at)).where(
            ArchivedProp.provider == provider_name,
            ArchivedProp.event_id == event_id,
            ArchivedProp.captured_at >= start,
            ArchivedProp.captured_at <= end,
            ArchivedProp.status != "unavailable",
        )
    )


def reduced_until(session: Session, provider_name: str, event_id: str) -> datetime | None:
    """The time up to which the event's rows are only the kept ones, or ``None`` when the
    prune has never handled it (every row of it is still there).

    A prune handles an event when its last event row is before that prune's cutoff and
    no open prop offer of it is stored from the cutoff on, and then reduces every row the
    event has at that moment. So prune i (run at ``now_i``, cutoff ``c_i``) handled the
    event exactly when the event had a row before ``c_i``, none in ``[c_i, now_i]``, and
    no open offer stored in ``[c_i, now_i]`` (:func:`open_offer_stored`): a gap in its
    event rows, or the open end after its last one, that holds such a prune. Rows
    captured after ``now_i`` (the game came back into scope) were never touched by it.
    The latest such ``now_i`` is the answer. A cutoff is at least a day before its prune
    (``snapshot_retention_days`` is at least 1), so only gaps longer than a day are
    looked at.

    Whether an open offer was stored in ``[c_i, now_i]`` can be read now: a prune that
    handles the event deletes every such row (the kept closing offers are older than its
    cutoff), a prune that left the event alone deletes none, and no row is ever written
    with an earlier capture time. An offer stored at ``t`` stops every prune from ``t``
    until it has aged out, so the search goes on among the prunes before ``t``.

    A prune counts from its start (``PRUNE_REACH``): one that is running, or was cut
    short, may or may not have reached the event yet, and the event is read as reduced
    either way. (Its transaction per game makes the two cases the only ones.)"""
    times = list(
        session.scalars(
            select(ArchivedEvent.captured_at)
            .where(ArchivedEvent.provider == provider_name, ArchivedEvent.event_id == event_id)
            .order_by(ArchivedEvent.captured_at)
        )
    )
    if not times:
        return None
    gaps: list[tuple[datetime, datetime | None]] = [
        (earlier, later)
        for earlier, later in pairwise(times)
        if later - earlier > timedelta(days=1)
    ]
    gaps.append((times[-1], None))
    for earlier, later in reversed(gaps):
        before = later
        while True:
            conditions = [SnapshotRun.kind == "prune", SnapshotRun.status.in_(PRUNE_REACH)]
            if before is not None:
                conditions.append(SnapshotRun.captured_at < before)
            # Cutoffs never move back, so the last prune before the bound has the
            # largest: if a prune before it handled the event, this one did, unless an
            # open offer stopped it.
            prune = session.execute(
                select(SnapshotRun.captured_at, SnapshotRun.prune_cutoff)
                .where(*conditions)
                .order_by(SnapshotRun.captured_at.desc(), SnapshotRun.id.desc())
                .limit(1)
            ).first()
            if prune is None or prune.prune_cutoff is None or prune.prune_cutoff <= earlier:
                break
            stopped_at = open_offer_stored(
                session, provider_name, event_id, prune.prune_cutoff, prune.captured_at
            )
            if stopped_at is None:
                return prune.captured_at  # type: ignore[no-any-return]
            before = stopped_at
    return None


def _pruned_while_in_scope(
    session: Session, provider_name: str, event_id: str, run_at: datetime
) -> bool:
    """Whether the event's row from the run at ``run_at`` existed and was pruned: the run
    falls between the event's first and last captures (the prune keeps both, so they are
    when it entered and left scope) and at or before the time up to which the prune has
    reduced the event's rows (:func:`reduced_until`)."""
    first, last = _event_bounds(session, provider_name, event_id)
    if first is None or last is None or not first <= run_at <= last:
        return False
    reduced = reduced_until(session, provider_name, event_id)
    return reduced is not None and run_at <= reduced


def _covering_run(
    session: Session,
    provider_name: str,
    as_of: datetime,
    settings: Settings,
    keep_cutoff: datetime | None,
) -> tuple[CoverageStatus, datetime | None]:
    """R, the latest ``ok`` odds capture at or before T, when it covers T
    (``captured``); otherwise why not. A run from before the keep horizon is not
    trusted: runs are thinned there, so a later capture may have existed."""
    limit = timedelta(seconds=settings.snapshot_max_gap_seconds)
    run_at = _latest_odds_run_at(session, provider_name, as_of)
    if (
        keep_cutoff is not None
        and as_of - limit < keep_cutoff
        and (run_at is None or run_at < keep_cutoff)
    ):
        return "archive_pruned", None
    if run_at is None:
        return "not_captured", None
    if as_of - run_at > limit:
        return "archive_gap", run_at
    return "captured", run_at


def coverage_at(
    session: Session,
    provider_name: str,
    event_id: str,
    as_of: datetime,
    settings: Settings,
    cutoffs: tuple[datetime | None, datetime | None] | None = None,
) -> Coverage:
    prune_cutoff, keep_cutoff = cutoffs if cutoffs is not None else prune_cutoffs(session)
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
    status, run_at = _covering_run(session, provider_name, as_of, settings, keep_cutoff)
    if status != "captured" or run_at is None:
        return Coverage(status, snapshot)
    # Captured only from the latest capture at or before T, never from an older row
    # (for example another bet's kept anchor) when that capture's row is gone. A kept
    # capture is whole: the keep horizon removes a game's rows together.
    if snapshot is not None and snapshot.captured_at >= run_at:
        return Coverage("captured", snapshot)
    if prune_cutoff is not None and _pruned_while_in_scope(
        session, provider_name, event_id, run_at
    ):
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
    """How far back from T an open offer's latest row can be
    (``Settings.snapshot_prop_lookback_seconds``): the capture horizon plus the game, and
    never less than the age at which an unchanged offer is stored again plus the props
    gap limit, so the read finds every open offer at every allowed setting."""
    return timedelta(seconds=settings.snapshot_prop_lookback_seconds)


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


def props_max_gap_seconds(settings: Settings) -> int:
    """Two props intervals plus one worker turn (7,320 s with hourly props), the props
    counterpart of ``snapshot_max_gap_seconds``."""
    return settings.snapshot_props_max_gap_seconds


@dataclass(frozen=True)
class PropsRead:
    """One player's props as of T.

    ``status`` is read from P, the latest ``ok`` props capture at or before T:
    ``captured`` when P is at most :func:`props_max_gap_seconds` before T,
    ``archive_gap`` when it is older, ``not_captured`` before the first capture, and
    ``archive_pruned`` when the look-back before T reaches past the keep horizon, where
    rows and runs are no longer all kept. ``rows`` is empty unless the status is
    ``captured``.

    ``pruned_event_ids`` names the player's games whose offers at T cannot be read back
    exactly because the retention prune removed rows of them; their rows are left out.
    """

    status: CoverageStatus
    captured_at: datetime | None
    rows: list[ArchivedProp]
    pruned_event_ids: list[str]


def _run_after(
    session: Session, provider_name: str, kind: str, moment: datetime | None, *, inclusive: bool
) -> datetime | None:
    """The first ``ok`` run of ``kind`` at (``inclusive``) or after ``moment``; the first
    of all when ``moment`` is ``None``."""
    conditions = [
        SnapshotRun.kind == kind,
        SnapshotRun.provider == provider_name,
        SnapshotRun.status == "ok",
    ]
    if moment is not None:
        conditions.append(
            SnapshotRun.captured_at >= moment if inclusive else SnapshotRun.captured_at > moment
        )
    return session.scalar(select(func.min(SnapshotRun.captured_at)).where(*conditions))


def _pruned_prop_events(
    session: Session,
    provider_name: str,
    player_id: str,
    team_id: str | None,
    market: str | None,
    as_of: datetime,
    settings: Settings,
    prune_cutoff: datetime,
    run_at: datetime,
) -> tuple[set[str], list[str]]:
    """(games whose rows are left out, games named as pruned) for one player at T, where
    ``run_at`` is P, the props capture that covers T.

    Let U be the time up to which the prune has reduced a game G
    (:func:`reduced_until`). Of G's prop rows captured up to U only the closing offers are
    left: per offer, the latest row at or before C, G's last ``upcoming`` capture up to
    U. Rows captured after U (G came back into scope) are all there. So G's props at T
    are exact in two cases only:

    - T is at or before U and before P1, the first props capture after C, and no kept row
      of the player lies in (T, C] (else an earlier row of that offer was deleted);
    - T and P are after U, and the player has no row of G from the look-back before T
      that was captured up to U: the answer then comes from rows captured after U only.
      (Every offer open at P has such a row: an offer is stored again at a capture
      unless its stored row is less than ``PROP_REFRESH_HOURS`` old.)

    Otherwise G's rows are left out, and G is named as pruned while T is inside its
    props activity: from the first props capture that can have had G (the first one
    after the odds capture before G's first, which the prune keeps, so a start time
    moved after G entered scope changes nothing) to the look-back after the props
    capture that tombstoned its offers (the first one after the odds capture that no
    longer had G). A game with a kept row of the player at or before T was in scope by
    T whatever the runs say, and is checked the same way.

    Candidate games: those with a prop row of the player, or (by the player's team) an
    event row in the pruned range, within a few look-backs of T.
    """
    lookback = prop_lookback(settings)
    start, end = as_of - 3 * lookback, as_of + 2 * lookback
    p, e = ArchivedProp, ArchivedEvent
    prop_filter = [p.provider == provider_name, p.player_id == player_id]
    if market is not None:
        prop_filter.append(p.market == market)
    candidates = set(
        session.scalars(
            select(p.event_id)
            .where(*prop_filter, p.captured_at >= start, p.captured_at <= end)
            .distinct()
        )
    )
    if team_id is not None:
        candidates |= set(
            session.scalars(
                select(e.event_id)
                .where(
                    e.provider == provider_name,
                    e.captured_at >= start,
                    e.captured_at < min(end, prune_cutoff),
                    or_(e.home_team_id == team_id, e.away_team_id == team_id),
                )
                .distinct()
            )
        )

    def rows_of(event_id: str, *conditions: Any) -> int:
        return int(
            session.scalar(
                select(func.count())
                .select_from(p)
                .where(*prop_filter, p.event_id == event_id, *conditions)
            )
            or 0
        )

    withheld: set[str] = set()
    named: list[str] = []
    for event_id in sorted(candidates):
        reduced = reduced_until(session, provider_name, event_id)
        if reduced is None:
            continue  # never pruned: every row of it is still there
        of_event = (e.provider == provider_name, e.event_id == event_id)
        entered = session.scalar(select(func.min(e.captured_at)).where(*of_event))
        before = session.scalar(
            select(func.max(SnapshotRun.captured_at)).where(
                SnapshotRun.kind == "odds",
                SnapshotRun.provider == provider_name,
                SnapshotRun.status == "ok",
                SnapshotRun.captured_at < entered,
            )
        )
        first = _run_after(session, provider_name, "props", before, inclusive=False)
        if (first is None or as_of < first) and not rows_of(event_id, p.captured_at <= as_of):
            continue  # nothing of it had been captured by T
        if as_of > reduced:
            if run_at > reduced and not rows_of(
                event_id, p.captured_at >= as_of - lookback, p.captured_at <= reduced
            ):
                continue  # exact: only rows captured after the prune are the answer
            withheld.add(event_id)
            named.append(event_id)
            continue
        else:
            closing = session.scalar(
                select(func.max(e.captured_at)).where(
                    *of_event, e.status == "upcoming", e.captured_at <= reduced
                )
            )
            if closing is not None:
                next_props = _run_after(session, provider_name, "props", closing, inclusive=False)
                later_kept = rows_of(event_id, p.captured_at > as_of, p.captured_at <= closing)
                if (next_props is None or as_of < next_props) and not later_kept:
                    continue  # exact: the kept closing rows are the answer
        withheld.add(event_id)
        last = session.scalar(
            select(func.max(e.captured_at)).where(*of_event, e.captured_at <= reduced)
        )
        left = _run_after(session, provider_name, "odds", last, inclusive=False)
        tombstoned = (
            _run_after(session, provider_name, "props", left, inclusive=True)
            if left is not None
            else None
        )
        if tombstoned is None or as_of - lookback <= tombstoned:
            named.append(event_id)
    return withheld, named


def props_at(
    session: Session,
    provider_name: str,
    player_id: str,
    market: str | None,
    as_of: datetime,
    settings: Settings,
    team_id: str | None = None,
) -> PropsRead:
    """The player's props as of T with their coverage (:class:`PropsRead`), read so that
    a prune running beside it cannot change the answer (:func:`settled`). No event row
    is named to the check: an offer row read before its game was reduced is the true
    one, and a game reduced before the rows were read is known as reduced by the time
    the prune check below runs."""
    return settled(
        session,
        lambda: (
            _props_at(session, provider_name, player_id, market, as_of, settings, team_id),
            set(),
        ),
    )


def _props_at(
    session: Session,
    provider_name: str,
    player_id: str,
    market: str | None,
    as_of: datetime,
    settings: Settings,
    team_id: str | None,
) -> PropsRead:
    prune_cutoff, keep_cutoff = prune_cutoffs(session)
    lookback = prop_lookback(settings)
    gap = timedelta(seconds=props_max_gap_seconds(settings))
    if keep_cutoff is not None and as_of - max(lookback, gap) < keep_cutoff:
        # The rows and runs this read would look at reach past the keep horizon (the
        # look-back is never shorter than the gap limit; both are named for the reader).
        return PropsRead("archive_pruned", None, [], [])
    run_at = session.scalar(
        select(func.max(SnapshotRun.captured_at)).where(
            SnapshotRun.kind == "props",
            SnapshotRun.provider == provider_name,
            SnapshotRun.status == "ok",
            SnapshotRun.captured_at <= as_of,
        )
    )
    if run_at is None:
        return PropsRead("not_captured", None, [], [])
    if as_of - run_at > gap:
        return PropsRead("archive_gap", run_at, [], [])
    rows = latest_prop_rows(session, provider_name, player_id, market, as_of, settings)
    if prune_cutoff is None:
        return PropsRead("captured", run_at, rows, [])
    withheld, named = _pruned_prop_events(
        session, provider_name, player_id, team_id, market, as_of, settings, prune_cutoff, run_at
    )
    return PropsRead("captured", run_at, [r for r in rows if r.event_id not in withheld], named)


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

    A view is made for one answer. Whoever builds an answer from its events and odds
    asks :meth:`settled` afterwards and, when it says no, throws the answer away and
    builds it again on a new view (module docstring, "Reading beside a running prune";
    ``service.archived_odds`` and ``placement.placement_prices`` do).
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
        #: Read first, before any row: :meth:`settled` compares it with a later reading.
        self._marker = prune_marker(session)
        self._coverage: dict[str, Coverage] = {}
        self._cutoffs: tuple[datetime | None, datetime | None] | None = None
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
            found = coverage_at(
                self.session, self.name, event_id, self.as_of, self.settings, self.cutoffs()
            )
            self._coverage[event_id] = found
        return found

    def cutoffs(self) -> tuple[datetime | None, datetime | None]:
        if self._cutoffs is None:
            self._cutoffs = prune_cutoffs(self.session)
        return self._cutoffs

    def settled(self) -> bool:
        """Whether everything this view has answered still stands: no prune has started
        since the view was made, and every capture it called ``captured`` is still held.
        Then the rows it read were all there together. Ask after the last read."""
        held = {
            coverage.snapshot.id
            for coverage in self._coverage.values()
            if coverage.status == "captured" and coverage.snapshot is not None
        }
        return prune_marker(self.session) == self._marker and still_held(self.session, held)

    def get_event(self, event_id: str) -> Event | None:
        coverage = self.coverage(event_id)
        if coverage.status != "captured" or coverage.snapshot is None:
            return None
        return event_from(coverage.snapshot)

    def list_events(
        self, league: str | None = None, status: str | None = None, on_date: date | None = None
    ) -> list[Event]:
        """The events of the latest odds capture at or before T, unless T is in a gap."""
        covered, run_at = _covering_run(
            self.session, self.name, self.as_of, self.settings, self.cutoffs()[1]
        )
        if covered != "captured" or run_at is None:
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
        """The covered offers as of T (:func:`props_at`): none in a gap, and none of a game
        whose rows the prune removed."""
        player = self.base.get_player(player_id)
        read = props_at(
            self.session,
            self.name,
            player_id,
            market,
            self.as_of,
            self.settings,
            team_id=player.team_id if player is not None else None,
        )
        return [prop_from(r) for r in read.rows]

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
    "PRUNE_REACH",
    "READ_ATTEMPTS",
    "WORKER_TURN_SECONDS",
    "ArchiveBoard",
    "ArchiveBusy",
    "ArchiveView",
    "Coverage",
    "CoverageStatus",
    "PropsRead",
    "board_at",
    "coverage_at",
    "event_from",
    "latest_odds_rows",
    "latest_prop_rows",
    "open_offer_stored",
    "prop_lookback",
    "props_at",
    "props_max_gap_seconds",
    "prune_cutoffs",
    "prune_marker",
    "reduced_until",
    "settled",
    "still_held",
]
