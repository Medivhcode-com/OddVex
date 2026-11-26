"""Index space on PostgreSQL (``archive/reclaim.py``) and the ceiling on the archive's
files: the stated factor over prune cycles, both directions of the ceiling, what an
interrupted rebuild leaves and how the next pass cleans it up (a rebuild whose database
session is ended included), the locks a rebuild holds, when a pass rebuilds and when it
does not, the record of a run, and the no-op on SQLite."""

from __future__ import annotations

import threading
import time
from datetime import date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Connection, func, select, text
from sqlalchemy.exc import DBAPIError

from oddvex_api.archive import prune as prune_module
from oddvex_api.archive import reclaim
from oddvex_api.archive.capture import (
    ADVISORY_LOCK_KEY,
    PassReport,
    archive_bytes,
    archive_disk_bytes,
    capture_pass,
    new_run,
)
from oddvex_api.archive.reclaim import (
    INDEX_ROW_BYTES,
    STATED_FILES_FACTOR,
    IndexState,
    NotAutocommit,
    drop_leftover,
    expected_bytes,
    index_states,
    leftover_indexes,
    plan_rebuilds,
    rebuild_index,
    reclaim_pass,
)
from oddvex_api.archive.service import archive_stats, archived_odds
from oddvex_api.db import ARCHIVE_MODELS, ArchivedOdds, ArchivedProp, SnapshotRun
from oddvex_api.providers import Event, OddsSnapshot

from .archive_support import PREGAME, T0, ArchiveEnv, archive_env
from .conftest import EXTERNAL_DATABASE_URL
from .fakes import ControlledProvider

__all__ = ["archive_env"]

postgres_only = pytest.mark.skipif(
    not EXTERNAL_DATABASE_URL, reason="index rebuilds and the file ceiling exist on PostgreSQL only"
)
sqlite_only = pytest.mark.skipif(
    bool(EXTERNAL_DATABASE_URL), reason="the no-op is what every other database gets"
)
#: An index is a whole number of 8 kB pages, so in these small archives it may be a page
#: over a figure worked out per row.
PAGE_BYTES = 8192


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def sizes(env: ArchiveEnv) -> tuple[int, int]:
    """(counted bytes, bytes of the files)."""
    with env.session_factory() as db:
        disk = archive_disk_bytes(db)
        assert disk is not None
        return archive_bytes(db), disk


def vacuum(env: ArchiveEnv) -> None:
    """A plain VACUUM of every archive table: what autovacuum does once it runs (it waits
    for a fifth of a table's rows to be dead or new; docs/features/p0-1.md, "Bounds")."""
    with env.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        for model in ARCHIVE_MODELS:
            connection.execute(text(f"VACUUM {model.__tablename__}"))


def reclaim_runs(env: ArchiveEnv) -> list[SnapshotRun]:
    with env.session_factory() as db:
        return list(
            db.scalars(
                select(SnapshotRun).where(SnapshotRun.kind == "reclaim").order_by(SnapshotRun.id)
            )
        )


def states(env: ArchiveEnv) -> list[IndexState]:
    with env.engine.connect() as connection:
        return index_states(connection)


@pytest.fixture
def small_indexes(monkeypatch: pytest.MonkeyPatch) -> None:
    """These archives hold a few thousand rows: let an index be rebuilt for any excess,
    not only for a megabyte or more."""
    monkeypatch.setattr(reclaim, "MIN_EXCESS_BYTES", 0)


class FewGamesProvider(ControlledProvider):
    """Only each league's first game of a day is on the schedule (ten games in scope), so a
    pass is small and a cycle can hold many captures of the same games: the prune then
    deletes most of each game's rows and keeps a few, which is what leaves index pages
    nearly empty."""

    def list_events(
        self, league: str | None = None, status: str | None = None, on_date: date | None = None
    ) -> list[Event]:
        return [e for e in super().list_events(league, status, on_date) if e.id.endswith("_0")]


#: Captures per cycle, 360 s apart (three hours of the same games), and cycles.
PASSES = 30
CYCLES = 4


def cycle(
    env: ArchiveEnv, start: datetime, *, reclaim_indexes: bool
) -> tuple[int, int, PassReport]:
    """``PASSES`` captures from ``start`` (odds every pass, props hourly), the sizes at that
    peak, then, eight days on (every game of the cycle is past its seven days), a plain
    VACUUM, the prune and, when asked, the index reclaim in one pass as the worker runs
    it, and a plain VACUUM again."""
    for i in range(PASSES):
        env.provider.current = start + timedelta(seconds=360 * i)
        report = capture_pass(env.engine, env.provider, env.settings, prune=False)
        assert report.odds is not None and report.odds.status == "ok", report
    peak = sizes(env)
    env.provider.current = start + timedelta(days=8)
    vacuum(env)
    report = capture_pass(
        env.engine,
        env.provider,
        env.settings,
        capture=False,
        force_prune=True,
        reclaim=reclaim_indexes,
    )
    assert report.prune is not None and report.prune.status == "ok" and report.prune.rows_deleted
    vacuum(env)
    return (*peak, report)


@pytest.fixture
def few_games(archive_env: ArchiveEnv) -> ArchiveEnv:
    archive_env.provider = FewGamesProvider()
    archive_env.settings = archive_env.settings.model_copy(
        update={"snapshot_props_interval_seconds": 3600}
    )
    return archive_env


