"""Retention prune of the snapshot archive: the only code that deletes archive rows.

Full-resolution odds, prop and event rows are kept ``snapshot_retention_days`` (7). The
prune handles an event once, when all of its rows are older than that (its last event
row has aged out), so a read at any time after the cutoff never misses a row that an
unchanged quote carried forward. An event with an open prop offer stored inside the
full-resolution window is left alone as well (``view.open_offer_stored``): a props
capture has it in scope, although no odds capture has written an event row for it yet
(a game listed again days later, seen first by a props capture) or since. Its rows are
reduced once that offer has aged out too. The prune then keeps, for
``snapshot_keep_days`` (400):

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

Every other row of the event is deleted. That includes prop rows captured after the
event's last event row (the tombstones written when it left scope), which therefore go up
to about an hour before they are 7 days old; the props read (``view.props_at``) serves the
kept closing offers only for times at which they are still the answer, and names the game
as pruned otherwise.

**A prune can stop anywhere** (the worker container is replaced on every deploy, a
connection drops, the database restarts), and reads go on beside it. Two rules keep every
read right at every such point:

- *It says how far it will go before it deletes anything.* ``prune_pass`` first commits a
  ``prune`` run with status ``started`` that carries both cutoffs. From then on the reads
  (``view.prune_cutoffs``, ``view.reduced_until``) treat every game and every time the
  prune may reach as reduced, whether the prune has got there, is still running or was
  cut short. When it ends it writes its ``ok`` run (or a ``failed`` one). The next prune
  starts its window from the last ``ok`` run, so what a cut-short prune left is done then.
- *A game is reduced in one transaction.* Its event rows are the coverage record: a
  capture's event row without its quotes would read as ``captured`` and be priced from an
  older capture's rows (review round 4). So a game's event, odds and prop rows are
  deleted together and committed once, at the 7-day reduction and at the keep horizon
  alike; a prune that stops inside a game leaves that game as it was. One game is a few
  thousand rows (about 4,800 on the synthetic schedule, measured: 0.1 s a game), deleted
  ``DELETE_BATCH`` ids per statement; the rows are old and nothing else writes them, so
  the transaction holds no lock anything waits for.

**The keep horizon** (``keep_sweep``) works per game, because a kept capture holds rows
older than itself (a quote unchanged since an earlier capture is stored once). A game's
event, odds and prop rows leave together, once its last event row is older than
``snapshot_keep_days``; until then every kept capture of it is whole. A status row goes
by its own age (each record stands alone). A capture run past the horizon is deleted
only when no remaining row refers to it; the last successful odds and props capture
before the horizon also stays, so a later time with no capture since still reads as a
gap. Each prune records its two cutoffs (``prune_cutoff``, ``keep_cutoff``) when it
starts and again when it ends; neither ever moves back, so a later change of setting
cannot make a read trust what an earlier prune removed. The reads (``view.py``) answer
nothing from capture runs before ``keep_cutoff``: runs are thinned there, so "the latest
capture at or before T" is no longer knowable. Status rows, rows of a game without an
event row and capture runs past the horizon are deleted in batches with a commit each:
no read answers from before the horizon once the prune has started.
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
from .view import open_offer_stored, prune_cutoffs

#: Ids deleted per statement.
DELETE_BATCH = 1000
#: Each pass re-examines the events whose last row aged out this long before the
#: previous pass's cutoff.
WINDOW_OVERLAP = timedelta(hours=1)
#: Captures kept per event for stored bets, beyond the closing and last captures.
MAX_ANCHORS_PER_EVENT = 6


def _delete_ids(session: Session, model: type[Any], ids: Sequence[int]) -> int:
    """Delete these rows, ``DELETE_BATCH`` ids per statement. Not committed: the caller
    decides what has to go together (module docstring)."""
    for start in range(0, len(ids), DELETE_BATCH):
        session.execute(delete(model).where(model.id.in_(ids[start : start + DELETE_BATCH])))
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
    capture, the closing capture, the last capture and the bounded bet anchors: in one
    transaction, committed here, so the event is never left with a capture's event row
    and without its quotes."""
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
    deleted = (
        _delete_ids(session, e, event_ids)
        + _delete_ids(session, o, odds_ids)
        + _delete_ids(session, p, prop_ids)
    )
    session.commit()
    return deleted


@dataclass(frozen=True)
class PrunePlan:
    """How far one prune at ``now`` goes. ``cutoff`` and ``keep_cutoff`` are what it records, never
    earlier than any prune before it recorded, started or finished. ``window_from`` is
    where it starts looking for games to reduce: the cutoff of the last prune that
    finished (``None``: from the beginning), so the games a cut-short prune did not
    reach are reduced now."""

    now: datetime
    cutoff: datetime
    keep_cutoff: datetime
    window_from: datetime | None


@dataclass(frozen=True)
class PruneResult:
    """What one prune did: rows deleted and the two cutoffs it reached."""

    deleted: int
    cutoff: datetime
    keep_cutoff: datetime


