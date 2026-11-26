"""Capture passes of the snapshot archive.

One pass (``capture_pass``), run by ``scripts/capture_snapshots.py`` in the worker loop:

1. Nothing at all happens while the ``snapshot_archive`` flag is off.
2. On PostgreSQL an advisory lock makes sure two passes never overlap.
3. Every timestamp is the provider's clock (``provider.now()``).
4. Odds are captured when the last odds capture is at least
   ``snapshot_odds_interval_seconds`` old, less ``INTERVAL_SLACK_SECONDS`` for the drift of
   the 120 s loop; props likewise with ``snapshot_props_interval_seconds``.
5. At ``snapshot_max_bytes`` capture stops with a ``skipped_full`` run; the prune goes on.
   The size is the rows held times measured bytes per row (``ROW_BYTES``), not the size
   of the files: on PostgreSQL a delete and a plain VACUUM make room for new rows but do
   not shrink the files, so a file-size cap alone would never release after the prune.
   On PostgreSQL capture also stops while the files themselves (tables and indexes) are
   at ``snapshot_max_disk_bytes``, a hard ceiling above anything the counted cap allows;
   index rebuilds (``archive/reclaim.py``) are what brings the files back under it.
6. In scope: live events whose start time passed at most ``LIVE_GRACE_HOURS`` ago, and
   upcoming ones starting within ``snapshot_horizon_hours`` whose start time passed at
   most ``UPCOMING_GRACE_HOURS`` ago.
7. A quote or offer is written only when it differs from the latest stored row for its
   key; a key that disappears gets a tombstone row, and so does every prop offer of a
   game that has left scope. An unchanged prop offer is stored again at the first props
   capture after its latest row is ``PROP_REFRESH_HOURS`` old; the props read looks back
   at least that far plus its gap limit, so it finds every open offer. Inserts go in
   chunks of ``INSERT_CHUNK``, one transaction per kind. A failed kind is rolled back
   and recorded as a ``failed`` run with the exception's class name only.
8. The prune (``archive/prune.py``) runs when it is due.
9. On PostgreSQL, anything an interrupted index rebuild left is dropped and, unless the
   capture or the prune of this pass failed, bloated indexes are rebuilt
   (``archive/reclaim.py``), still inside the pass's advisory lock.

The run row is built before it is inserted, with its counters already set: archive rows,
runs included, are never updated (``archive/guard.py``).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field, model_validator
from sqlalchemy import Engine, and_, func, insert, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..config import SNAPSHOT_PROP_REFRESH_HOURS, Settings
from ..db import (
    ARCHIVE_MODELS,
    ArchivedEvent,
    ArchivedOdds,
    ArchivedProp,
    ArchivedStatus,
    SnapshotRun,
    utcnow,
)
from ..flags import service as flags
from ..providers import Event, OddsSnapshot, PropOffer, SportsDataProvider
from ..providers.base import ProviderRecord

logger = logging.getLogger("oddvex.archive")

FLAG = "snapshot_archive"
#: Changes when the capture rules change.
ARCHIVE_VERSION = 1
#: Absorbs the drift of the worker loop: with a 120 s loop and a 360 s interval the
#: third turn after a capture is a few seconds short of 360 s.
INTERVAL_SLACK_SECONDS = 15
#: Rows per INSERT statement.
INSERT_CHUNK = 500
#: Bytes per stored row, heap, keys and indexes, measured on PostgreSQL 16 with
#: ``pg_total_relation_size`` after ``VACUUM ANALYZE`` (docs/features/p0-1.md, "Bounds").
#: The status figure is an estimate: no status source exists yet to measure (P0.5).
ROW_BYTES: dict[str, int] = {
    "odds_snapshots": 415,
    "prop_snapshots": 395,
    "event_snapshots": 349,
    "status_snapshots": 400,
    "snapshot_runs": 388,
}
#: An unchanged prop offer is stored again at the first props capture after its latest
#: row is this old. The props read's look-back is never shorter than this plus the props
#: gap limit (``Settings.snapshot_prop_lookback_seconds``), so it finds every open offer.
PROP_REFRESH_HOURS = SNAPSHOT_PROP_REFRESH_HOURS
#: ``pg_try_advisory_lock`` key held for the length of one pass (72 for MED-72).
ADVISORY_LOCK_KEY = 72001
#: An event the provider still calls ``upcoming`` this many hours after its start time
#: (a postponed game whose status was never updated) is no longer captured.
UPCOMING_GRACE_HOURS = 6
#: Nor is an event the provider still calls ``live`` this many hours after its start time
#: (a finished game whose status was never updated). Without it such a game would never
#: leave scope: the prune reduces a game only once its last capture has aged out, so its
#: rows would stay at full resolution and grow until the cap stopped all capture.
LIVE_GRACE_HOURS = 24

RunKind = Literal["odds", "props", "status", "prune", "reclaim"]
StatusKind = Literal["lineup", "injury", "news", "weather"]
StatusValue = Literal[
    "expected",
    "confirmed",
    "out",
    "doubtful",
    "questionable",
    "probable",
    "active",
    "reported",
    "unknown",
]


class StatusRecord(ProviderRecord):
    """One lineup, injury, news or weather status, as a P0.5 provider will supply it.

    A status, a source name and times only: no article or headline text.
    """

    event_id: str | None = Field(default=None, max_length=64)
    team_id: str | None = Field(default=None, max_length=64)
    player_id: str | None = Field(default=None, max_length=64)
    kind: StatusKind
    status: StatusValue
    source: str = Field(min_length=1, max_length=120)
    reported_at: datetime | None = None

    @model_validator(mode="after")
    def _has_a_subject(self) -> StatusRecord:
        if not (self.event_id or self.team_id or self.player_id):
            raise ValueError("a status record names an event, a team or a player")
        return self


@dataclass(frozen=True)
class RunSummary:
    """What one run did, as recorded in ``snapshot_runs``."""

    run_id: int
    kind: str
    status: str
    captured_at: datetime
    events_in_scope: int
    rows_written: int
    rows_unchanged: int
    rows_deleted: int
    #: A ``reclaim`` run's figures (``archive/reclaim.py``); a failed run's error class.
    detail: dict[str, Any] | None = None

    @classmethod
    def of(cls, run: SnapshotRun) -> RunSummary:
        return cls(
            run_id=run.id,
            kind=run.kind,
            status=run.status,
            captured_at=run.captured_at,
            events_in_scope=run.events_in_scope,
            rows_written=run.rows_written,
            rows_unchanged=run.rows_unchanged,
            rows_deleted=run.rows_deleted,
            detail=run.detail,
        )


@dataclass
class PassReport:
    """The outcome of one pass. ``None`` for a kind that was not due."""

    enabled: bool
    locked: bool = False
    #: Capture was due and was skipped: the archive is at one of its two limits.
    full: bool = False
    #: The limit reached was the size of the files (``snapshot_max_disk_bytes``).
    over_ceiling: bool = False
    odds: RunSummary | None = None
    props: RunSummary | None = None
    prune: RunSummary | None = None
    reclaim: RunSummary | None = None

    @property
    def failed(self) -> bool:
        return any(
            r is not None and r.status == "failed"
            for r in (self.odds, self.props, self.prune, self.reclaim)
        )


# ------------------------------------------------------------------ helpers
def in_scope(provider: SportsDataProvider, now: datetime, settings: Settings) -> list[Event]:
    """Live events and upcoming events that start within the horizon. Final events are
    not captured: their last rows from before the start are the closing rows. An event
    still ``upcoming`` more than ``UPCOMING_GRACE_HOURS`` after its start time, or still
    ``live`` more than ``LIVE_GRACE_HOURS`` after it, is left out, so a game whose status
    the provider never updates is not captured forever."""
    horizon = now + timedelta(hours=settings.snapshot_horizon_hours)
    grace = now - timedelta(hours=UPCOMING_GRACE_HOURS)
    live_grace = now - timedelta(hours=LIVE_GRACE_HOURS)
    return [
        e
        for e in provider.list_events()
        if (e.status == "live" and e.start_time >= live_grace)
        or (e.status == "upcoming" and grace <= e.start_time <= horizon)
    ]


def last_run_at(session: Session, provider_name: str, kind: str) -> datetime | None:
    """When the last run of ``kind`` that did not fail was captured. A failed run does not
    count, so the next turn of the loop tries again."""
    return session.scalar(
        select(func.max(SnapshotRun.captured_at)).where(
            SnapshotRun.kind == kind,
            SnapshotRun.provider == provider_name,
            SnapshotRun.status.in_(("ok", "skipped_full")),
        )
    )


def is_due(session: Session, provider_name: str, kind: str, now: datetime, interval: int) -> bool:
    last = last_run_at(session, provider_name, kind)
    return last is None or (now - last).total_seconds() >= interval - INTERVAL_SLACK_SECONDS


def archive_bytes(session: Session) -> int:
    """The data the archive holds, as the cap counts it: each table's row count times its
    ``ROW_BYTES``. It falls as soon as the prune deletes rows, on every database."""
    return sum(
        int(session.scalar(select(func.count()).select_from(model)) or 0)
        * ROW_BYTES[model.__tablename__]
        for model in ARCHIVE_MODELS
    )


def archive_disk_bytes(session: Session) -> int | None:
    """On PostgreSQL, the size of the five tables' files with their indexes
    (``pg_total_relation_size``, so it includes anything an interrupted index rebuild
    left). The table files do not shrink after the prune (later rows reuse the freed
    space); the index files shrink when ``archive/reclaim.py`` rebuilds them. Capture
    stops while this is at ``snapshot_max_disk_bytes``. ``None`` elsewhere."""
    if session.get_bind().dialect.name != "postgresql":
        return None
    names = ", ".join(f"'{model.__tablename__}'" for model in ARCHIVE_MODELS)
    total = session.execute(
        text(
            "SELECT coalesce(sum(pg_total_relation_size(n::regclass)), 0) "
            f"FROM unnest(ARRAY[{names}]) AS n"
        )
    ).scalar()
    return int(total or 0)


def new_run(
    provider: SportsDataProvider,
    settings: Settings,
    kind: RunKind,
    now: datetime,
    status: str = "ok",
) -> SnapshotRun:
    return SnapshotRun(
        kind=kind,
        provider=provider.name,
        data_mode=provider.data_mode,
        captured_at=now,
        started_at=utcnow(),
        status=status,
        archive_version=ARCHIVE_VERSION,
        stale_pregame_seconds=settings.stale_pregame_seconds,
        stale_live_seconds=settings.stale_live_seconds,
        events_in_scope=0,
        rows_written=0,
        rows_unchanged=0,
        rows_deleted=0,
    )


def _insert(session: Session, model: type[Any], rows: Sequence[dict[str, Any]]) -> None:
    for start in range(0, len(rows), INSERT_CHUNK):
        session.execute(insert(model), list(rows[start : start + INSERT_CHUNK]))


def _write_run(
    session: Session, run: SnapshotRun, tables: Iterable[tuple[type[Any], list[dict[str, Any]]]]
) -> SnapshotRun:
    """Insert the run (to get its id), then its rows. Not committed."""
    run.finished_at = utcnow()
    session.add(run)
    session.flush()
    common = {"run_id": run.id, "captured_at": run.captured_at, "provider": run.provider}
    for model, rows in tables:
        _insert(session, model, [{**common, **row} for row in rows])
    return run


def guarded(
    session: Session,
    provider: SportsDataProvider,
    settings: Settings,
    kind: RunKind,
    now: datetime,
    work: Callable[[], SnapshotRun],
) -> RunSummary:
    """Run one kind in its own transaction. On any error roll back everything it wrote and
    record a ``failed`` run carrying only the exception's class name."""
    try:
        run = work()
        session.commit()
        return RunSummary.of(run)
    except Exception as exc:
        session.rollback()
        logger.warning("snapshot_run_failed", extra={"kind": kind, "error": type(exc).__name__})
        failed = new_run(provider, settings, kind, now, status="failed")
        failed.detail = {"error": type(exc).__name__}
        failed.finished_at = utcnow()
        session.add(failed)
        session.commit()
        return RunSummary.of(failed)