# ------------------------------------------------------------- the stated factor
@postgres_only
def test_the_files_stay_within_the_stated_factor_of_the_counted_size_over_prune_cycles(
    few_games: ArchiveEnv, small_indexes: None
) -> None:
    """Regression (review round 3): each prune left nearly empty index pages that nothing
    reused, so the files grew by an index's worth per cycle while the counted size stayed
    flat. With the reclaim, at every peak the files are within ``STATED_FILES_FACTOR`` of
    the largest counted size so far. (The long version of this measurement, eight cycles
    of two synthetic days, is a documented script: docs/features/p0-1.md, "Bounds".)"""
    env = few_games
    # What the files hold before a single row (empty tables, one or two pages per index),
    # measured here: that much is allowed on top of the factor in these small archives.
    empty = sizes(env)[1]
    assert 0 < empty < 262_144
    largest = 0
    for number in range(CYCLES):
        counted, disk, report = cycle(env, T0 + timedelta(days=9 * number), reclaim_indexes=True)
        largest = max(largest, counted)
        assert disk <= STATED_FILES_FACTOR * largest + empty, (number, counted, disk)
        assert report.reclaim is not None and report.reclaim.status == "ok", report
        detail = report.reclaim.detail or {}
        assert detail["rebuilt"] and detail["freed_bytes"] > 0 and not detail["failed"]
        # After the pass no index is larger than 1.3 times the size its rows need: every
        # one that was has been rebuilt, not only the first or the largest.
        with env.session_factory() as db:
            rows = {
                model.__tablename__: db.scalar(select(func.count()).select_from(model)) or 0
                for model in ARCHIVE_MODELS
            }
        for state in states(env):
            needed = expected_bytes(state.name, rows[state.table])[0]
            assert state.size <= 1.3 * needed + PAGE_BYTES, (number, state, needed)
    assert leftover_indexes(states(env)) == []
    assert all(state.valid for state in states(env))


@postgres_only
def test_without_the_reclaim_the_same_cycles_leave_the_stated_factor(
    few_games: ArchiveEnv,
) -> None:
    """The measurement above can fail: the same cycles with the reclaim switched off (the
    code as it was at review round 3) leave the stated factor by the third peak."""
    env = few_games
    empty = sizes(env)[1]
    largest = 0
    ratios = []
    for number in range(3):
        counted, disk, report = cycle(env, T0 + timedelta(days=9 * number), reclaim_indexes=False)
        assert report.reclaim is None
        largest = max(largest, counted)
        ratios.append((disk - empty) / largest)
    assert ratios[-1] > STATED_FILES_FACTOR and ratios == sorted(ratios), ratios


# ------------------------------------------------------------------ the ceiling
@postgres_only
def test_capture_stops_at_the_file_ceiling_and_resumes_once_space_is_really_released(
    archive_env: ArchiveEnv, small_indexes: None
) -> None:
    """Both directions of the hard ceiling on the files. Capture stops while the files
    are at ``snapshot_max_disk_bytes``, whatever the counted size. The prune and a plain
    VACUUM do not shrink the files, so alone they would never release it (review round
    2); the index rebuild does, and the next capture runs."""
    env = archive_env
    for i in range(3):
        report = env.capture(at(360 * i))
        assert report.odds is not None and report.odds.status == "ok"
    counted, disk = sizes(env)
    env.settings = env.settings.model_copy(update={"snapshot_max_disk_bytes": disk})
    assert counted < env.settings.snapshot_max_bytes

    # Stops: the files are at the ceiling, the counted size is far under its cap.
    env.provider.current = at(1080)
    report = capture_pass(env.engine, env.provider, env.settings, force=True, reclaim=False)
    assert report.full is True and report.over_ceiling is True
    assert report.odds is not None and report.odds.status == "skipped_full"
    assert report.props is not None and report.props.status == "skipped_full"

    # Eight days on the prune deletes nearly every row. Without the index rebuild the
    # files are as large as before, and capture stays stopped.
    env.provider.current = T0 + timedelta(days=8)
    report = capture_pass(env.engine, env.provider, env.settings, force=True, reclaim=False)
    assert report.prune is not None and report.prune.rows_deleted > 0
    assert report.odds is not None and report.odds.status == "skipped_full"
    vacuum(env)
    counted_after, disk_after = sizes(env)
    assert counted_after < counted / 2
    assert disk_after >= disk

    # The next pass finds the files over the ceiling and rebuilds the indexes: the space
    # really returns to the disk.
    env.provider.current += timedelta(seconds=360)
    report = capture_pass(env.engine, env.provider, env.settings, force=True)
    assert report.odds is not None and report.odds.status == "skipped_full"
    assert report.reclaim is not None and report.reclaim.status == "ok", report
    detail = report.reclaim.detail or {}
    assert detail["over_ceiling"] is True and detail["freed_bytes"] > 0
    released = sizes(env)[1]
    assert released < disk and released == disk_after - detail["freed_bytes"]

    # Resumes.
    env.provider.current += timedelta(seconds=360)
    report = capture_pass(env.engine, env.provider, env.settings, force=True)
    assert report.full is False and report.over_ceiling is False
    assert report.odds is not None and report.odds.status == "ok"
    assert report.odds.rows_written > 0


# --------------------------------------------------- interruption and the locks
class Blocker:
    """A transaction with a snapshot older than the rebuild, as a long report or a dump
    holds one: a concurrent rebuild has to wait for it to end."""

    def __init__(self, env: ArchiveEnv) -> None:
        self.connection = env.engine.connect()
        self.connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        self.connection.execute(text("SELECT count(*) FROM odds_snapshots")).scalar()

    def release(self) -> None:
        self.connection.rollback()
        self.connection.close()


