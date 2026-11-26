"""Retention prune of the snapshot archive: the only code that deletes archive rows.

Full-resolution odds, prop and event rows are kept ``snapshot_retention_days`` (7). When
they age out, two kinds of row are kept for ``snapshot_keep_days`` (400):

- **Closing rows.** Per event, its last ``upcoming`` event row and, per (market, book) and
  per (player, market, book), the latest row captured at or before it.
- **Bet anchors.** For every stored bet leg on the event, the event row covering the bet's
  ``placed_at`` and, per (market, book), the latest odds row at or before it.

So every stored bet keeps the rows its placement-time price was read from. Each pass looks
only at the rows aged out since the previous pass (the previous cutoff less an hour of
overlap), one event at a time, and deletes in batches of ``DELETE_BATCH`` ids with a commit
each, so no long lock is held and the write-ahead log stays small. Then everything older
than ``snapshot_keep_days`` goes: rows first, then the capture runs, which share the rows'
``captured_at`` and so the same cutoff.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, Engine, delete, func, select
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
)
from ..flags import service as flags
from ..providers import SportsDataProvider
from .capture import FLAG, RunSummary, guarded, is_due, new_run

#: Ids deleted per statement, each batch in its own transaction.
DELETE_BATCH = 1000
#: A condition on an archive model's columns.
Window = Callable[[Any], ColumnElement[bool]]
#: Each pass re-examines this much of the previous pass's window.
WINDOW_OVERLAP = timedelta(hours=1)


def _delete_ids(session: Session, model: type[Any], ids: Sequence[int]) -> int:
    for start in range(0, len(ids), DELETE_BATCH):
        session.execute(delete(model).where(model.id.in_(ids[start : start + DELETE_BATCH])))
        session.commit()
    return len(ids)


def _delete_older(session: Session, model: type[Any], cutoff: datetime) -> int:
    deleted = 0
    while True:
        ids = list(
            session.scalars(select(model.id).where(model.captured_at < cutoff).limit(DELETE_BATCH))
        )
        if not ids:
            return deleted
        deleted += _delete_ids(session, model, ids)


def _anchor_times(
    session: Session, provider_name: str, event_id: str
) -> tuple[datetime | None, set[datetime]]:
    """The event's closing time (its last upcoming row) and the placement times of the
    stored bets with a leg on it."""
    closing = session.scalar(
        select(func.max(ArchivedEvent.captured_at)).where(
            ArchivedEvent.provider == provider_name,
            ArchivedEvent.event_id == event_id,
            ArchivedEvent.status == "upcoming",
        )
    )
    placed = set(
        session.scalars(
            select(Bet.placed_at)
            .join(BetLeg, BetLeg.bet_id == Bet.id)
            .where(BetLeg.event_id == event_id)
            .distinct()
        )
    )
    return closing, placed


def _prune_event(session: Session, provider_name: str, event_id: str, window: list[Window]) -> int:
    closing, placed = _anchor_times(session, provider_name, event_id)
    e, o, p = ArchivedEvent, ArchivedOdds, ArchivedProp
    keep_events: set[datetime] = set()
    keep_odds: set[tuple[str, str, datetime]] = set()
    keep_props: set[tuple[str, str, str, datetime]] = set()
    for anchor in sorted({closing, *placed} - {None}):  # type: ignore[type-var]
        covered = session.scalar(
            select(func.max(e.captured_at)).where(
                e.provider == provider_name, e.event_id == event_id, e.captured_at <= anchor
            )
        )
        if covered is None:
            continue
        keep_events.add(covered)
        keep_odds.update(
            (r.market, r.sportsbook_id, r.at)
            for r in session.execute(
                select(o.market, o.sportsbook_id, func.max(o.captured_at).label("at"))
                .where(
                    o.provider == provider_name, o.event_id == event_id, o.captured_at <= covered
                )
                .group_by(o.market, o.sportsbook_id)
            )
        )
        if anchor == closing:
            keep_props.update(
                (r.player_id, r.market, r.sportsbook_id, r.at)
                for r in session.execute(
                    select(
                        p.player_id, p.market, p.sportsbook_id, func.max(p.captured_at).label("at")
                    )
                    .where(
                        p.provider == provider_name,
                        p.event_id == event_id,
                        p.captured_at <= covered,
                    )
                    .group_by(p.player_id, p.market, p.sportsbook_id)
                )
            )

    def where(model: Any) -> list[ColumnElement[bool]]:
        return [
            model.provider == provider_name,
            model.event_id == event_id,
            *(c(model) for c in window),
        ]

    event_ids = [
        r.id
        for r in session.execute(select(e.id, e.captured_at).where(*where(e)))
        if r.captured_at not in keep_events
    ]
    odds_ids = [
        r.id
        for r in session.execute(
            select(o.id, o.market, o.sportsbook_id, o.captured_at).where(*where(o))
        )
        if (r.market, r.sportsbook_id, r.captured_at) not in keep_odds
    ]
    prop_ids = [
        r.id
        for r in session.execute(
            select(p.id, p.player_id, p.market, p.sportsbook_id, p.captured_at).where(*where(p))
        )
        if (r.player_id, r.market, r.sportsbook_id, r.captured_at) not in keep_props
    ]
    session.commit()
    return (
        _delete_ids(session, o, odds_ids)
        + _delete_ids(session, p, prop_ids)
        + _delete_ids(session, e, event_ids)
    )


def prune_rows(session: Session, settings: Settings, now: datetime) -> tuple[int, datetime]:
    """Delete what has aged out. Returns (rows deleted, full-resolution cutoff)."""
    cutoff = now - timedelta(days=settings.snapshot_retention_days)
    keep_cutoff = now - timedelta(
        days=max(settings.snapshot_keep_days, settings.snapshot_retention_days)
    )
    previous = session.scalar(
        select(func.max(SnapshotRun.prune_cutoff)).where(
            SnapshotRun.kind == "prune", SnapshotRun.status == "ok"
        )
    )
    start = previous - WINDOW_OVERLAP if previous is not None else None

    window: list[Window] = [lambda m: m.captured_at < cutoff]
    if start is not None:
        window.append(lambda m: m.captured_at >= start)

    events: set[tuple[str, str]] = set()
    for model in (ArchivedEvent, ArchivedOdds, ArchivedProp):
        events.update(
            (r.provider, r.event_id)
            for r in session.execute(
                select(model.provider, model.event_id).where(*(c(model) for c in window)).distinct()
            )
        )
    session.commit()
    deleted = 0
    for provider_name, event_id in sorted(events):
        deleted += _prune_event(session, provider_name, event_id, window)
    for table in (ArchivedOdds, ArchivedProp, ArchivedEvent, ArchivedStatus, SnapshotRun):
        deleted += _delete_older(session, table, keep_cutoff)
    return deleted, cutoff


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
        deleted, cutoff = prune_rows(session, settings, now)
        run = new_run(provider, settings, "prune", now)
        run.rows_deleted = deleted
        run.prune_cutoff = cutoff
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


__all__ = ["DELETE_BATCH", "prune_archive", "prune_pass", "prune_rows"]