# --------------------------------------------------------------------- odds
_ODDS_COMPARED = ("status", "last_updated", "outcomes", "provider_id")
_PROP_COMPARED = (
    "status",
    "last_updated",
    "line",
    "over_american",
    "under_american",
    "provider_id",
)
_STATUS_COMPARED = ("status", "source", "reported_at", "provider_id")


def _same(previous: dict[str, Any], current: dict[str, Any], fields: Sequence[str]) -> bool:
    return all(previous[name] == current[name] for name in fields)


def _odds_values(snap: OddsSnapshot) -> dict[str, Any]:
    return {
        "event_id": snap.event_id,
        "market": snap.market,
        "sportsbook_id": snap.sportsbook_id,
        "status": snap.status,
        "last_updated": snap.last_updated,
        "outcomes": [[o.key, o.name, o.line, o.price_american] for o in snap.outcomes],
        "provider_id": snap.provider_id,
        "fetched_at": snap.fetched_at,
    }


def _event_values(event: Event) -> dict[str, Any]:
    return {
        "event_id": event.id,
        "league": event.league,
        "home_team_id": event.home_team_id,
        "away_team_id": event.away_team_id,
        "status": event.status,
        "start_time": event.start_time,
        "score_home": event.score.home if event.score else None,
        "score_away": event.score.away if event.score else None,
        "score_updated_at": event.score_updated_at,
        "period_text": event.period_text,
        "markets": list(event.markets),
        "provider_id": event.provider_id,
        "fetched_at": event.fetched_at,
    }


