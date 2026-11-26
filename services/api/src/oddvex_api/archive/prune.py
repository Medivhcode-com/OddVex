"""Retention prune of the snapshot archive: the only code that deletes archive rows.

Full-resolution odds, prop and event rows are kept ``snapshot_retention_days`` (7). The
prune handles an event once, when all of its rows are older than that (its last event
row has aged out), so a read at any time after the cutoff never misses a row that an
unchanged quote carried forward. It then keeps, for ``snapshot_keep_days`` (400):

- **The first capture.** The event's first event row and its odds rows. It marks when the
  event entered scope, whatever its start time was then or became later.
- **The closing capture.** The event's last ``upcoming`` event row and, per (market, book)
  and per (player, event, market, book), the latest row captured at or before it.
- **The last capture.** The event's last event row and, per (market, book), the latest
  odds row at or before it. It marks when the event left scope, so coverage can tell
  ``archive_pruned`` from ``not_captured``, and it is a complete capture in its own right.
- **Bet anchors, bounded.** For stored bet legs the archive can price (moneyline, spread
  or total with an outcome and, for spread and total, a line), the capture that covered
  the bet's ``placed_at`` (``view.coverage_at``) and, per (market, book), the latest odds
  row at or before it. At most ``MAX_ANCHORS_PER_EVENT`` captures per event are kept,
  ranked by weight: every user with a bet on the event has one vote, split evenly over
  the captures that user anchors there; ties go to the earlier capture. So one user's
  bets, however many, never keep more than ``MAX_ANCHORS_PER_EVENT`` captures of a game
  and weigh no more than one other user's single bet. (With ties to the earlier capture,
  one user's single earlier capture can still take the last slot from another user's
  later one.)

Every other row of the event is deleted, in batches of ``DELETE_BATCH`` ids with a commit
each, so no long lock is held and the write-ahead log stays small. That includes prop rows
captured after the event's last event row (the tombstones written when it left scope),
which therefore go up to about an hour before they are 7 days old; the props read
(``view.props_at``) serves the kept closing offers only for times at which they are still
the answer, and names the game as pruned otherwise.

**The keep horizon** (``keep_sweep``) works per game, because a kept capture holds rows
older than itself (a quote unchanged since an earlier capture is stored once). A game's
event, odds and prop rows leave together, once its last event row is older than
``snapshot_keep_days``; until then every kept capture of it is whole. A status row goes
by its own age (each record stands alone). A capture run past the horizon is deleted
only when no remaining row refers to it; the last successful odds and props capture
before the horizon also stays, so a later time with no capture since still reads as a
gap. Each prune run records its two cutoffs (``prune_cutoff``, ``keep_cutoff``); neither
ever moves back, so a later change of setting cannot make a read trust what an earlier
prune removed. The reads (``view.py``) answer nothing from capture runs before
``keep_cutoff``: runs are thinned there, so "the latest capture at or before T" is no
longer knowable.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..db import (
    ArchivedEvent,
    ArchivedOdds,
    ArchivedProp,
    ArchivedStatus,
    Bet,
    BetLeg,
    SnapshotRun,
    utcnow,
)
from ..flags import service as flags
from ..providers import SportsDataProvider
from .capture import FLAG, RunSummary, guarded, is_due, new_run
from .placement import structured_leg_condition
from .view import prune_cutoffs

#: Ids deleted per statement, each batch in its own transaction.
DELETE_BATCH = 1000
#: Each pass re-examines the events whose last row aged out this long before the
#: previous pass's cutoff.
WINDOW_OVERLAP = timedelta(hours=1)
#: Captures kept per event for stored bets, beyond the closing and last captures.
MAX_ANCHORS_PER_EVENT = 6


def _delete_ids(session: Session, model: type[Any], ids: Sequence[int]) -> int:
    for start in range(0, len(ids), DELETE_BATCH):
        session.execute(delete(model).where(model.id.in_(ids[start : start + DELETE_BATCH])))
        session.commit()
    return len(ids)


def _bet_anchors(
    session: Session,
    provider_name: str,
    event_id: str,
    event_times: Sequence[datetime],
    settings: Settings,
) -> set[datetime]:
    """The captures (event row times) kept for stored bets on the event, at most
    ``MAX_ANCHORS_PER_EVENT``. A bet anchors the capture that covers its ``placed_at``:
    the latest ``ok`` odds run at or before it, within ``snapshot_max_gap_seconds``, when
    the event has a row from that run."""
    if not event_times:
        return set()
    limit = timedelta(seconds=settings.snapshot_max_gap_seconds)
    first, last = event_times[0], event_times[-1]
    runs = list(
        session.scalars(
            select(SnapshotRun.captured_at)
            .where(
                SnapshotRun.kind == "odds",
                SnapshotRun.provider == provider_name,
                SnapshotRun.status == "ok",
                SnapshotRun.captured_at >= first,
                SnapshotRun.captured_at <= last + limit,
            )
            .order_by(SnapshotRun.captured_at)
        )
    )
    rows = set(event_times)
    per_user: dict[str, set[datetime]] = defaultdict(set)
    legs = session.execute(
        select(Bet.user_id, Bet.placed_at)
        .join(BetLeg, BetLeg.bet_id == Bet.id)
        .where(
            BetLeg.event_id == event_id,
            structured_leg_condition(),
            Bet.placed_at >= first,
            Bet.placed_at <= last + limit,
        )
        .execution_options(yield_per=1000)
    )
    for user_id, placed_at in legs:
        index = bisect_right(runs, placed_at)
        if index == 0:
            continue
        run_at = runs[index - 1]
        if placed_at - run_at <= limit and run_at in rows:
            per_user[user_id].add(run_at)
    weight: dict[datetime, float] = defaultdict(float)
    for anchored in per_user.values():
        for run_at in anchored:
            weight[run_at] += 1 / len(anchored)
    ranked = sorted(weight, key=lambda run_at: (-weight[run_at], run_at))
    return set(ranked[:MAX_ANCHORS_PER_EVENT])


def _prune_event(session: Session, provider_name: str, event_id: str, settings: Settings) -> int:
    """Delete every row of an event whose rows have all aged out, except the first
    capture, the closing capture, the last capture and the bounded bet anchors."""
    e, o, p = ArchivedEvent, ArchivedOdds, ArchivedProp
    events = session.execute(
        select(e.id, e.captured_at, e.status)
        .where(e.provider == provider_name, e.event_id == event_id)
        .order_by(e.captured_at)
    ).all()
    if not events:
        return 0
    times = [r.captured_at for r in events]
    upcoming = [r.captured_at for r in events if r.status == "upcoming"]
    closing = upcoming[-1] if upcoming else None
    keep_events = {
        times[0],
        times[-1],
        *_bet_anchors(session, provider_name, event_id, times, settings),
    }
    if closing is not None:
        keep_events.add(closing)

    odds = session.execute(
        select(o.id, o.market, o.sportsbook_id, o.captured_at)
        .where(o.provider == provider_name, o.event_id == event_id)
        .order_by(o.captured_at)
    ).all()
    by_key: dict[tuple[str, str], list[tuple[datetime, int]]] = defaultdict(list)
    for r in odds:
        by_key[(r.market, r.sportsbook_id)].append((r.captured_at, r.id))
    keep_odds: set[int] = set()
    for anchor in keep_events:
        for rows in by_key.values():
            # The key's latest row at or before the anchor (rows are in time order).
            index = bisect_right(rows, (anchor, float("inf")))
            if index:
                keep_odds.add(rows[index - 1][1])

    keep_props: set[int] = set()
    if closing is not None:
        newest = (
            select(p.player_id, p.market, p.sportsbook_id, func.max(p.captured_at).label("at"))
            .where(p.provider == provider_name, p.event_id == event_id, p.captured_at <= closing)
            .group_by(p.player_id, p.market, p.sportsbook_id)
            .subquery()
        )
        keep_props = set(
            session.scalars(
                select(p.id)
                .join(
                    newest,
                    (p.player_id == newest.c.player_id)
                    & (p.market == newest.c.market)
                    & (p.sportsbook_id == newest.c.sportsbook_id)
                    & (p.captured_at == newest.c.at),
                )
                .where(p.provider == provider_name, p.event_id == event_id)
            )
        )
    prop_ids = [
        pid
        for pid in session.scalars(
            select(p.id).where(p.provider == provider_name, p.event_id == event_id)
        )
        if pid not in keep_props
    ]
    event_ids = [r.id for r in events if r.captured_at not in keep_events]
    odds_ids = [r.id for r in odds if r.id not in keep_odds]
    session.commit()
    return (
        _delete_ids(session, o, odds_ids)
        + _delete_ids(session, p, prop_ids)
        + _delete_ids(session, e, event_ids)
    )


@dataclass(frozen=True)
class PruneResult:
    """What one prune did: rows deleted and the two cutoffs it reached."""

    deleted: int
    cutoff: datetime
    keep_cutoff: datetime


def _sweep_event(session: Session, provider_name: str, event_id: str, cutoff: datetime) -> int:
    """Delete a game whose last event row is past the keep horizon: its odds, prop and
    event rows together. (Prop rows of it captured at or after the cutoff, which only a
    provider that briefly listed the game again could have left, stay until they age.)"""
    deleted = 0
    for model, conditions in (
        (ArchivedOdds, ()),
        (ArchivedProp, (ArchivedProp.captured_at < cutoff,)),
        (ArchivedEvent, ()),
    ):
        ids = list(
            session.scalars(
                select(model.id).where(
                    model.provider == provider_name, model.event_id == event_id, *conditions
                )
            )
        )
        session.commit()
        deleted += _delete_ids(session, model, ids)
    return deleted


def _delete_where(session: Session, model: type[Any], *conditions: Any) -> int:
    deleted = 0
    while True:
        ids = list(session.scalars(select(model.id).where(*conditions).limit(DELETE_BATCH)))
        session.commit()
        if not ids:
            return deleted
        deleted += _delete_ids(session, model, ids)


def keep_sweep(session: Session, cutoff: datetime) -> int:
    """Delete what is past the keep horizon, game by game (module docstring)."""
    e, s = ArchivedEvent, ArchivedStatus
    deleted = 0
    # Games with a row older than the cutoff; of those, the ones whose last row is.
    old = sorted(
        set(
            session.execute(
                select(e.provider, e.event_id).where(e.captured_at < cutoff).distinct()
            ).tuples()
        )
    )
    session.commit()
    for provider_name, event_id in old:
        last = session.scalar(
            select(func.max(e.captured_at)).where(
                e.provider == provider_name, e.event_id == event_id
            )
        )
        if last is not None and last < cutoff:
            deleted += _sweep_event(session, provider_name, event_id, cutoff)
    # Odds and prop rows of a game with no event row at all (a props capture of a game
    # no odds capture ever had, or rows a swept game left behind) go by their own age.
    for model in (ArchivedOdds, ArchivedProp):
        has_event = (
            select(e.id).where(e.provider == model.provider, e.event_id == model.event_id).exists()
        )
        deleted += _delete_where(session, model, model.captured_at < cutoff, ~has_event)
    # Status rows stand alone (the read takes the latest per subject and kind), so each
    # goes by its own age: a record that has not changed for the whole keep period is
    # dropped, and the status read says from when its records are kept.
    deleted += _delete_where(session, s, s.captured_at < cutoff)
    # Capture runs past the cutoff that no remaining row refers to. A row's
    # ``captured_at`` is its run's, so only rows past the cutoff can refer to such a run.
    referenced: set[int] = set()
    rows: tuple[type[Any], ...] = (ArchivedEvent, ArchivedOdds, ArchivedProp, ArchivedStatus)
    for table in rows:
        referenced |= set(
            session.scalars(select(table.run_id).where(table.captured_at < cutoff).distinct())
        )
    # The last successful odds and props capture before the cutoff stays as well: a time
    # after the cutoff with no capture since still reads when capture last ran (a gap),
    # not "never captured".
    newest = (
        select(
            func.max(SnapshotRun.captured_at).label("at"), SnapshotRun.kind, SnapshotRun.provider
        )
        .where(
            SnapshotRun.captured_at < cutoff,
            SnapshotRun.status == "ok",
            SnapshotRun.kind.in_(("odds", "props")),
        )
        .group_by(SnapshotRun.kind, SnapshotRun.provider)
        .subquery()
    )
    referenced |= set(
        session.scalars(
            select(SnapshotRun.id).join(
                newest,
                (SnapshotRun.kind == newest.c.kind)
                & (SnapshotRun.provider == newest.c.provider)
                & (SnapshotRun.captured_at == newest.c.at),
            )
        )
    )
    run_ids = [
        run_id
        for run_id in session.scalars(
            select(SnapshotRun.id).where(SnapshotRun.captured_at < cutoff)
        )
        if run_id not in referenced
    ]
    session.commit()
    return deleted + _delete_ids(session, SnapshotRun, run_ids)


def prune_rows(session: Session, settings: Settings, now: datetime) -> PruneResult:
    """Delete what has aged out. The cutoffs never move back from an earlier prune's."""
    previous, previous_keep = prune_cutoffs(session)
    cutoff = now - timedelta(days=settings.snapshot_retention_days)
    keep_cutoff = now - timedelta(
        days=max(settings.snapshot_keep_days, settings.snapshot_retention_days)
    )
    if previous is not None:
        cutoff = max(cutoff, previous)
    if previous_keep is not None:
        keep_cutoff = max(keep_cutoff, previous_keep)
    e = ArchivedEvent
    # Events with a row in the window that aged out since the previous pass; of those,
    # the ones whose rows have all aged out. The others are handled when their last row
    # ages out, in a later pass.
    in_window = select(e.provider, e.event_id).where(e.captured_at < cutoff)
    if previous is not None:
        in_window = in_window.where(e.captured_at >= previous - WINDOW_OVERLAP)
    candidates = sorted(set(session.execute(in_window.distinct()).tuples()))
    session.commit()
    deleted = 0
    for provider_name, event_id in candidates:
        last = session.scalar(
            select(func.max(e.captured_at)).where(
                e.provider == provider_name, e.event_id == event_id
            )
        )
        if last is None or last >= cutoff:
            continue
        deleted += _prune_event(session, provider_name, event_id, settings)
    deleted += keep_sweep(session, keep_cutoff)
    return PruneResult(deleted, cutoff, keep_cutoff)