@pytest.fixture
def bloated(archive_env: ArchiveEnv, monkeypatch: pytest.MonkeyPatch) -> ArchiveEnv:
    """An archive with one capture whose odds key index is planned for a rebuild on
    every check: its expected size is set to nearly nothing."""
    monkeypatch.setattr(reclaim, "MIN_EXCESS_BYTES", 0)
    monkeypatch.setitem(reclaim.INDEX_ROW_BYTES, "uq_odds_snapshots_key", (0.001, 0.001))
    report = capture_pass(
        archive_env.engine, archive_env.provider, archive_env.settings, force=True, reclaim=False
    )
    assert report.odds is not None and report.odds.status == "ok"
    return archive_env


@pytest.fixture
def wait_one_second(monkeypatch: pytest.MonkeyPatch) -> None:
    """A rebuild gives up waiting for older transactions after one second, not ten."""
    monkeypatch.setattr(reclaim, "LOCK_TIMEOUT_SECONDS", 1)


@pytest.fixture
def wait_twenty_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    """A rebuild keeps waiting long enough for the test to look at what it holds."""
    monkeypatch.setattr(reclaim, "LOCK_TIMEOUT_SECONDS", 20)


@postgres_only
def test_an_interrupted_rebuild_is_cleaned_up_by_the_next_pass_and_nothing_is_unusable(
    bloated: ArchiveEnv, wait_one_second: None
) -> None:
    env = bloated
    blocker = Blocker(env)
    try:
        # The rebuild waits for the older transaction, gives up at lock_timeout and
        # leaves an invalid index behind. That cannot be dropped yet either.
        summary = reclaim_pass(env.engine, env.provider, env.settings, due=True, force=True)
        assert summary is not None and summary.status == "failed"
        detail = summary.detail or {}
        assert detail["failed"]["uq_odds_snapshots_key"] == "LockNotAvailable"
        assert detail["rebuilt"] == {}
        (left,) = leftover_indexes(states(env))
        assert left.name.startswith("uq_odds_snapshots_key_cc") and not left.valid
        assert detail["failed"][left.name] == "LockNotAvailable"

        # Nothing is unusable meanwhile: the working index is valid, reads answer and the
        # next capture writes. That pass tries the cleanup first, cannot drop the
        # leftover yet, and so starts no rebuild: there is still exactly one leftover.
        assert {s.name for s in states(env) if s.valid} == set(INDEX_ROW_BYTES)
        with env.session_factory() as db:
            odds = archived_odds(db, env.provider, env.settings, PREGAME, "moneyline", at(10))
        assert odds.coverage.status == "captured" and odds.quotes
        report = env.capture(at(360))
        assert report.odds is not None and report.odds.status == "ok"
        assert report.odds.rows_written > 0
        assert report.reclaim is not None and report.reclaim.status == "failed"
        again = report.reclaim.detail or {}
        assert list(again["failed"]) == [left.name] and again["rebuilt"] == {}
        assert [s.name for s in leftover_indexes(states(env))] == [left.name]
    finally:
        blocker.release()

    # The older transaction has ended: the next pass drops the leftover, then rebuilds.
    report = capture_pass(env.engine, env.provider, env.settings, force_reclaim=True)
    assert report.reclaim is not None and report.reclaim.status == "ok", report
    detail = report.reclaim.detail or {}
    assert list(detail["dropped"]) == [left.name]
    assert "uq_odds_snapshots_key" in detail["rebuilt"] and detail["failed"] == {}
    assert leftover_indexes(states(env)) == []
    assert {s.name for s in states(env) if s.valid} == set(INDEX_ROW_BYTES)
    with env.session_factory() as db:
        odds = archived_odds(db, env.provider, env.settings, PREGAME, "moneyline", at(400))
    assert odds.coverage.status == "captured" and odds.quotes


def _rebuild_backend(connection: Connection) -> list[tuple[int, str, str, bool]]:
    """(backend pid, lock type, mode, granted) of every lock held or awaited by a REINDEX
    backend of this database (another database of the same server may be rebuilding)."""
    return [
        (row[0], row[1], row[2], row[3])
        for row in connection.execute(
            text(
                "SELECT a.pid, l.locktype, l.mode, l.granted FROM pg_locks l "
                "JOIN pg_stat_activity a ON a.pid = l.pid "
                "WHERE a.datname = current_database() "
                "AND a.query LIKE 'REINDEX INDEX CONCURRENTLY%' AND a.pid <> pg_backend_pid()"
            )
        )
    ]


def _wait_for_a_waiting_rebuild(probe: Connection) -> list[tuple[int, str, str, bool]]:
    """The locks of the rebuild once it waits for the older transaction (it then holds
    one lock it has not been granted)."""
    deadline = time.monotonic() + 15
    locks: list[tuple[int, str, str, bool]] = []
    while time.monotonic() < deadline:
        locks = _rebuild_backend(probe)
        probe.rollback()
        if any(not granted for _pid, _type, _mode, granted in locks):
            break
        time.sleep(0.05)
    assert any(not granted for _pid, _type, _mode, granted in locks), locks
    return locks