def _latest_odds(
    session: Session, provider_name: str, event_ids: Sequence[str]
) -> dict[tuple[str, str, str], dict[str, Any]]:
    """The latest stored row per (event, market, book) of these events, in one query."""
    if not event_ids:
        return {}
    o = ArchivedOdds
    newest = (
        select(o.event_id, o.market, o.sportsbook_id, func.max(o.captured_at).label("at"))
        .where(o.provider == provider_name, o.event_id.in_(event_ids))
        .group_by(o.event_id, o.market, o.sportsbook_id)
        .subquery()
    )
    rows = session.execute(
        select(
            o.event_id,
            o.market,
            o.sportsbook_id,
            o.status,
            o.last_updated,
            o.outcomes,
            o.provider_id,
        ).join(
            newest,
            and_(
                o.provider == provider_name,
                o.event_id == newest.c.event_id,
                o.market == newest.c.market,
                o.sportsbook_id == newest.c.sportsbook_id,
                o.captured_at == newest.c.at,
            ),
        )
    )
    return {(r.event_id, r.market, r.sportsbook_id): dict(r._mapping) for r in rows}


def capture_odds(
    session: Session,
    provider: SportsDataProvider,
    settings: Settings,
    now: datetime,
    events: Sequence[Event],
) -> SnapshotRun:
    """One odds run: an event row per in-scope event, and every changed quote."""
    current: dict[tuple[str, str, str], dict[str, Any]] = {}
    for event in events:
        for market in event.markets:
            for snap in provider.get_odds(event.id, market):
                current[(snap.event_id, snap.market, snap.sportsbook_id)] = _odds_values(snap)
    latest = _latest_odds(session, provider.name, [e.id for e in events])
    rows: list[dict[str, Any]] = []
    unchanged = 0
    for key, values in current.items():
        previous = latest.get(key)
        if previous is not None and _same(previous, values, _ODDS_COMPARED):
            unchanged += 1
        else:
            rows.append(values)
    for key, previous in latest.items():
        if key not in current and previous["status"] != "unavailable":
            rows.append(
                {
                    "event_id": key[0],
                    "market": key[1],
                    "sportsbook_id": key[2],
                    "status": "unavailable",
                    "last_updated": None,
                    "outcomes": [],
                    "provider_id": previous["provider_id"],
                    "fetched_at": now,
                }
            )
    event_rows = [_event_values(e) for e in events]
    run = new_run(provider, settings, "odds", now)
    run.events_in_scope = len(events)
    run.rows_written = len(rows) + len(event_rows)
    run.rows_unchanged = unchanged
    return _write_run(session, run, [(ArchivedEvent, event_rows), (ArchivedOdds, rows)])


