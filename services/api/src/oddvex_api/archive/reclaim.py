"""Returning index space to the disk on PostgreSQL (snapshot archive, P0.1).

**Why.** The retention prune deletes most rows of a finished game but keeps a few (its
first, closing and last captures and the bet anchors). In a B-tree those kept entries are
scattered over the game's old pages. A page is given back for reuse only when it is
completely empty, so each pruned game leaves pages that are nearly empty, never empty and
never filled again (new games sort elsewhere). ``VACUUM`` cannot merge them. Measured
before this module existed: about 12 MB of index per synthetic day that nothing
reclaimed. The table files themselves do reuse the space the prune frees.

**What.** After each successful prune, and on every capture that found the files over
``snapshot_max_disk_bytes``, ``reclaim_pass`` compares each archive index with the size
its rows need (``INDEX_ROW_BYTES``) and rebuilds the ones that have grown past
``RECLAIM_FACTOR`` times that, one at a time, with ``REINDEX INDEX CONCURRENTLY``. The
rebuilt index is dense and the old one's file is removed, so the space really returns to
the disk. On any other database (SQLite) this module does nothing.

**How it stays safe on a shared server.**

- *Locks.* ``REINDEX INDEX CONCURRENTLY`` holds ``SHARE UPDATE EXCLUSIVE`` on the table
  and the index: reads, inserts and deletes go on; only ``VACUUM`` of that table and
  schema changes wait. It waits for older transactions at three points; ``lock_timeout``
  (``LOCK_TIMEOUT_SECONDS``) ends such a wait, and ``statement_timeout``
  (``STATEMENT_TIMEOUT_SECONDS``) ends a rebuild that takes too long.
- *Never with a capture or a prune.* It runs only inside ``capture.capture_pass``, which
  holds the archive's advisory lock for the whole pass, after the capture and the prune
  have committed.
- *Never in a transaction.* It opens its own connection in autocommit mode and checks
  that before every statement (``_require_autocommit``); PostgreSQL also refuses
  ``REINDEX CONCURRENTLY`` inside a transaction block. The connection is closed for
  good afterwards, so its settings never reach the pool.
- *Interrupted.* A rebuild that is cancelled or killed leaves an invalid index named
  ``<name>_ccnew`` (or ``_ccold``) beside the working one. Queries ignore it; inserts
  still maintain it. Every capture pass looks for invalid indexes on the archive tables
  and drops them (``DROP INDEX CONCURRENTLY``) before anything is rebuilt. If one cannot
  be dropped yet (an old transaction is still open) nothing is rebuilt in that pass, and
  a pass stops rebuilding at its first failure, so at most one such index exists.
- *Bounded.* One index at a time: the extra disk is one new copy of that index plus the
  sort's temporary files, the write-ahead log about one copy. ``maintenance_work_mem``
  is set to ``WORK_MEM_MB`` and parallel workers are off, so a rebuild uses one core and
  a known amount of memory. A pass starts no new rebuild after ``BUDGET_SECONDS``, and
  an index is rebuilt at most once per ``MIN_INTERVAL`` unless the files are over the
  ceiling. The measured figures are in docs/features/p0-1.md, "Bounds".
- *Recorded.* A pass that rebuilt, dropped or failed writes a ``reclaim`` run whose
  ``detail`` holds the index names and byte counts; the administrators' statistics show
  the latest one.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Connection, Engine, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from ..config import Settings
from ..db import ARCHIVE_MODELS, SnapshotRun, utcnow
from ..providers import SportsDataProvider
from .capture import RunSummary, new_run

logger = logging.getLogger("oddvex.archive")

#: The promise this module keeps, measured and tested: at its largest the archive's files
#: (``pg_total_relation_size`` of the five tables) are within this times the largest
#: counted size (``capture.archive_bytes``) the archive has held. The table files never
#: shrink, so after a prune the files stay near that largest size while the counted size
#: falls; what must not happen is growth beyond it, prune after prune.
STATED_FILES_FACTOR = 1.25
#: An index is rebuilt when it is larger than this times the size its rows need as they
#: are normally written (the first figure of ``INDEX_ROW_BYTES``).
RECLAIM_FACTOR = 1.3
#: While the files are over ``snapshot_max_disk_bytes``: larger than this times the size
#: a freshly rebuilt index needs (the second figure), so everything a rebuild can release
#: is released.
RECLAIM_FACTOR_FULL = 1.1
#: An index is not rebuilt for less than this.
MIN_EXCESS_BYTES = 1_048_576
#: A new index: one metadata page and one root page.
INDEX_BASE_BYTES = 16_384
#: An index is rebuilt at most once in this time, unless the files are over the ceiling.
MIN_INTERVAL = timedelta(hours=24)
#: Seconds a rebuild or a drop may wait for a lock or for older transactions.
LOCK_TIMEOUT_SECONDS = 10
#: Seconds one rebuild may take.
STATEMENT_TIMEOUT_SECONDS = 120
#: A pass starts no new rebuild once it has run this long.
BUDGET_SECONDS = 60
#: ``maintenance_work_mem`` for a rebuild, in megabytes (the database container has 512).
WORK_MEM_MB = 32
#: A rebuild of at least this many rows also tells what a dense index of this data needs
#: per row; the larger of that and the measured figure below is used from then on, so a
#: feed with longer identifiers does not make every check ask for a rebuild.
CALIBRATION_MIN_ROWS = 10_000
#: Reclaim runs read back for the last rebuild of each index.
HISTORY_RUNS = 50

#: Bytes per row of each archive index: (as normally written, freshly rebuilt). Measured
#: on PostgreSQL 16 after two synthetic days (244,438 odds rows, 85,471 prop rows, 15,440
#: event rows), before and after ``REINDEX`` (docs/features/p0-1.md, "Bounds"). The
#: status and run figures are estimates from the like-shaped indexes above them: no
#: status source exists yet (P0.5) and two days hold only 528 runs.
INDEX_ROW_BYTES: dict[str, tuple[float, float]] = {
    "pk_odds_snapshots": (22.6, 22.6),
    "uq_odds_snapshots_key": (125.1, 79.2),
    "ix_odds_snapshots_captured_at": (8.1, 7.2),
    "pk_prop_snapshots": (22.6, 22.6),
    "uq_prop_snapshots_key": (132.8, 96.5),
    "ix_prop_snapshots_event_captured": (11.4, 7.8),
    "ix_prop_snapshots_captured_at": (9.4, 7.4),
    "pk_event_snapshots": (23.9, 23.9),
    "uq_event_snapshots_key": (91.8, 60.0),
    "ix_event_snapshots_captured_at": (9.0, 8.5),
    "pk_snapshot_runs": (22.6, 22.6),
    "ix_snapshot_runs_kind_provider_captured": (108.6, 77.6),
    "pk_status_snapshots": (22.6, 22.6),
    "ix_status_snapshots_event": (91.8, 60.0),
    "ix_status_snapshots_player": (91.8, 60.0),
    "ix_status_snapshots_captured_at": (9.0, 8.5),
}


class NotAutocommit(RuntimeError):
    """An index statement was about to run on a connection that is not in autocommit
    mode, where it would be inside a transaction."""


@dataclass(frozen=True)
class IndexState:
    """One index of an archive table as the catalog shows it."""

    name: str
    table: str
    size: int
    valid: bool


@dataclass(frozen=True)
class Rebuild:
    """One index the plan wants rebuilt, and why."""

    name: str
    table: str
    size: int
    rows: int
    expected: int


@dataclass
class Outcome:
    """What one pass did."""

    rebuilt: dict[str, list[int]] = field(default_factory=dict)  # name: [before, after, rows]
    dropped: dict[str, int] = field(default_factory=dict)  # name: size
    failed: dict[str, str] = field(default_factory=dict)  # name: exception class
    skipped: list[str] = field(default_factory=list)  # left for a later pass

    @property
    def freed_bytes(self) -> int:
        rebuilt = sum(before - after for before, after, _rows in self.rebuilt.values())
        return rebuilt + sum(self.dropped.values())

    def detail(self, over_ceiling: bool) -> dict[str, Any]:
        return {
            "rebuilt": self.rebuilt,
            "dropped": self.dropped,
            "failed": self.failed,
            "skipped": self.skipped,
            "freed_bytes": self.freed_bytes,
            "over_ceiling": over_ceiling,
        }


def _tables() -> list[str]:
    return [model.__tablename__ for model in ARCHIVE_MODELS]


def index_states(connection: Connection) -> list[IndexState]:
    """Every index on the archive tables, with its size and whether it is valid."""
    rows = connection.execute(
        text(
            "SELECT c.relname, t.relname, pg_relation_size(c.oid), i.indisvalid "
            "FROM pg_index i "
            "JOIN pg_class c ON c.oid = i.indexrelid "
            "JOIN pg_class t ON t.oid = i.indrelid "
            "WHERE t.relname = ANY(:tables) AND pg_table_is_visible(t.oid) "
            "ORDER BY c.relname"
        ),
        {"tables": _tables()},
    )
    return [IndexState(name, table, int(size), bool(valid)) for name, table, size, valid in rows]


def leftover_indexes(states: list[IndexState]) -> list[IndexState]:
    """Invalid indexes that are not part of the schema: what an interrupted concurrent
    rebuild leaves behind (``<name>_ccnew``, ``<name>_ccold``, with or without a number)."""
    return [s for s in states if not s.valid and s.name not in INDEX_ROW_BYTES]


def expected_bytes(name: str, rows: int, calibrated: float | None = None) -> tuple[int, int]:
    """(as normally written, freshly rebuilt) bytes an index needs for ``rows`` rows.
    ``calibrated`` is the bytes per row a past rebuild of this index really produced."""
    normal, dense = INDEX_ROW_BYTES[name]
    per_row = max(dense, calibrated) if calibrated is not None else dense
    return (
        INDEX_BASE_BYTES + int(rows * per_row * normal / dense),
        INDEX_BASE_BYTES + int(rows * per_row),
    )


def _history(session: Session, provider_name: str) -> dict[str, tuple[datetime, float | None]]:
    """Per index, when it was last rebuilt and the bytes per row that rebuild produced
    (``None`` when it held too few rows to tell)."""
    found: dict[str, tuple[datetime, float | None]] = {}
    runs = session.execute(
        select(SnapshotRun.captured_at, SnapshotRun.detail)
        .where(SnapshotRun.kind == "reclaim", SnapshotRun.provider == provider_name)
        .order_by(SnapshotRun.captured_at.desc(), SnapshotRun.id.desc())
        .limit(HISTORY_RUNS)
    )
    for captured_at, detail in runs:
        for name, figures in ((detail or {}).get("rebuilt") or {}).items():
            if name in found or len(figures) != 3:
                continue
            _before, after, rows = figures
            per_row = (after - INDEX_BASE_BYTES) / rows if rows >= CALIBRATION_MIN_ROWS else None
            found[name] = (captured_at, per_row)
    return found


def plan_rebuilds(
    session: Session,
    provider_name: str,
    states: list[IndexState],
    now: datetime,
    *,
    over_ceiling: bool = False,
    force: bool = False,
) -> list[Rebuild]:
    """The indexes to rebuild, largest excess first. An invalid index of the schema itself
    (which no interrupted concurrent rebuild leaves, but a failed manual one could) is
    always rebuilt. ``force`` ignores ``MIN_INTERVAL``, not the sizes."""
    counts = {
        model.__tablename__: int(session.scalar(select(func.count()).select_from(model)) or 0)
        for model in ARCHIVE_MODELS
    }
    history = _history(session, provider_name)
    wanted: list[tuple[int, Rebuild]] = []
    for state in states:
        if state.name not in INDEX_ROW_BYTES:
            continue
        rows = counts[state.table]
        last = history.get(state.name)
        normal, dense = expected_bytes(state.name, rows, last[1] if last else None)
        if over_ceiling:
            limit = max(int(RECLAIM_FACTOR_FULL * dense), dense + MIN_EXCESS_BYTES)
        else:
            limit = max(int(RECLAIM_FACTOR * normal), normal + MIN_EXCESS_BYTES)
        recently = last is not None and now - last[0] < MIN_INTERVAL
        if state.valid and (state.size <= limit or (recently and not (over_ceiling or force))):
            continue
        wanted.append(
            (state.size - dense, Rebuild(state.name, state.table, state.size, rows, dense))
        )
    return [rebuild for _excess, rebuild in sorted(wanted, key=lambda w: (-w[0], w[1].name))]


def _require_autocommit(connection: Connection) -> None:
    """The driver connection itself must be in autocommit mode: then no statement sent
    on it is inside a transaction."""
    driver = connection.connection.dbapi_connection
    if getattr(driver, "autocommit", False) is not True:
        raise NotAutocommit("index rebuilds and drops run in autocommit mode only")


def _quoted(connection: Connection, name: str) -> str:
    return connection.dialect.identifier_preparer.quote(name)


def rebuild_index(connection: Connection, name: str) -> None:
    """``REINDEX INDEX CONCURRENTLY`` on an autocommit connection, and only there."""
    _require_autocommit(connection)
    connection.exec_driver_sql(f"REINDEX INDEX CONCURRENTLY {_quoted(connection, name)}")


def drop_leftover(connection: Connection, name: str) -> None:
    """``DROP INDEX CONCURRENTLY`` of an invalid leftover: it waits for older transactions
    (at most ``lock_timeout``) instead of locking the table."""
    _require_autocommit(connection)
    if name in INDEX_ROW_BYTES:
        raise ValueError(f"{name} is an index of the schema, not a leftover")
    connection.exec_driver_sql(f"DROP INDEX CONCURRENTLY IF EXISTS {_quoted(connection, name)}")


def _error(exc: DBAPIError) -> str:
    return type(exc.orig).__name__ if exc.orig is not None else type(exc).__name__


def _drop_leftovers(connection: Connection, outcome: Outcome) -> bool:
    """Drop every leftover. False when one could not be dropped."""
    clean = True
    for state in leftover_indexes(index_states(connection)):
        try:
            drop_leftover(connection, state.name)
            outcome.dropped[state.name] = outcome.dropped.get(state.name, 0) + state.size
        except DBAPIError as exc:
            outcome.failed[state.name] = _error(exc)
            clean = False
    return clean


def execute(engine: Engine, plan: list[Rebuild]) -> Outcome:
    """Drop leftovers, then rebuild the planned indexes one at a time, on a connection of
    its own in autocommit mode."""
    outcome = Outcome()
    started = time.monotonic()
    with engine.connect() as pooled:
        connection = pooled.execution_options(isolation_level="AUTOCOMMIT")
        try:
            _require_autocommit(connection)
            connection.exec_driver_sql(f"SET lock_timeout = '{LOCK_TIMEOUT_SECONDS}s'")
            connection.exec_driver_sql(f"SET statement_timeout = '{STATEMENT_TIMEOUT_SECONDS}s'")
            connection.exec_driver_sql(f"SET maintenance_work_mem = '{WORK_MEM_MB}MB'")
            connection.exec_driver_sql("SET max_parallel_maintenance_workers = 0")
            if not _drop_leftovers(connection, outcome):
                outcome.skipped = [rebuild.name for rebuild in plan]
                return outcome
            for position, rebuild in enumerate(plan):
                if time.monotonic() - started > BUDGET_SECONDS:
                    outcome.skipped = [r.name for r in plan[position:]]
                    break
                try:
                    rebuild_index(connection, rebuild.name)
                except DBAPIError as exc:
                    outcome.failed[rebuild.name] = _error(exc)
                    outcome.skipped = [r.name for r in plan[position + 1 :]]
                    # What the failed rebuild left behind, if it can be dropped already.
                    _drop_leftovers(connection, outcome)
                    break
                sizes = {state.name: state.size for state in index_states(connection)}
                outcome.rebuilt[rebuild.name] = [
                    rebuild.size,
                    sizes.get(rebuild.name, rebuild.size),
                    rebuild.rows,
                ]
        finally:
            # Not back to the pool: the session settings above end with the connection.
            pooled.detach()
    return outcome


def reclaim_pass(
    engine: Engine,
    provider: SportsDataProvider,
    settings: Settings,
    *,
    due: bool,
    over_ceiling: bool = False,
    force: bool = False,
) -> RunSummary | None:
    """Look for leftovers on every call; when ``due`` (a prune has just run), the files
    are over the ceiling, or ``force``, also for indexes to rebuild. ``None`` when there
    was nothing to do, and always on a database other than PostgreSQL. Call it only
    while holding the archive's advisory lock (``capture.capture_pass`` does)."""
    if engine.dialect.name != "postgresql":
        return None
    now = provider.now()
    with Session(engine, expire_on_commit=False) as session:
        states = index_states(session.connection())
        plan = (
            plan_rebuilds(
                session, provider.name, states, now, over_ceiling=over_ceiling, force=force
            )
            if due or over_ceiling or force
            else []
        )
        session.rollback()
    if not plan and not leftover_indexes(states):
        return None
    run = new_run(provider, settings, "reclaim", now)
    try:
        outcome = execute(engine, plan)
    except DBAPIError as exc:
        outcome = Outcome(failed={"connection": _error(exc)})
    if outcome.failed:
        run.status = "failed"
        logger.warning("snapshot_reclaim_failed", extra={"indexes": sorted(outcome.failed)})
    run.detail = outcome.detail(over_ceiling)
    run.finished_at = utcnow()
    with Session(engine, expire_on_commit=False) as session:
        session.add(run)
        session.commit()
        return RunSummary.of(run)


__all__ = [
    "BUDGET_SECONDS",
    "INDEX_ROW_BYTES",
    "LOCK_TIMEOUT_SECONDS",
    "MIN_EXCESS_BYTES",
    "MIN_INTERVAL",
    "RECLAIM_FACTOR",
    "RECLAIM_FACTOR_FULL",
    "STATED_FILES_FACTOR",
    "STATEMENT_TIMEOUT_SECONDS",
    "WORK_MEM_MB",
    "IndexState",
    "NotAutocommit",
    "Outcome",
    "Rebuild",
    "drop_leftover",
    "execute",
    "expected_bytes",
    "index_states",
    "leftover_indexes",
    "plan_rebuilds",
    "rebuild_index",
    "reclaim_pass",
]