@postgres_only
def test_a_rebuild_that_has_to_wait_blocks_neither_reads_nor_writes(
    bloated: ArchiveEnv, wait_twenty_seconds: None
) -> None:
    """While a rebuild waits for an older transaction it holds SHARE UPDATE EXCLUSIVE on
    the table and the index and nothing stronger: a read and an insert go through, each
    with a ``lock_timeout`` of one second, which a lock they had to wait for would end."""
    env = bloated
    blocker = Blocker(env)
    done: list[Any] = []
    worker = threading.Thread(
        target=lambda: done.append(
            reclaim_pass(env.engine, env.provider, env.settings, due=True, force=True)
        )
    )
    worker.start()
    try:
        with env.engine.connect() as probe:
            locks = _wait_for_a_waiting_rebuild(probe)
            held = {mode for _pid, kind, mode, granted in locks if granted and kind == "relation"}
            assert held == {"ShareUpdateExclusiveLock"}
            probe.execute(text("SET lock_timeout = '1s'"))
            assert probe.execute(text("SELECT count(*) FROM odds_snapshots")).scalar()
            probe.execute(
                text(
                    "INSERT INTO odds_snapshots (run_id, captured_at, provider, provider_id, "
                    "fetched_at, event_id, market, sportsbook_id, status, outcomes) "
                    "VALUES (0, now(), 'scratch', 'x', now(), 'e', 'moneyline', 'b', 'open', '[]')"
                )
            )
            probe.commit()
            probe.execute(text("DELETE FROM odds_snapshots WHERE provider = 'scratch'"))
            probe.commit()
    finally:
        blocker.release()
        worker.join(timeout=30)
    assert not worker.is_alive()
    (summary,) = done
    assert summary is not None and summary.status == "ok", summary
    assert leftover_indexes(states(env)) == []


@postgres_only
def test_index_statements_never_run_inside_a_transaction(bloated: ArchiveEnv) -> None:
    env = bloated
    with env.engine.connect() as connection:
        # A connection that is not in autocommit mode is refused before anything is sent.
        with pytest.raises(NotAutocommit):
            rebuild_index(connection, "uq_odds_snapshots_key")
        with pytest.raises(NotAutocommit):
            drop_leftover(connection, "uq_odds_snapshots_key_ccnew")
        # PostgreSQL refuses it as well.
        with pytest.raises(DBAPIError, match="cannot run inside a transaction block"):
            connection.exec_driver_sql('REINDEX INDEX CONCURRENTLY "uq_odds_snapshots_key"')
        connection.rollback()
    with env.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        # An index of the schema is never dropped as a leftover.
        with pytest.raises(ValueError, match="not a leftover"):
            drop_leftover(connection, "uq_odds_snapshots_key")
        rebuild_index(connection, "uq_odds_snapshots_key")
    assert {s.name for s in states(env) if s.valid} == set(INDEX_ROW_BYTES)
    # The settings of the rebuild's connection do not reach the pool.
    reclaim_pass(env.engine, env.provider, env.settings, due=True, force=True)
    for _ in range(6):
        with env.engine.connect() as connection:
            assert connection.execute(text("SHOW statement_timeout")).scalar() == "0"
            assert connection.execute(text("SHOW lock_timeout")).scalar() == "0"


@postgres_only
def test_the_reclaim_never_overlaps_another_pass(bloated: ArchiveEnv) -> None:
    """It runs only inside a capture pass, under the archive's advisory lock: while
    another pass holds the lock, nothing is rebuilt."""
    env = bloated
    with env.engine.connect() as holder:
        assert holder.execute(
            text("SELECT pg_try_advisory_lock(:k)"), {"k": ADVISORY_LOCK_KEY}
        ).scalar()
        holder.commit()
        report = capture_pass(env.engine, env.provider, env.settings, force_reclaim=True)
        assert report.locked is True and report.reclaim is None
        holder.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": ADVISORY_LOCK_KEY})
        holder.commit()
    assert reclaim_runs(env) == []
    report = capture_pass(env.engine, env.provider, env.settings, force_reclaim=True)
    assert report.reclaim is not None and report.reclaim.status == "ok"


@postgres_only
def test_a_reclaim_is_recorded_for_administrators(bloated: ArchiveEnv) -> None:
    env = bloated
    before = {s.name: s.size for s in states(env)}["uq_odds_snapshots_key"]
    report = capture_pass(env.engine, env.provider, env.settings, force_reclaim=True)
    assert report.reclaim is not None
    (run,) = reclaim_runs(env)
    assert run.status == "ok" and run.finished_at is not None
    assert run.captured_at == env.provider.current
    after = {s.name: s.size for s in states(env)}["uq_odds_snapshots_key"]
    assert run.detail is not None
    rows = run.detail["rebuilt"]["uq_odds_snapshots_key"]
    with env.session_factory() as db:
        held = db.scalar(select(func.count()).select_from(ArchivedOdds))
        stats = archive_stats(db, env.settings)
    assert rows == [before, after, held] and after < before
    assert run.detail["freed_bytes"] == before - after
    (shown,) = [r for r in stats.last_runs if r.kind == "reclaim"]
    assert (shown.status, shown.indexes_rebuilt, shown.indexes_dropped, shown.indexes_failed) == (
        "ok",
        1,
        0,
        0,
    )
    assert shown.bytes_freed == before - after and shown.finished_at == run.finished_at
    assert shown.failed_indexes == {} and shown.error is None
    assert stats.disk_bytes is not None and stats.disk_bytes < stats.max_disk_bytes
    assert stats.max_disk_bytes == env.settings.snapshot_max_disk_bytes
    # Rebuilt a moment ago: the next check leaves it alone, whatever its size.
    report = capture_pass(env.engine, env.provider, env.settings, capture=False, force_prune=True)
    assert report.prune is not None and report.reclaim is None
    assert len(reclaim_runs(env)) == 1