# -------------------------------------------------------------------- props
def _line(value: float | None) -> Decimal | None:
    return None if value is None else Decimal(str(value)).quantize(Decimal("0.01"))


def _prop_values(offer: PropOffer) -> dict[str, Any]:
    return {
        "player_id": offer.player_id,
        "event_id": offer.event_id,
        "sportsbook_id": offer.sportsbook_id,
        "market": offer.market,
        "status": offer.status,
        "last_updated": offer.last_updated,
        "line": _line(offer.line),
        "over_american": offer.over_american,
        "under_american": offer.under_american,
        "provider_id": offer.provider_id,
        "fetched_at": offer.fetched_at,
    }


#: A prop offer's key: (player, event, market, book). The event is part of it, so a
#: player with two games in scope (a doubleheader) keeps both games' offers.
type PropKey = tuple[str, str, str, str]


def _latest_props(
    session: Session, provider_name: str, event_ids: Sequence[str]
) -> dict[PropKey, dict[str, Any]]:
    """The latest stored row per (player, event, market, book) of these events."""
    if not event_ids:
        return {}
    p = ArchivedProp
    newest = (
        select(
            p.player_id,
            p.event_id,
            p.market,
            p.sportsbook_id,
            func.max(p.captured_at).label("at"),
        )
        .where(p.provider == provider_name, p.event_id.in_(event_ids))
        .group_by(p.player_id, p.event_id, p.market, p.sportsbook_id)
        .subquery()
    )
    rows = session.execute(
        select(
            p.player_id,
            p.market,
            p.sportsbook_id,
            p.event_id,
            p.status,
            p.last_updated,
            p.line,
            p.over_american,
            p.under_american,
            p.provider_id,
            p.captured_at,
        ).join(
            newest,
            and_(
                p.provider == provider_name,
                p.player_id == newest.c.player_id,
                p.event_id == newest.c.event_id,
                p.market == newest.c.market,
                p.sportsbook_id == newest.c.sportsbook_id,
                p.captured_at == newest.c.at,
            ),
        )
    )
    return {(r.player_id, r.event_id, r.market, r.sportsbook_id): dict(r._mapping) for r in rows}


