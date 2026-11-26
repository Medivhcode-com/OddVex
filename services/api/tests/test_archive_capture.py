"""Capture passes: the flag, intervals, dedupe, tombstones, scope, the cap, failures, the
append-only guard, data-mode isolation, the lock and the script."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, insert, select, text
from sqlalchemy.exc import IntegrityError

from oddvex_api.archive.capture import (
    ADVISORY_LOCK_KEY,
    StatusRecord,
    capture_pass,
    capture_status,
)
from oddvex_api.archive.guard import ArchiveIsAppendOnly
from oddvex_api.archive.service import archived_odds
from oddvex_api.db import (
    ARCHIVE_MODELS,
    ArchivedEvent,
    ArchivedOdds,
    ArchivedProp,
    ArchivedStatus,
    SnapshotRun,
)
from oddvex_api.providers import OddsSnapshot

from .archive_support import PREGAME, T0, ArchiveEnv, archive_env, enable_archive
from .conftest import EXTERNAL_DATABASE_URL
from .fakes import ControlledProvider, moneyline

__all__ = ["archive_env"]

API_ROOT = Path(__file__).resolve().parents[1]


def count(env: ArchiveEnv, model: Any, *where: Any) -> int:
    with env.session_factory() as db:
        return int(db.scalar(select(func.count()).select_from(model).where(*where)) or 0)


def total_rows(env: ArchiveEnv) -> int:
    return sum(count(env, model) for model in ARCHIVE_MODELS)


def test_nothing_is_written_while_the_flag_is_off(archive_env: ArchiveEnv) -> None:
    env = archive_env
    enable_archive(env.session_factory, False)
    report = env.capture(T0)
    assert report.enabled is False and (report.odds, report.props, report.prune) == (
        None,
        None,
        None,
    )
    with env.session_factory() as db:
        record = StatusRecord(
            provider="synthetic",
            provider_id="x",
            fetched_at=T0,
            event_id=PREGAME,
            kind="lineup",
            status="expected",
            source="Fictional Lineup Desk",
        )
        assert capture_status(db, env.provider, env.settings, [record]) is None
    assert total_rows(env) == 0


def test_capture_waits_for_its_interval_less_the_slack(archive_env: ArchiveEnv) -> None:
    env = archive_env
    first = env.capture(T0, force=False)
    assert first.odds is not None and first.props is not None and first.prune is not None
    assert first.odds.events_in_scope == 32 and first.odds.rows_written > 32
    # 240 s later (two worker turns): nothing is due, no run row is written.
    runs = count(env, SnapshotRun)
    early = env.capture(T0 + timedelta(seconds=240), force=False)
    assert (early.odds, early.props, early.prune) == (None, None, None)
    assert count(env, SnapshotRun) == runs
    # 350 s later: within the 15 s slack of the 360 s interval, so odds and props (360 s
    # in these tests) are captured.
    late = env.capture(T0 + timedelta(seconds=350), force=False)
    assert late.odds is not None and late.odds.status == "ok"
    assert late.props is not None and late.props.status == "ok"
    assert late.prune is None  # hourly


def test_an_unchanged_quote_is_not_written_again_and_a_vanished_one_is_tombstoned(
    archive_env: ArchiveEnv,
) -> None:
    env = archive_env
    p = env.provider
    p.set_odds(
        PREGAME,
        "moneyline",
        [
            ("northline", "open", 30, moneyline(-120, 100)),
            ("summit", "open", 30, moneyline(-125, 105)),
        ],
    )
    env.capture(T0)
    where = (ArchivedOdds.event_id == PREGAME, ArchivedOdds.market == "moneyline")
    assert count(env, ArchivedOdds, *where) == 2
    # Same prices and the same last_updated (30 s + 360 s old now): nothing new. The
    # summit quote is gone: one tombstone row.
    p.set_odds(PREGAME, "moneyline", [("northline", "open", 390, moneyline(-120, 100))])
    second = env.capture(T0 + timedelta(seconds=360))
    assert second.odds is not None and second.odds.rows_unchanged > 0
    with env.session_factory() as db:
        rows = db.execute(
            select(
                ArchivedOdds.sportsbook_id,
                ArchivedOdds.status,
                ArchivedOdds.outcomes,
                ArchivedOdds.captured_at,
            )
            .where(*where)
            .order_by(ArchivedOdds.captured_at, ArchivedOdds.sportsbook_id)
        ).all()
    assert [(r.sportsbook_id, r.status, r.captured_at) for r in rows] == [
        ("northline", "open", T0),
        ("summit", "open", T0),
        ("summit", "unavailable", T0 + timedelta(seconds=360)),
    ]
    assert rows[-1].outcomes == []
    # A tombstone is written once; northline is still unchanged (750 s old).
    p.set_odds(PREGAME, "moneyline", [("northline", "open", 750, moneyline(-120, 100))])
    env.capture(T0 + timedelta(seconds=720))
    assert count(env, ArchivedOdds, *where, ArchivedOdds.sportsbook_id == "northline") == 1
    assert count(env, ArchivedOdds, *where, ArchivedOdds.sportsbook_id == "summit") == 2
    # A changed price is written.
    p.set_odds(PREGAME, "moneyline", [("northline", "open", 30, moneyline(-118, 100))])
    env.capture(T0 + timedelta(seconds=1080))
    assert count(env, ArchivedOdds, *where, ArchivedOdds.sportsbook_id == "northline") == 2


def test_the_natural_key_admits_one_row_per_key_and_capture_time(archive_env: ArchiveEnv) -> None:
    env = archive_env
    env.capture(T0)
    with env.session_factory() as db:
        row = db.scalars(select(ArchivedOdds).limit(1)).one()
        values = {
            c: getattr(row, c)
            for c in (
                "run_id",
                "captured_at",
                "provider",
                "provider_id",
                "fetched_at",
                "event_id",
                "market",
                "sportsbook_id",
                "status",
                "last_updated",
                "outcomes",
            )
        }
    with env.session_factory() as db, pytest.raises(IntegrityError):
        db.execute(insert(ArchivedOdds), [values])
        db.commit()


def test_final_events_are_not_captured(archive_env: ArchiveEnv) -> None:
    env = archive_env
    env.provider.finish(PREGAME, 3, 2)
    report = env.capture(T0)
    assert report.odds is not None and report.odds.events_in_scope == 31
    assert count(env, ArchivedEvent, ArchivedEvent.event_id == PREGAME) == 0
    assert count(env, ArchivedOdds, ArchivedOdds.event_id == PREGAME) == 0
    with env.session_factory() as db:
        statuses = set(db.scalars(select(ArchivedEvent.status).distinct()))
    assert statuses <= {"upcoming", "live"}


def test_capture_stops_at_the_storage_cap_and_the_prune_goes_on(archive_env: ArchiveEnv) -> None:
    env = archive_env
    env.capture(T0)
    rows = count(env, ArchivedOdds)
    env.settings = env.settings.model_copy(update={"snapshot_max_bytes": 1})
    env.provider.current = T0 + timedelta(hours=2)
    report = capture_pass(env.engine, env.provider, env.settings, force=True)
    assert report.full is True
    assert (
        report.odds is not None
        and report.odds.status == "skipped_full"
        and report.odds.rows_written == 0
    )
    assert report.props is not None and report.props.status == "skipped_full"
    assert report.prune is not None and report.prune.status == "ok"
    assert count(env, ArchivedOdds) == rows


class BrokenProvider(ControlledProvider):
    """Raises part-way through an odds pass, after other events were read."""

    def get_odds(self, event_id: str, market: str) -> list[OddsSnapshot]:
        if event_id == PREGAME and market == "total":
            raise ConnectionError("feed dropped (text that must not be stored)")
        return super().get_odds(event_id, market)


def test_a_failed_pass_is_recorded_and_leaves_no_partial_rows(archive_env: ArchiveEnv) -> None:
    env = archive_env
    env.provider = BrokenProvider()
    report = env.capture(T0)
    assert report.failed and report.odds is not None and report.odds.status == "failed"
    assert report.props is None and report.prune is None  # the pass stops at the failure
    assert count(env, ArchivedOdds) == count(env, ArchivedEvent) == 0
    with env.session_factory() as db:
        (run,) = db.scalars(select(SnapshotRun)).all()
    assert (run.kind, run.status, run.detail) == ("odds", "failed", {"error": "ConnectionError"})
    # The next turn tries again: a failed run does not count as a capture.
    env.provider = ControlledProvider(T0 + timedelta(seconds=120))
    again = capture_pass(env.engine, env.provider, env.settings)
    assert again.odds is not None and again.odds.status == "ok"


def test_archive_rows_cannot_be_updated_or_deleted_through_the_orm(archive_env: ArchiveEnv) -> None:
    env = archive_env
    env.capture(T0)
    for model in (ArchivedOdds, ArchivedEvent, ArchivedProp, SnapshotRun):
        with env.session_factory() as db:
            row = db.scalars(select(model).limit(1)).one()
            if model is SnapshotRun:
                row.rows_written = 0
            else:
                row.provider_id = "changed"
            with pytest.raises(ArchiveIsAppendOnly):
                db.commit()
        with env.session_factory() as db:
            db.delete(db.scalars(select(model).limit(1)).one())
            with pytest.raises(ArchiveIsAppendOnly):
                db.commit()
    with env.session_factory() as db:
        capture_status(
            db,
            env.provider,
            env.settings,
            [
                StatusRecord(
                    provider="synthetic",
                    provider_id="x",
                    fetched_at=T0,
                    event_id=PREGAME,
                    kind="news",
                    status="reported",
                    source="Fictional Wire",
                )
            ],
        )
        status = db.scalars(select(ArchivedStatus)).one()
        status.status = "unknown"
        with pytest.raises(ArchiveIsAppendOnly):
            db.commit()


class ReplayNamedProvider(ControlledProvider):
    name = "replay"
    data_mode = "replay"


def test_rows_of_another_provider_are_invisible(archive_env: ArchiveEnv) -> None:
    env = archive_env
    env.provider = ReplayNamedProvider()
    report = env.capture(T0)
    assert report.odds is not None and report.odds.status == "ok"
    synthetic = ControlledProvider(T0 + timedelta(seconds=60))
    with env.session_factory() as db:
        seen = archived_odds(
            db, synthetic, env.settings, PREGAME, "moneyline", T0 + timedelta(seconds=60)
        )
        assert seen.coverage.status == "not_captured" and seen.quotes == []
        mine = archived_odds(
            db, env.provider, env.settings, PREGAME, "moneyline", T0 + timedelta(seconds=60)
        )
        assert mine.coverage.status == "captured" and mine.quotes and mine.data_mode == "replay"
    # And the synthetic provider's own captures start from nothing: no dedupe against
    # the other provider's rows.
    synthetic_report = capture_pass(env.engine, synthetic, env.settings, force=True)
    assert synthetic_report.odds is not None
    assert synthetic_report.odds.rows_unchanged == 0


@pytest.mark.skipif(not EXTERNAL_DATABASE_URL, reason="the advisory lock exists on PostgreSQL only")
def test_two_passes_never_overlap_on_postgresql(archive_env: ArchiveEnv) -> None:
    env = archive_env
    with env.engine.connect() as holder:
        assert holder.execute(
            text("SELECT pg_try_advisory_lock(:k)"), {"k": ADVISORY_LOCK_KEY}
        ).scalar()
        report = env.capture(T0)
        assert report.locked is True and report.odds is None
        holder.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": ADVISORY_LOCK_KEY})
        holder.commit()
    assert total_rows(env) == 0
    assert env.capture(T0).odds is not None


def _script(env: ArchiveEnv, *args: str) -> subprocess.CompletedProcess[str]:
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "DATABASE_URL": env.settings.database_url,
        "ODDVEX_ENV": "test",
        "ODDVEX_LOG_LEVEL": "WARNING",
    }
    return subprocess.run(
        [sys.executable, str(API_ROOT / "scripts" / "capture_snapshots.py"), *args],
        cwd=API_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )


def test_the_capture_script(archive_env: ArchiveEnv) -> None:
    env = archive_env
    enable_archive(env.session_factory, False)
    off = _script(env)
    assert off.returncode == 0, off.stderr
    assert "Snapshot archive is off; nothing captured." in off.stdout
    assert total_rows(env) == 0

    enable_archive(env.session_factory)
    dry = _script(env, "--dry-run")
    assert dry.returncode == 0 and "Dry run, nothing saved" in dry.stdout, dry.stderr
    assert total_rows(env) == 0

    captured = _script(env)
    assert captured.returncode == 0, captured.stderr
    assert "odds ok" in captured.stdout and "props ok" in captured.stdout
    again = _script(env)
    assert again.returncode == 0 and "odds not due" in again.stdout, again.stdout

    stats = _script(env, "--stats")
    assert stats.returncode == 0 and "Snapshot archive on" in stats.stdout, stats.stderr
    pruned = _script(env, "--prune-only", "--force")
    assert pruned.returncode == 0 and "prune ok" in pruned.stdout, pruned.stdout


class NoScheduleProvider(ControlledProvider):
    """The schedule itself cannot be read."""

    def list_events(
        self, league: str | None = None, status: str | None = None, on_date: Any = None
    ) -> Any:
        raise TimeoutError("schedule unavailable")


def test_a_schedule_error_is_recorded_as_a_failed_run(archive_env: ArchiveEnv) -> None:
    env = archive_env
    env.provider = NoScheduleProvider()
    report = env.capture(T0)
    assert report.odds is not None and report.odds.status == "failed"
    with env.session_factory() as db:
        (run,) = db.scalars(select(SnapshotRun)).all()
    assert run.detail == {"error": "TimeoutError"}
    assert total_rows(env) == 1