@postgres_only
def test_a_rebuild_whose_database_session_is_ended_is_recorded_and_cleaned_up(
    bloated: ArchiveEnv, wait_twenty_seconds: None
) -> None:
    """Regression (review round 4, blocking). A database restart, a dropped connection or
    ``pg_terminate_backend`` ends the rebuild's session. The pass then tried to clean up
    on the dead connection and to detach it, both of which raise errors that are not the
    driver's: the script ended with a traceback and no ``reclaim`` run was written, so
    the administrators' statistics kept showing the previous one.

    Here the rebuild waits for an older transaction and its backend is terminated from a
    second connection. The pass ends normally with a ``failed`` reclaim run that names
    the index and the error's class; the invalid index it left is dropped by the next
    pass, once the older transaction has ended."""
    env = bloated
    blocker = Blocker(env)
    done: list[Any] = []

    def one_pass() -> None:
        try:
            done.append(
                capture_pass(
                    env.engine,
                    env.provider,
                    env.settings,
                    capture=False,
                    prune=False,
                    force_reclaim=True,
                )
            )
        except BaseException as exc:  # the defect: the pass raised instead of recording
            done.append(exc)

    worker = threading.Thread(target=one_pass)
    worker.start()
    try:
        with env.engine.connect() as probe:
            locks = _wait_for_a_waiting_rebuild(probe)
            (pid,) = {pid for pid, _type, _mode, _granted in locks}
            assert probe.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": pid}).scalar()
            probe.commit()
        worker.join(timeout=30)
        assert not worker.is_alive()
        (report,) = done
        assert isinstance(report, PassReport), repr(report)
        assert report.failed and report.reclaim is not None
        assert report.reclaim.status == "failed"
        detail = report.reclaim.detail or {}
        assert detail["failed"] == {"uq_odds_snapshots_key": "AdminShutdown"}
        assert detail["rebuilt"] == {} and detail["dropped"] == {}
        (run,) = reclaim_runs(env)
        assert run.status == "failed" and run.detail == detail and run.finished_at is not None
        with env.session_factory() as db:
            (shown,) = [r for r in archive_stats(db, env.settings).last_runs if r.kind == "reclaim"]
        assert (shown.status, shown.indexes_failed, shown.indexes_rebuilt) == ("failed", 1, 0)
        assert shown.failed_indexes == {"uq_odds_snapshots_key": "AdminShutdown"}
        # The terminated rebuild left its invalid copy; the working index is untouched.
        (left,) = leftover_indexes(states(env))
        assert left.name.startswith("uq_odds_snapshots_key_cc") and not left.valid
        assert {s.name for s in states(env) if s.valid} == set(INDEX_ROW_BYTES)
        # Nothing of the dead session reached the pool.
        with env.engine.connect() as connection:
            assert connection.execute(text("SHOW statement_timeout")).scalar() == "0"
    finally:
        blocker.release()
        worker.join(timeout=30)

    # The older transaction has ended: the next pass drops the leftover. The index whose
    # rebuild failed is left alone for a while (the back-off), unless the check is forced.
    report = capture_pass(env.engine, env.provider, env.settings, capture=False, force_prune=True)
    assert report.reclaim is not None and report.reclaim.status == "ok", report
    detail = report.reclaim.detail or {}
    assert list(detail["dropped"]) == [left.name] and detail["rebuilt"] == {}
    assert leftover_indexes(states(env)) == []
    report = capture_pass(env.engine, env.provider, env.settings, force_reclaim=True)
    assert report.reclaim is not None and report.reclaim.status == "ok", report
    assert "uq_odds_snapshots_key" in (report.reclaim.detail or {})["rebuilt"]
    assert {s.name for s in states(env) if s.valid} == set(INDEX_ROW_BYTES)
    assert leftover_indexes(states(env)) == []