def _recent_prop_events(
    session: Session, provider_name: str, now: datetime, settings: Settings
) -> set[str]:
    """Events with a prop row in the props look-back: the games whose offers may still be
    stored as open, including games that have just left scope."""
    from .view import prop_lookback  # view imports helpers from this module

    p = ArchivedProp
    return set(
        session.scalars(
            select(p.event_id)
            .where(p.provider == provider_name, p.captured_at >= now - prop_lookback(settings))
            .distinct()
        )
    )


def capture_props(
    session: Session,
    provider: SportsDataProvider,
    settings: Settings,
    now: datetime,
    events: Sequence[Event],
) -> SnapshotRun:
    """One props run: every changed offer for an in-scope event, and a tombstone for every
    stored open offer that is gone, including all of a game's offers once it leaves
    scope (so a finished game's last offers are never read back as open)."""
    scope = {e.id for e in events}
    current: dict[PropKey, dict[str, Any]] = {}
    for player in provider.list_players():
        for offer in provider.get_prop_offers(player.id):
            if offer.event_id in scope:
                key = (offer.player_id, offer.event_id, offer.market, offer.sportsbook_id)
                current[key] = _prop_values(offer)
    recent = _recent_prop_events(session, provider.name, now, settings)
    latest = _latest_props(session, provider.name, sorted(scope | recent))
    refresh_before = now - timedelta(hours=PROP_REFRESH_HOURS)
    rows: list[dict[str, Any]] = []
    unchanged = 0
    for key, values in current.items():
        previous = latest.get(key)
        if (
            previous is not None
            and _same(previous, values, _PROP_COMPARED)
            and previous["captured_at"] > refresh_before
        ):
            unchanged += 1
        else:
            rows.append(values)
    for key, previous in latest.items():
        if key not in current and previous["status"] != "unavailable":
            rows.append(
                {
                    "player_id": key[0],
                    "event_id": key[1],
                    "sportsbook_id": key[3],
                    "market": key[2],
                    "status": "unavailable",
                    "last_updated": None,
                    "line": None,
                    "over_american": None,
                    "under_american": None,
                    "provider_id": previous["provider_id"],
                    "fetched_at": now,
                }
            )
    run = new_run(provider, settings, "props", now)
    run.events_in_scope = len(events)
    run.rows_written = len(rows)
    run.rows_unchanged = unchanged
    return _write_run(session, run, [(ArchivedProp, rows)])