def _sweep_event(session: Session, provider_name: str, event_id: str, cutoff: datetime) -> int:
    """Delete a game whose last event row is past the keep horizon: its event, odds and
    prop rows together, in one transaction committed here. (Prop rows of it captured at
    or after the cutoff, which only a provider that briefly listed the game again could
    have left, stay until they age.)"""
    deleted = 0
    for model, conditions in (
        (ArchivedEvent, ()),
        (ArchivedOdds, ()),
        (ArchivedProp, (ArchivedProp.captured_at < cutoff,)),
    ):
        ids = list(
            session.scalars(
                select(model.id).where(
                    model.provider == provider_name, model.event_id == event_id, *conditions
                )
            )
        )
        deleted += _delete_ids(session, model, ids)
    session.commit()
    return deleted


def _delete_where(session: Session, model: type[Any], *conditions: Any) -> int:
    """Delete the rows that match, a batch and a commit at a time."""
    deleted = 0
    while True:
        ids = list(session.scalars(select(model.id).where(*conditions).limit(DELETE_BATCH)))
        if not ids:
            session.commit()
            return deleted
        deleted += _delete_ids(session, model, ids)
        session.commit()


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
    deleted += _delete_ids(session, SnapshotRun, run_ids)
    session.commit()
    return deleted


def plan_prune(session: Session, settings: Settings, now: datetime) -> PrunePlan:
    """How far a prune at ``now`` goes (:class:`PrunePlan`)."""
    previous, previous_keep = prune_cutoffs(session)
    cutoff = now - timedelta(days=settings.snapshot_retention_days)
    keep_cutoff = now - timedelta(
        days=max(settings.snapshot_keep_days, settings.snapshot_retention_days)
    )
    if previous is not None:
        cutoff = max(cutoff, previous)
    if previous_keep is not None:
        keep_cutoff = max(keep_cutoff, previous_keep)
    finished = session.scalar(
        select(func.max(SnapshotRun.prune_cutoff)).where(
            SnapshotRun.kind == "prune", SnapshotRun.status == "ok"
        )
    )
    return PrunePlan(now, cutoff, keep_cutoff, finished)


def prune_rows(session: Session, settings: Settings, plan: PrunePlan) -> PruneResult:
    """Delete what has aged out, as far as ``plan`` says. Call it only once the plan's
    cutoffs are recorded and committed (``prune_pass`` does)."""
    cutoff = plan.cutoff
    e = ArchivedEvent
    # Events with an event row or a prop row in the window that aged out since the last
    # prune that finished; of those, the ones whose rows have all aged out. The others
    # are handled when their last row ages out, in a later pass. (The prop rows are in
    # the window for the event that was left alone because of an open offer: it comes
    # up again when that offer ages out.)
    candidates: set[tuple[str, str]] = set()
    for model in (e, ArchivedProp):
        in_window = select(model.provider, model.event_id).where(model.captured_at < cutoff)
        if plan.window_from is not None:
            in_window = in_window.where(model.captured_at >= plan.window_from - WINDOW_OVERLAP)
        candidates |= set(session.execute(in_window.distinct()).tuples())
    session.commit()
    deleted = 0
    for provider_name, event_id in sorted(candidates):
        last = session.scalar(
            select(func.max(e.captured_at)).where(
                e.provider == provider_name, e.event_id == event_id
            )
        )
        if last is None or last >= cutoff:
            continue
        if open_offer_stored(session, provider_name, event_id, cutoff, plan.now) is not None:
            continue  # a props capture has the game in scope: its rows are not all old
        deleted += _prune_event(session, provider_name, event_id, settings)
    deleted += keep_sweep(session, plan.keep_cutoff)
    return PruneResult(deleted, cutoff, plan.keep_cutoff)


def prune_pass(
    session: Session, provider: SportsDataProvider, settings: Settings, *, force: bool = False
) -> RunSummary | None:
    """Prune when the last prune that finished is at least
    ``snapshot_prune_interval_seconds`` old. It is recorded twice: a ``started`` run with
    the cutoffs, committed before anything is deleted, and the ``ok`` run when it ends (a
    ``failed`` one when it raised). ``None`` when it was not due."""
    now = provider.now()
    if not force and not is_due(
        session, provider.name, "prune", now, settings.snapshot_prune_interval_seconds
    ):
        session.rollback()
        return None

    def work() -> SnapshotRun:
        plan = plan_prune(session, settings, now)
        started = new_run(provider, settings, "prune", now, status="started")
        started.prune_cutoff = plan.cutoff
        started.keep_cutoff = plan.keep_cutoff
        session.add(started)
        session.commit()
        result = prune_rows(session, settings, plan)
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
    "PrunePlan",
    "PruneResult",
    "keep_sweep",
    "plan_prune",
    "prune_archive",
    "prune_pass",
    "prune_rows",
]