@postgres_only
def test_a_pass_stops_rebuilding_at_its_first_failure(
    bloated: ArchiveEnv, wait_one_second: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two indexes are planned and an older transaction makes every rebuild wait. The
    first fails at ``lock_timeout``; the second is not tried in this pass (it would fail
    the same way, and leave a second invalid index), only named as skipped."""
    env = bloated
    monkeypatch.setitem(reclaim.INDEX_ROW_BYTES, "uq_prop_snapshots_key", (0.001, 0.001))
    with env.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ArchivedProp))
    blocker = Blocker(env)
    try:
        summary = reclaim_pass(env.engine, env.provider, env.settings, due=True, force=True)
    finally:
        blocker.release()
    assert summary is not None and summary.status == "failed"
    detail = summary.detail or {}
    planned = ["uq_odds_snapshots_key", "uq_prop_snapshots_key"]
    tried = [name for name in planned if name in detail["failed"]]
    assert len(tried) == 1 and detail["skipped"] == [n for n in planned if n not in tried]
    assert detail["rebuilt"] == {}
    # One rebuild was tried, so at most one invalid index is left (none, if it could be
    # dropped at once: the older transaction holds no lock on that index's table).
    assert len(leftover_indexes(states(env))) <= 1


@postgres_only
def test_indexes_are_checked_after_a_prune_and_not_on_every_capture(bloated: ArchiveEnv) -> None:
    """Counting the rows of every table and reading the catalog is the prune's
    follow-up, once an hour: a capture pass without a prune rebuilds nothing, however
    large an index is. The pass with the prune does."""
    env = bloated
    env.provider.current = at(360)
    report = capture_pass(env.engine, env.provider, env.settings, force=True, prune=False)
    assert report.odds is not None and report.odds.status == "ok"
    assert report.prune is None and report.reclaim is None
    assert reclaim_runs(env) == []
    env.provider.current = at(720)
    report = capture_pass(env.engine, env.provider, env.settings, force=True, force_prune=True)
    assert report.prune is not None and report.prune.status == "ok"
    assert report.reclaim is not None and report.reclaim.status == "ok"
    assert "uq_odds_snapshots_key" in (report.reclaim.detail or {})["rebuilt"]


class NoOddsProvider(ControlledProvider):
    """The feed is down: every odds call fails."""

    def get_odds(self, event_id: str, market: str) -> list[OddsSnapshot]:
        raise ConnectionError("feed dropped")


@postgres_only
def test_after_a_failed_pass_nothing_is_rebuilt_but_a_leftover_is_dropped(
    bloated: ArchiveEnv, wait_one_second: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pass whose capture or prune failed starts no rebuild (the feed or the database is
    in trouble, and a rebuild is heavy work), whatever is due: here the files are over
    the ceiling and the prune fails. What an interrupted rebuild left is still dropped:
    a feed that is down for hours must not keep an invalid index on the disk."""
    env = bloated
    blocker = Blocker(env)
    try:
        summary = reclaim_pass(env.engine, env.provider, env.settings, due=True, force=True)
        assert summary is not None and summary.status == "failed"
    finally:
        blocker.release()
    (left,) = leftover_indexes(states(env))

    # A failed capture: the leftover goes, nothing is rebuilt.
    good, env.provider = env.provider, NoOddsProvider()
    report = env.capture(at(360))
    assert report.odds is not None and report.odds.status == "failed" and report.prune is None
    assert report.reclaim is not None and report.reclaim.status == "ok"
    detail = report.reclaim.detail or {}
    assert list(detail["dropped"]) == [left.name] and detail["rebuilt"] == {}
    assert leftover_indexes(states(env)) == []
    assert len(reclaim_runs(env)) == 2

    # A failed prune with the files over the ceiling: no rebuild either, and with no
    # leftover there is nothing to record.
    env.provider = good
    env.settings = env.settings.model_copy(update={"snapshot_max_disk_bytes": 1})

    def failing(*args: Any, **kwargs: Any) -> Any:
        raise ConnectionError("connection lost")

    with monkeypatch.context() as patch:
        patch.setattr(prune_module, "prune_rows", failing)
        report = capture_pass(env.engine, env.provider, env.settings, force=True, force_prune=True)
    assert report.over_ceiling is True
    assert report.prune is not None and report.prune.status == "failed"
    assert report.reclaim is None and len(reclaim_runs(env)) == 2
    # The same pass without the failure rebuilds (over the ceiling, the back-off after
    # the failed rebuild above is an hour; the provider's clock has not moved that far,
    # so the check is forced here).
    report = capture_pass(env.engine, env.provider, env.settings, force_reclaim=True)
    assert report.reclaim is not None and report.reclaim.status == "ok"
    detail = report.reclaim.detail or {}
    assert detail["over_ceiling"] is True and "uq_odds_snapshots_key" in detail["rebuilt"]


@postgres_only
def test_a_pass_starts_no_rebuild_once_its_time_is_used_up(
    bloated: ArchiveEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``BUDGET_SECONDS``: with none left the planned index is named as skipped and left
    for a later pass; the run is recorded, and nothing failed."""
    env = bloated
    monkeypatch.setattr(reclaim, "BUDGET_SECONDS", -1)
    before = {s.name: s.size for s in states(env)}
    summary = reclaim_pass(env.engine, env.provider, env.settings, due=True)
    assert summary is not None and summary.status == "ok"
    detail = summary.detail or {}
    assert detail["skipped"] == ["uq_odds_snapshots_key"]
    assert detail["rebuilt"] == {} and detail["failed"] == {} and detail["freed_bytes"] == 0
    assert {s.name: s.size for s in states(env)} == before
    monkeypatch.setattr(reclaim, "BUDGET_SECONDS", 60)
    summary = reclaim_pass(env.engine, env.provider, env.settings, due=True)
    assert summary is not None and list((summary.detail or {})["rebuilt"]) == [
        "uq_odds_snapshots_key"
    ]


@postgres_only
def test_a_rebuild_that_takes_too_long_is_ended_by_the_configured_timeout(
    bloated: ArchiveEnv, wait_twenty_seconds: None
) -> None:
    """``ODDVEX_SNAPSHOT_RECLAIM_TIMEOUT_SECONDS`` is the rebuild's ``statement_timeout``.
    Here the rebuild waits for an older transaction (it may wait 20 s for that) and the
    timeout is one second: it is cancelled, recorded as failed with the error's class,
    and its leftover is dropped by the next pass."""
    env = bloated
    assert env.settings.snapshot_reclaim_timeout_seconds == 120
    env.settings = env.settings.model_copy(update={"snapshot_reclaim_timeout_seconds": 1})
    blocker = Blocker(env)
    started = time.monotonic()
    try:
        summary = reclaim_pass(env.engine, env.provider, env.settings, due=True, force=True)
    finally:
        blocker.release()
    assert time.monotonic() - started < 15  # far less than the 20 s it may wait for a lock
    assert summary is not None and summary.status == "failed"
    detail = summary.detail or {}
    assert detail["failed"]["uq_odds_snapshots_key"] == "QueryCanceled"
    report = capture_pass(env.engine, env.provider, env.settings, force_reclaim=True)
    assert report.reclaim is not None and report.reclaim.status == "ok", report
    assert leftover_indexes(states(env)) == []


@postgres_only
def test_a_forced_check_uses_the_lower_bar_while_the_files_are_over_the_ceiling(
    archive_env: ArchiveEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--reclaim`` captures nothing, so its pass has not compared the files with the
    ceiling before the check; it does so itself. An index that is under 1.3 times its
    normal size but over 1.1 times its dense size is rebuilt only over the ceiling."""
    env = archive_env
    report = capture_pass(env.engine, env.provider, env.settings, force=True, reclaim=False)
    assert report.odds is not None and report.odds.status == "ok"
    monkeypatch.setattr(reclaim, "MIN_EXCESS_BYTES", 0)
    # As normally written this index "needs" a megabyte a row; freshly rebuilt, nearly
    # nothing: only the over-the-ceiling bar asks for a rebuild.
    monkeypatch.setitem(reclaim.INDEX_ROW_BYTES, "uq_odds_snapshots_key", (1_000_000.0, 0.001))
    report = capture_pass(
        env.engine, env.provider, env.settings, capture=False, prune=False, force_reclaim=True
    )
    assert report.reclaim is None
    env.settings = env.settings.model_copy(update={"snapshot_max_disk_bytes": 1})
    report = capture_pass(
        env.engine, env.provider, env.settings, capture=False, prune=False, force_reclaim=True
    )
    assert report.reclaim is not None and report.reclaim.status == "ok"
    detail = report.reclaim.detail or {}
    assert detail["over_ceiling"] is True and "uq_odds_snapshots_key" in detail["rebuilt"]


# ------------------------------------------------------------------ the plan
def test_every_archive_index_has_a_measured_size() -> None:
    """A new index on an archive table needs its figures in ``INDEX_ROW_BYTES``, or the
    reclaim would never look at it."""
    names: set[str] = set()
    for model in ARCHIVE_MODELS:
        table = model.__table__
        names.add(str(table.primary_key.name))
        names |= {str(index.name) for index in table.indexes}
        names |= {
            str(constraint.name)
            for constraint in table.constraints
            if constraint.__visit_name__ == "unique_constraint"
        }
    assert names == set(INDEX_ROW_BYTES)
    for normal, dense in INDEX_ROW_BYTES.values():
        assert normal >= dense > 0


def test_which_indexes_the_plan_rebuilds(archive_env: ArchiveEnv) -> None:
    """The plan is arithmetic on the catalog's sizes, so it is checked on every database
    with sizes written by hand: 10,000 odds rows, one megabyte of allowance."""
    env = archive_env
    name = "uq_odds_snapshots_key"
    rows = 10_000
    normal, dense = expected_bytes(name, rows)
    assert (normal, dense) == (16_384 + 1_251_000, 16_384 + 792_000)
    now = T0 + timedelta(days=30)
    with env.session_factory() as db:
        db.execute(
            ArchivedOdds.__table__.insert(),
            [
                {
                    "run_id": 0,
                    "captured_at": T0 + timedelta(microseconds=i),
                    "provider": "synthetic",
                    "provider_id": "x",
                    "fetched_at": T0,
                    "event_id": "e",
                    "market": "moneyline",
                    "sportsbook_id": "b",
                    "status": "open",
                    "outcomes": [],
                }
                for i in range(rows)
            ],
        )
        db.commit()

        def planned(size: int, **options: Any) -> list[str]:
            found = plan_rebuilds(
                db,
                env.provider.name,
                [IndexState(name, "odds_snapshots", size, True)],
                now,
                **options,
            )
            return [rebuild.name for rebuild in found]

        # Past 1.3 times the normal size and by more than a megabyte: rebuilt.
        limit = normal + reclaim.MIN_EXCESS_BYTES  # larger than 1.3 times at this size
        assert limit > reclaim.RECLAIM_FACTOR * normal
        assert planned(limit) == [] and planned(limit + 1) == [name]
        # Over the ceiling the bar is the freshly rebuilt size, so more is released.
        full = dense + reclaim.MIN_EXCESS_BYTES
        assert planned(full, over_ceiling=True) == []
        assert planned(full + 1, over_ceiling=True) == [name]
        assert planned(full + 1) == []
        # An invalid index of the schema is rebuilt whatever its size.
        assert [
            r.name
            for r in plan_rebuilds(
                db, env.provider.name, [IndexState(name, "odds_snapshots", 8192, False)], now
            )
        ] == [name]
        # An index that is not part of the schema is never planned.
        assert (
            plan_rebuilds(
                db,
                env.provider.name,
                [IndexState(name + "_ccnew", "odds_snapshots", 10**9, False)],
                now,
            )
            == []
        )

        # Rebuilt 23 hours ago: left alone, unless the files are over the ceiling or the
        # check is forced. The rebuild then produced 150 bytes a row (a feed with longer
        # identifiers than the synthetic one): the expected size follows it.
        run = new_run(env.provider, env.settings, "reclaim", now - timedelta(hours=23))
        fat = 16_384 + 150 * rows
        run.detail = {"rebuilt": {name: [5_000_000, fat, rows]}}
        db.add(run)
        db.commit()
        huge = 50_000_000
        assert planned(huge) == []
        assert planned(huge, over_ceiling=True) == [name] and planned(huge, force=True) == [name]
        later = now + timedelta(hours=2)
        fat_normal = 16_384 + int(rows * 150 * 125.1 / 79.2)
        for size, expected in ((fat_normal + reclaim.MIN_EXCESS_BYTES, []), (huge, [name])):
            found = plan_rebuilds(
                db, env.provider.name, [IndexState(name, "odds_snapshots", size, True)], later
            )
            assert [r.name for r in found] == expected
            # Without that rebuild's figure the smaller size would already be over.
        assert fat_normal + reclaim.MIN_EXCESS_BYTES > limit


def test_an_index_whose_rebuild_failed_is_left_alone_for_a_while(archive_env: ArchiveEnv) -> None:
    """A rebuild that cannot finish on this server (too slow for the timeout, or always
    in the way of a long transaction) would otherwise write and discard a full copy of
    the index after every prune. After a failure the index is not planned for
    ``FAILURE_BACKOFF`` (6 hours), or ``FAILURE_BACKOFF_FULL`` (1 hour) while the files
    are over the ceiling; a forced check (``--reclaim``) ignores it; a rebuild that
    succeeded since ends it. Checked on every database, with sizes written by hand."""
    env = archive_env
    name = "uq_odds_snapshots_key"
    huge = 50_000_000
    now = T0 + timedelta(days=30)
    backoffs = (reclaim.FAILURE_BACKOFF, reclaim.FAILURE_BACKOFF_FULL)
    assert backoffs == (timedelta(hours=6), timedelta(hours=1))
    with env.session_factory() as db:

        def planned(at_time: datetime, **options: Any) -> list[str]:
            found = plan_rebuilds(
                db,
                env.provider.name,
                [IndexState(name, "odds_snapshots", huge, True)],
                at_time,
                **options,
            )
            return [rebuild.name for rebuild in found]

        assert planned(now) == [name]
        run = new_run(env.provider, env.settings, "reclaim", now, status="failed")
        # The leftover's own failed drop is not the index's failure.
        run.detail = {"failed": {name: "QueryCanceled", name + "_ccnew": "LockNotAvailable"}}
        db.add(run)
        db.commit()
        us = timedelta(microseconds=1)
        assert planned(now + timedelta(hours=6) - us) == []
        assert planned(now + timedelta(hours=6)) == [name]
        assert planned(now + timedelta(hours=1) - us, over_ceiling=True) == []
        assert planned(now + timedelta(hours=1), over_ceiling=True) == [name]
        assert planned(now + timedelta(minutes=1), force=True) == [name]
        # An invalid index of the schema waits out the back-off too.
        invalid = [IndexState(name, "odds_snapshots", 8192, False)]
        assert plan_rebuilds(db, env.provider.name, invalid, now + timedelta(hours=1)) == []
        assert [
            r.name for r in plan_rebuilds(db, env.provider.name, invalid, now + timedelta(hours=6))
        ] == [name]
        # A failure of another index changes nothing for this one.
        other = new_run(env.provider, env.settings, "reclaim", now + timedelta(hours=7))
        other.status = "failed"
        other.detail = {"failed": {"uq_prop_snapshots_key": "QueryCanceled"}}
        db.add(other)
        db.commit()
        assert planned(now + timedelta(hours=7, minutes=1)) == [name]
        # A rebuild that succeeded after the failure ends the back-off (and starts the
        # once-a-day rule instead, which over the ceiling does not apply).
        fixed = new_run(env.provider, env.settings, "reclaim", now + timedelta(minutes=30))
        fixed.detail = {"rebuilt": {name: [huge, 1_000_000, 100]}}
        db.add(fixed)
        db.commit()
        assert planned(now + timedelta(minutes=40), over_ceiling=True) == [name]
        assert planned(now + timedelta(minutes=40)) == []
        assert planned(now + timedelta(hours=25)) == [name]


# -------------------------------------------------------------------- SQLite
@sqlite_only
def test_on_sqlite_the_reclaim_and_the_file_ceiling_do_nothing(archive_env: ArchiveEnv) -> None:
    env = archive_env
    # A ceiling of one byte stops nothing: there is no file size to compare with.
    env.settings = env.settings.model_copy(update={"snapshot_max_disk_bytes": 1})
    report = env.capture(T0)
    assert report.full is False and report.over_ceiling is False
    assert report.odds is not None and report.odds.status == "ok"
    assert report.prune is not None and report.prune.status == "ok"
    assert report.reclaim is None
    with env.session_factory() as db:
        assert archive_disk_bytes(db) is None
        before = {
            m.__tablename__: db.scalar(select(func.count()).select_from(m)) for m in ARCHIVE_MODELS
        }
    # Asked directly, forced and "over the ceiling": still nothing, and no statement sent.
    assert (
        reclaim_pass(
            env.engine, env.provider, env.settings, due=True, over_ceiling=True, force=True
        )
        is None
    )
    report = capture_pass(env.engine, env.provider, env.settings, capture=False, force_reclaim=True)
    assert report.reclaim is None
    assert reclaim_runs(env) == []
    with env.session_factory() as db:
        after = {
            m.__tablename__: db.scalar(select(func.count()).select_from(m)) for m in ARCHIVE_MODELS
        }
        stats = archive_stats(db, env.settings)
    assert after == before
    assert stats.disk_bytes is None and stats.max_disk_bytes == 1
    assert [r.kind for r in stats.last_runs if r.kind == "reclaim"] == []