# ------------------------------------------------------------------- status
def _status_key(row: Any) -> tuple[str | None, str | None, str | None, str]:
    return (row["event_id"], row["team_id"], row["player_id"], row["kind"])


def _latest_status(
    session: Session, provider_name: str, records: Sequence[StatusRecord]
) -> dict[tuple[str | None, str | None, str | None, str], dict[str, Any]]:
    """The latest stored row per (event, team, player, kind) for the subjects named: one
    grouped query per subject column, so a subject's history is never loaded whole."""
    events = {r.event_id for r in records if r.event_id}
    players = {r.player_id for r in records if r.player_id}
    teams = {r.team_id for r in records if r.team_id}
    s = ArchivedStatus
    found: dict[tuple[str | None, str | None, str | None, str], dict[str, Any]] = {}
    for column, values in ((s.event_id, events), (s.player_id, players), (s.team_id, teams)):
        if not values:
            continue
        newest = (
            select(s.event_id, s.team_id, s.player_id, s.kind, func.max(s.captured_at).label("at"))
            .where(s.provider == provider_name, column.in_(sorted(values)))
            .group_by(s.event_id, s.team_id, s.player_id, s.kind)
            .subquery()
        )
        rows = session.execute(
            select(
                s.event_id,
                s.team_id,
                s.player_id,
                s.kind,
                s.status,
                s.source,
                s.reported_at,
                s.provider_id,
                s.captured_at,
            )
            .join(
                newest,
                and_(
                    s.event_id.is_not_distinct_from(newest.c.event_id),
                    s.team_id.is_not_distinct_from(newest.c.team_id),
                    s.player_id.is_not_distinct_from(newest.c.player_id),
                    s.kind == newest.c.kind,
                    s.captured_at == newest.c.at,
                ),
            )
            .where(s.provider == provider_name)
            .order_by(s.captured_at, s.id)
        )
        for row in rows:
            mapping = dict(row._mapping)
            found[_status_key(mapping)] = mapping
    return found