def prune_pass(
    session: Session, provider: SportsDataProvider, settings: Settings, *, force: bool = False
) -> RunSummary | None:
    """Prune when the last prune is at least ``snapshot_prune_interval_seconds`` old, and
    record it as a ``prune`` run. ``None`` when it was not due."""
    now = provider.now()
    if not force and not is_due(
        session, provider.name, "prune", now, settings.snapshot_prune_interval_seconds
    ):
        session.rollback()
        return None

    def work() -> SnapshotRun:
        result = prune_rows(session, settings, now)
        run = new_run(provider, settings, "prune", now)
        run.rows_deleted = result.deleted
        run.prune_cutoff = result.cutoff
        run.keep_cutoff = result.keep_cutoff
        run.finished_at = utcnow()
        session.add(run)
        session.flush()
        return run

    return guarded(session, provider, settings, "prune", now, work)


def prune_archive(
    engine: Engine, provider: SportsDataProvider, settings: Settings, *, force: bool = False
) -> RunSummary | None:
    """A prune on its own session (``scripts/capture_snapshots.py --prune-only`` and tests).
    Nothing happens while the flag is off."""
    with Session(engine, expire_on_commit=False) as session:
        if not flags.is_enabled(session, FLAG, settings):
            return None
        return prune_pass(session, provider, settings, force=force)


__all__ = [
    "DELETE_BATCH",
    "MAX_ANCHORS_PER_EVENT",
    "PruneResult",
    "keep_sweep",
    "prune_archive",
    "prune_pass",
    "prune_rows",
]
