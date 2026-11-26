"""The long measurements behind docs/features/p0-1.md, "Bounds": how large the snapshot
archive's files get on PostgreSQL next to the size the storage cap counts.

Not a test (pytest does not collect it) and not product code. The fast version that CI
runs is ``tests/test_archive_reclaim.py``. It needs a throwaway PostgreSQL database, whose
archive tables it drops and creates:

    cd services/api
    ODDVEX_MEASURE_DATABASE_URL=postgresql+psycopg://oddvex:oddvex@localhost:5432/oddvex_measure \\
        .venv/bin/python tests/measure_archive_files.py cycles 9
    ODDVEX_MEASURE_DATABASE_URL=... .venv/bin/python tests/measure_archive_files.py rolling 8

``cycles N`` repeats the measurement of review round 3 (the one that showed the indexes
growing with every prune): N times, 480 capture passes 360 s apart on the whole synthetic
schedule (two synthetic days, odds every pass and props hourly), a plain VACUUM and the
sizes at that peak; then, seven days on, one pass that prunes and reclaims index space
exactly as ``scripts/capture_snapshots.py`` does, a plain VACUUM, and the sizes again.
About two minutes a cycle.

``rolling D`` runs the worker's pass every 360 s for D synthetic days with retention
shortened to 1 day and the keep period to 3 days, so that rows arrive and leave at the
same rate within the run, and prints the sizes every six synthetic hours and every
reclaim run. About a minute a day.

Everything else is the production default: no test overrides. The provider is the
synthetic one; nothing is fetched from anywhere.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from oddvex_api.archive.capture import archive_bytes, archive_disk_bytes, capture_pass
from oddvex_api.archive.guard import install_archive_guard
from oddvex_api.archive.reclaim import STATED_FILES_FACTOR, index_states
from oddvex_api.config import Settings
from oddvex_api.db import (
    ARCHIVE_MODELS,
    ArchivedEvent,
    Base,
    SnapshotRun,
    make_engine,
    make_session_factory,
)
from oddvex_api.flags import service as flags
from oddvex_api.providers import SyntheticProvider

START = datetime(2026, 3, 14, 0, 0, tzinfo=UTC)
MB = 1e6


def database_url() -> str:
    url = os.environ.get("ODDVEX_MEASURE_DATABASE_URL", "")
    name = make_url(url).database if url else ""
    if not url.startswith("postgresql") or not name or "measure" not in name:
        raise SystemExit(
            "Set ODDVEX_MEASURE_DATABASE_URL to a throwaway PostgreSQL database whose name "
            "contains 'measure': its archive tables are dropped."
        )
    return url


def set_up(settings: Settings) -> tuple[Engine, sessionmaker[Session]]:
    engine = make_engine(settings.database_url)
    with engine.begin() as connection:
        Base.metadata.drop_all(connection)
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    Base.metadata.create_all(engine)
    install_archive_guard()
    sessions = make_session_factory(engine)
    with sessions() as db:
        flags.set_flag(db, "snapshot_archive", True)
        db.commit()
    with engine.connect() as connection:
        version = connection.execute(text("SHOW server_version")).scalar()
    print(f"PostgreSQL {version}; stated factor {STATED_FILES_FACTOR}", flush=True)
    return engine, sessions


def vacuum(engine: Engine) -> None:
    """A plain VACUUM of every archive table: what autovacuum does."""
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        for model in ARCHIVE_MODELS:
            connection.execute(text(f"VACUUM {model.__tablename__}"))


def sizes(sessions: sessionmaker[Session]) -> tuple[int, int, int, int, int]:
    """(counted, files, of which tables, of which indexes, games held)."""
    tables = ", ".join(f"'{model.__tablename__}'" for model in ARCHIVE_MODELS)
    with sessions() as db:
        counted = archive_bytes(db)
        disk = archive_disk_bytes(db) or 0
        heap, indexes = db.execute(
            text(
                "SELECT sum(pg_table_size(n::regclass)), sum(pg_indexes_size(n::regclass)) "
                f"FROM unnest(ARRAY[{tables}]) AS n"
            )
        ).one()
        games = db.scalar(select(func.count(func.distinct(ArchivedEvent.event_id)))) or 0
    return counted, disk, int(heap), int(indexes), games


def cycles(count: int) -> None:
    settings = Settings(_env_file=None, env="test", database_url=database_url())
    engine, sessions = set_up(settings)
    now = [START]
    provider = SyntheticProvider(seed=20260101, clock=lambda: now[0])
    largest = 0
    worst = 0.0
    slowest = 0.0
    for number in range(count):
        started = time.perf_counter()
        for _ in range(480):
            before = time.perf_counter()
            capture_pass(engine, provider, settings, prune=False)
            slowest = max(slowest, time.perf_counter() - before)
            now[0] += timedelta(seconds=360)
        vacuum(engine)
        counted, disk, heap, indexes, _games = sizes(sessions)
        largest = max(largest, counted)
        worst = max(worst, disk / largest)
        print(
            f"cycle {number} peak ({time.perf_counter() - started:.0f} s): counted "
            f"{counted / MB:.1f} MB, files {disk / MB:.1f} MB (tables {heap / MB:.1f}, indexes "
            f"{indexes / MB:.1f}); files / largest counted so far = {disk / largest:.3f}",
            flush=True,
        )
        now[0] += timedelta(days=7)
        started = time.perf_counter()
        report = capture_pass(engine, provider, settings, capture=False, force_prune=True)
        took = time.perf_counter() - started
        vacuum(engine)
        counted, disk, heap, indexes, games = sizes(sessions)
        assert report.prune is not None
        detail = (report.reclaim.detail if report.reclaim is not None else None) or {}
        print(
            f"cycle {number} after the prune and reclaim pass ({took:.1f} s; "
            f"{report.prune.rows_deleted} rows deleted; reclaim "
            f"{report.reclaim.status if report.reclaim is not None else 'none'}, "
            f"{len(detail.get('rebuilt', {}))} indexes rebuilt, "
            f"{detail.get('freed_bytes', 0) / MB:.1f} MB freed, failed "
            f"{detail.get('failed', {})}): counted {counted / MB:.1f} MB ({games} games held), "
            f"files {disk / MB:.1f} MB (tables {heap / MB:.1f}, indexes {indexes / MB:.1f})",
            flush=True,
        )
    print(
        f"largest files / largest counted so far over {count} cycles: {worst:.3f} "
        f"(stated: {STATED_FILES_FACTOR}); slowest capture pass {slowest:.2f} s"
    )
    with engine.connect() as connection:
        for state in index_states(connection):
            print(f"  {state.name}: {state.size / MB:.2f} MB, valid {state.valid}")
    with sessions() as db:
        for model in ARCHIVE_MODELS:
            rows = db.scalar(select(func.count()).select_from(model))
            print(f"  rows in {model.__tablename__}: {rows}")


def rolling(days: int) -> None:
    settings = Settings(
        _env_file=None,
        env="test",
        database_url=database_url(),
        snapshot_retention_days=1,
        snapshot_keep_days=3,
    )
    engine, sessions = set_up(settings)
    now = [START]
    provider = SyntheticProvider(seed=20260101, clock=lambda: now[0])
    worst = (0.0, 0.0)
    slowest = 0.0
    for turn in range(days * 240):
        started = time.perf_counter()
        report = capture_pass(engine, provider, settings)
        took = time.perf_counter() - started
        slowest = max(slowest, took)
        day = (now[0] - START).total_seconds() / 86400
        if report.prune is not None:
            vacuum(engine)
        if report.reclaim is not None:
            detail = report.reclaim.detail or {}
            print(
                f"  day {day:.2f}: reclaim {report.reclaim.status}, rebuilt "
                f"{sorted(detail['rebuilt'])}, {detail['freed_bytes'] / MB:.1f} MB freed, failed "
                f"{detail['failed']}; the pass took {took:.1f} s",
                flush=True,
            )
        if turn % 60 == 59:
            counted, disk, _heap, _indexes, _games = sizes(sessions)
            if day >= 2 and disk / counted > worst[0]:
                worst = (disk / counted, day)
            print(
                f"day {day:.2f}: counted {counted / MB:.1f} MB, files {disk / MB:.1f} MB, "
                f"files / counted = {disk / counted:.3f}",
                flush=True,
            )
        now[0] += timedelta(seconds=360)
    with sessions() as db:
        runs = db.execute(
            select(SnapshotRun.kind, SnapshotRun.status, func.count()).group_by(
                SnapshotRun.kind, SnapshotRun.status
            )
        ).all()
    print("runs still held:", sorted(tuple(run) for run in runs))
    print(
        f"largest files / counted after day 2: {worst[0]:.3f} at day {worst[1]:.2f} "
        f"(stated: {STATED_FILES_FACTOR}); slowest pass {slowest:.2f} s"
    )


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode not in ("cycles", "rolling"):
        raise SystemExit(__doc__)
    amount = int(sys.argv[2]) if len(sys.argv) > 2 else (9 if mode == "cycles" else 8)
    if mode == "cycles":
        cycles(amount)
    else:
        rolling(amount)