def capture_status(
    session: Session,
    provider: SportsDataProvider,
    settings: Settings,
    records: Iterable[StatusRecord],
    now: datetime | None = None,
) -> SnapshotRun | None:
    """Store lineup and news status records, with the same rule as quotes: a row only when
    the record differs from the latest stored one for its subject and kind. Nothing calls
    this on a schedule until P0.5 supplies a source. ``None`` while the flag is off."""
    if not flags.is_enabled(session, FLAG, settings):
        return None
    now = now or provider.now()
    batch = list(records)

    def work() -> SnapshotRun:
        latest = _latest_status(session, provider.name, batch)
        rows: list[dict[str, Any]] = []
        unchanged = 0
        for record in batch:
            values = {
                "event_id": record.event_id,
                "team_id": record.team_id,
                "player_id": record.player_id,
                "kind": record.kind,
                "status": record.status,
                "source": record.source,
                "reported_at": record.reported_at,
                "provider_id": record.provider_id,
                "fetched_at": record.fetched_at,
            }
            previous = latest.get(_status_key(values))
            if previous is not None and _same(previous, values, _STATUS_COMPARED):
                unchanged += 1
                continue
            latest[_status_key(values)] = values
            rows.append(values)
        run = new_run(provider, settings, "status", now)
        run.rows_written = len(rows)
        run.rows_unchanged = unchanged
        return _write_run(session, run, [(ArchivedStatus, rows)])

    summary = guarded(session, provider, settings, "status", now, work)
    return session.get(SnapshotRun, summary.run_id)


# --------------------------------------------------------------------- pass
def run_pass(
    session: Session,
    provider: SportsDataProvider,
    settings: Settings,
    *,
    force: bool = False,
    capture: bool = True,
    prune: bool = True,
    force_prune: bool = False,
) -> PassReport:
    """One pass on an open session. ``force`` ignores the capture intervals and
    ``force_prune`` the prune's; ``capture=False`` only prunes."""
    from .prune import prune_pass  # prune imports helpers from this module

    report = PassReport(enabled=flags.is_enabled(session, FLAG, settings))
    if not report.enabled:
        session.rollback()
        return report
    now = provider.now()
    due = {
        "odds": force
        or is_due(session, provider.name, "odds", now, settings.snapshot_odds_interval_seconds),
        "props": force
        or is_due(session, provider.name, "props", now, settings.snapshot_props_interval_seconds),
    }
    if capture and any(due.values()):
        size = archive_bytes(session)
        disk = archive_disk_bytes(session)
        report.over_ceiling = disk is not None and disk >= settings.snapshot_max_disk_bytes
        report.full = size >= settings.snapshot_max_bytes or report.over_ceiling
        session.commit()
        if size >= settings.snapshot_max_bytes:
            logger.warning(
                "snapshot archive full: %d bytes >= cap %d", size, settings.snapshot_max_bytes
            )
        if report.over_ceiling:
            logger.warning(
                "snapshot archive files at the ceiling: %d bytes >= %d",
                disk,
                settings.snapshot_max_disk_bytes,
            )
        scope: list[list[Event]] = []

        def events() -> list[Event]:
            """The in-scope events, read once per pass inside the first kind's guard, so a
            provider error is recorded as that kind's failed run."""
            if not scope:
                scope.append(in_scope(provider, now, settings))
            return scope[0]

        workers: dict[RunKind, Callable[[], SnapshotRun]] = {
            "odds": lambda: capture_odds(session, provider, settings, now, events()),
            "props": lambda: capture_props(session, provider, settings, now, events()),
        }
        for kind, work in workers.items():
            if not due[kind]:
                continue
            if report.full:

                def skipped(kind: RunKind = kind) -> SnapshotRun:
                    run = new_run(provider, settings, kind, now, status="skipped_full")
                    return _write_run(session, run, [])

                work = skipped
            summary = guarded(session, provider, settings, kind, now, work)
            setattr(report, kind, summary)
            if summary.status == "failed":
                return report
    if prune:
        report.prune = prune_pass(session, provider, settings, force=force_prune)
    return report


