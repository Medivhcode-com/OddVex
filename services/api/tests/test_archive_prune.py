"""The retention prune: what survives the full-resolution window, and what goes at the
keep horizon."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from oddvex_api.archive.capture import capture_pass
from oddvex_api.archive.prune import prune_archive
from oddvex_api.db import ARCHIVE_MODELS, ArchivedEvent, ArchivedOdds, ArchivedProp, SnapshotRun

from .archive_support import (
    OTHER_PREGAME,
    PREGAME,
    T0,
    ArchiveEnv,
    archive_env,
    capture_schedule,
    make_bet,
    make_user,
)

__all__ = ["archive_env"]


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def captured(env: ArchiveEnv, model: Any, event_id: str) -> list[datetime]:
    with env.session_factory() as db:
        return sorted(set(db.scalars(select(model.captured_at).where(model.event_id == event_id))))


def latest_props(env: ArchiveEnv, event_id: str) -> dict[tuple[str, str, str], datetime]:
    """Per (player, market, book) of the event, when its latest row was captured."""
    latest: dict[tuple[str, str, str], datetime] = {}
    with env.session_factory() as db:
        for r in db.execute(
            select(
                ArchivedProp.player_id,
                ArchivedProp.market,
                ArchivedProp.sportsbook_id,
                ArchivedProp.captured_at,
            )
            .where(ArchivedProp.event_id == event_id)
            .order_by(ArchivedProp.captured_at)
        ):
            latest[(r.player_id, r.market, r.sportsbook_id)] = r.captured_at
    return latest


def orphan_rows(env: ArchiveEnv) -> int:
    """Archive rows whose run_id names no run."""
    with env.session_factory() as db:
        runs = set(db.scalars(select(SnapshotRun.id)))
        return sum(
            1
            for model in ARCHIVE_MODELS
            if model is not SnapshotRun
            for run_id in db.scalars(select(model.run_id))  # type: ignore[attr-defined]
            if run_id not in runs
        )


def test_closing_rows_and_bet_anchors_survive_and_other_rows_go(archive_env: ArchiveEnv) -> None:
    env = archive_env
    capture_schedule(env)  # T0, +360, +720, +1800; every game below stays upcoming
    with env.session_factory() as db:
        make_bet(
            db,
            make_user(db),
            at(400),
            [{"event_id": PREGAME, "market": "moneyline", "outcome_key": "home"}],
        )
        db.commit()
    before = {model: captured(env, model, PREGAME) for model in (ArchivedEvent, ArchivedOdds)}
    assert before[ArchivedEvent] == [at(0), at(360), at(720), at(1800)]
    closing_props = latest_props(env, PREGAME)
    assert closing_props

    # Not due again within the hour.
    env.provider.current = at(1900)
    assert prune_archive(env.engine, env.provider, env.settings) is None

    env.provider.current = T0 + timedelta(days=8)
    report = prune_archive(env.engine, env.provider, env.settings)
    assert report is not None and report.status == "ok" and report.rows_deleted > 0

    # The bet placed at +400 s anchors the capture at +360 s; the last upcoming row
    # (+1800 s) is the closing row. The others are gone.
    assert captured(env, ArchivedEvent, PREGAME) == [at(360), at(1800)]
    assert captured(env, ArchivedOdds, PREGAME) == [at(360), at(1800)]
    # A game nobody bet on keeps only its closing rows.
    assert captured(env, ArchivedEvent, OTHER_PREGAME) == [at(1800)]
    # Props keep the closing offers: per (player, market, book) the latest row at or
    # before the closing capture, however old (an unchanged offer is stored once).
    with env.session_factory() as db:
        kept = {
            (r.player_id, r.market, r.sportsbook_id): r.captured_at
            for r in db.execute(
                select(
                    ArchivedProp.player_id,
                    ArchivedProp.market,
                    ArchivedProp.sportsbook_id,
                    ArchivedProp.captured_at,
                ).where(ArchivedProp.event_id == PREGAME)
            )
        }
        assert db.scalar(
            select(func.count()).select_from(ArchivedProp).where(ArchivedProp.event_id == PREGAME)
        ) == len(kept)
    assert kept == closing_props
    with env.session_factory() as db:
        run = db.scalars(
            select(SnapshotRun).where(SnapshotRun.kind == "prune").order_by(SnapshotRun.id.desc())
        ).first()
        assert run is not None and run.prune_cutoff == T0 + timedelta(days=1)
        # The closing capture is complete: the books still quoting and a tombstone for
        # each book that had stopped (moneyline 3 + 2, spread 2 + 2, total 2 + 1).
        books = db.execute(
            select(ArchivedOdds.market, func.count(func.distinct(ArchivedOdds.sportsbook_id)))
            .where(ArchivedOdds.event_id == PREGAME, ArchivedOdds.captured_at == at(1800))
            .group_by(ArchivedOdds.market)
        ).all()
        assert dict(books) == {"moneyline": 5, "spread": 4, "total": 3}
    # Capture runs are kept (400 days) and no row points at a missing run.
    assert orphan_rows(env) == 0

    # A second prune finds nothing new to delete in the window it already handled.
    env.provider.current += timedelta(hours=2)
    again = prune_archive(env.engine, env.provider, env.settings)
    assert again is not None and again.rows_deleted == 0


def test_kept_rows_and_runs_go_together_at_the_keep_horizon(archive_env: ArchiveEnv) -> None:
    env = archive_env
    env.settings = env.settings.model_copy(update={"snapshot_keep_days": 10})
    capture_schedule(env, (0, 360))
    env.provider.current = T0 + timedelta(days=8)
    prune_archive(env.engine, env.provider, env.settings)
    with env.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ArchivedOdds))
        assert (
            db.scalar(
                select(func.count()).select_from(SnapshotRun).where(SnapshotRun.kind == "odds")
            )
            == 2
        )

    # Eleven days on, past the 10-day keep horizon: closing rows and their runs go in the
    # same pass, rows first.
    env.provider.current = T0 + timedelta(days=11)
    report = prune_archive(env.engine, env.provider, env.settings)
    assert report is not None and report.status == "ok"
    with env.session_factory() as db:
        for model in (ArchivedOdds, ArchivedEvent, ArchivedProp):
            assert db.scalar(select(func.count()).select_from(model)) == 0, model
        kinds = set(db.scalars(select(SnapshotRun.kind)))
        assert kinds == {"prune"}
    assert orphan_rows(env) == 0


def test_capture_runs_the_prune_hourly(archive_env: ArchiveEnv) -> None:
    env = archive_env
    first = env.capture(T0, force=False)
    assert first.prune is not None
    env.provider.current = at(1800)
    assert capture_pass(env.engine, env.provider, env.settings).prune is None
    env.provider.current = at(3600)
    assert capture_pass(env.engine, env.provider, env.settings).prune is not None