def capture_pass(
    engine: Engine,
    provider: SportsDataProvider,
    settings: Settings,
    *,
    force: bool = False,
    capture: bool = True,
    prune: bool = True,
    force_prune: bool = False,
    reclaim: bool = True,
    force_reclaim: bool = False,
) -> PassReport:
    """One locked pass on its own connection. On PostgreSQL a session-level advisory lock
    is held on that connection for the whole pass (it survives the commits between kinds
    and is released when the pass ends or the connection drops); a pass that cannot take
    it does nothing. The index reclaim runs last, inside the same lock, once the capture
    and the prune have committed, so it is never started beside either. (A rebuild whose
    worker is killed goes on in the database server while the lock is released with the
    dead connection: the next pass can then capture beside it, which is safe, a
    concurrent rebuild being made to run beside writes.)"""
    from .reclaim import reclaim_pass  # reclaim imports helpers from this module

    with engine.connect() as connection:
        postgres = connection.dialect.name == "postgresql"
        with Session(bind=connection, expire_on_commit=False) as session:
            if not flags.is_enabled(session, FLAG, settings):
                return PassReport(enabled=False)
            session.rollback()
        if postgres:
            locked = connection.execute(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": ADVISORY_LOCK_KEY}
            ).scalar()
            connection.commit()
            if not locked:
                return PassReport(enabled=True, locked=True)
        try:
            with Session(bind=connection, expire_on_commit=False) as session:
                report = run_pass(
                    session,
                    provider,
                    settings,
                    force=force,
                    capture=capture,
                    prune=prune,
                    force_prune=force_prune,
                )
            # The pass's own connection must hold no transaction now: a concurrent
            # index rebuild waits for every older transaction to end.
            connection.rollback()
            if postgres and reclaim:
                # After a failed capture or prune nothing is rebuilt (the database or
                # the feed is in trouble; a rebuild is heavy work), but what an
                # interrupted rebuild left is still dropped.
                healthy = not report.failed
                pruned = report.prune is not None and report.prune.status == "ok"
                over_ceiling = report.over_ceiling
                if force_reclaim and healthy and not over_ceiling:
                    # ``--reclaim`` captures nothing, so the pass has not looked at the
                    # files yet: over the ceiling the lower bar applies here too.
                    with Session(bind=connection) as session:
                        disk = archive_disk_bytes(session)
                        session.rollback()
                    over_ceiling = disk is not None and disk >= settings.snapshot_max_disk_bytes
                try:
                    report.reclaim = reclaim_pass(
                        engine,
                        provider,
                        settings,
                        due=pruned and healthy,
                        over_ceiling=over_ceiling and healthy,
                        force=force_reclaim and healthy,
                    )
                except SQLAlchemyError as exc:
                    if healthy:
                        raise
                    # The pass has already failed and is recorded as such; if the
                    # database cannot even list its indexes, the clean-up waits.
                    logger.warning(
                        "snapshot_leftover_cleanup_skipped", extra={"error": type(exc).__name__}
                    )
            return report
        finally:
            if postgres:
                connection.rollback()
                connection.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": ADVISORY_LOCK_KEY}
                )
                connection.commit()


__all__ = [
    "ADVISORY_LOCK_KEY",
    "ARCHIVE_VERSION",
    "FLAG",
    "INSERT_CHUNK",
    "INTERVAL_SLACK_SECONDS",
    "LIVE_GRACE_HOURS",
    "PROP_REFRESH_HOURS",
    "ROW_BYTES",
    "UPCOMING_GRACE_HOURS",
    "PassReport",
    "RunSummary",
    "StatusRecord",
    "archive_bytes",
    "archive_disk_bytes",
    "capture_odds",
    "capture_pass",
    "capture_props",
    "capture_status",
    "in_scope",
    "is_due",
    "run_pass",
]
