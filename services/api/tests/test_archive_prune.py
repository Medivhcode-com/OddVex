"""The retention prune: what survives the full-resolution window, how many captures bets
can keep, how coverage reads after it, and what goes at the keep horizon."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from oddvex_api.archive.capture import capture_pass
from oddvex_api.archive.prune import MAX_ANCHORS_PER_EVENT, prune_archive
from oddvex_api.archive.view import coverage_at
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


def test_bets_keep_a_bounded_number_of_captures_per_game(archive_env: ArchiveEnv) -> None:
    """However many bets one user (or many users) record, the prune keeps at most
    ``MAX_ANCHORS_PER_EVENT`` captures of a game for them, beyond its closing and last
    captures. Legs the archive cannot price anchor nothing. A flood of bets from one user
    cannot crowd out the captures other users' bets point at."""
    env = archive_env
    times = [at(360 * i) for i in range(12)]  # 0 .. 3,960 s; PREGAME stays upcoming
    for moment in times:
        report = env.capture(moment)
        assert report.odds is not None and report.odds.status == "ok"
    with env.session_factory() as db:
        events = sorted(set(db.scalars(select(ArchivedEvent.event_id))))
        # Per game: its closing capture (last upcoming row) and its last capture.
        ends = {
            event_id: {
                db.scalar(
                    select(func.max(ArchivedEvent.captured_at)).where(
                        ArchivedEvent.event_id == event_id, ArchivedEvent.status == status
                    )
                )
                for status in ("upcoming", "live")
            }
            - {None}
            for event_id in events
        }
        rows_before = db.scalar(select(func.count()).select_from(ArchivedEvent))
        flooder = make_user(db, "flood@example.test")
        for moment in times:
            # One structured bet per capture on PREGAME, and 20-leg parlays of
            # unstructured legs on every game in scope.
            make_bet(
                db,
                flooder,
                moment,
                [{"event_id": PREGAME, "market": "moneyline", "outcome_key": "home"}],
            )
            for first in range(0, len(events), 20):
                legs = [
                    {
                        "event_id": e,
                        "market": "player_points",
                        "outcome_key": None,
                        "selection": "x",
                    }
                    for e in events[first : first + 20]
                ]
                make_bet(db, flooder, moment, legs + legs[:1] if len(legs) == 1 else legs)
        # Seven other users with one bet each on captures 3 to 9; two on capture 9.
        for i in range(3, 10):
            make_bet(
                db,
                make_user(db, f"user{i}@example.test"),
                times[i] + timedelta(seconds=30),
                [{"event_id": PREGAME, "market": "moneyline", "outcome_key": "home"}],
            )
        make_bet(
            db,
            make_user(db, "second@example.test"),
            times[9] + timedelta(seconds=60),
            [{"event_id": PREGAME, "market": "moneyline", "outcome_key": "away"}],
        )
        db.commit()

    env.provider.current = T0 + timedelta(days=8)
    report = prune_archive(env.engine, env.provider, env.settings)
    assert report is not None and report.status == "ok"

    kept = captured(env, ArchivedEvent, PREGAME)
    # Ranked by users (each user's weight split over the captures they anchor): capture 9
    # (two users), then 3 to 7 (one user each, earliest first). The flooder's other
    # captures lose; the last capture (also the closing one) is always kept.
    assert len(kept) <= MAX_ANCHORS_PER_EVENT + 2
    assert kept == sorted({times[i] for i in (3, 4, 5, 6, 7, 9)} | {times[-1]})
    with env.session_factory() as db:
        odds_times = set(
            db.scalars(select(ArchivedOdds.captured_at).where(ArchivedOdds.event_id == PREGAME))
        )
        # Odds rows are kept only at or before kept captures.
        assert odds_times <= set(kept) | {times[0]}
        # Every other game, bet on only through unstructured legs, keeps only its closing
        # and last captures.
        for event_id in events:
            if event_id != PREGAME:
                assert set(captured(env, ArchivedEvent, event_id)) == ends[event_id], event_id
        rows_after = db.scalar(select(func.count()).select_from(ArchivedEvent))
    assert rows_after == sum(len(ends[e]) for e in events if e != PREGAME) + len(kept)
    assert rows_after < rows_before


def test_coverage_past_the_keep_horizon_is_archive_pruned(archive_env: ArchiveEnv) -> None:
    """When even the capture runs from before T are gone (past the 400-day horizon), a
    time before that horizon answers ``archive_pruned``, not ``not_captured``."""
    env = archive_env
    capture_schedule(env)
    with env.session_factory() as db:
        assert coverage_at(db, env.provider.name, PREGAME, at(100), env.settings).status == (
            "captured"
        )
    env.provider.current = T0 + timedelta(days=401)
    report = prune_archive(env.engine, env.provider, env.settings)
    assert report is not None and report.status == "ok"
    with env.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ArchivedEvent)) == 0
        assert set(db.scalars(select(SnapshotRun.kind))) == {"prune"}
        for event_id in (PREGAME, OTHER_PREGAME):
            coverage = coverage_at(db, env.provider.name, event_id, at(100), env.settings)
            assert coverage.status == "archive_pruned", event_id
        # A time inside the horizon with no run before it is before the first capture.
        later = T0 + timedelta(days=200)
        assert coverage_at(db, env.provider.name, PREGAME, later, env.settings).status == (
            "not_captured"
        )


def test_coverage_tells_pruned_from_never_in_scope(archive_env: ArchiveEnv) -> None:
    """After the prune, a capture whose row for the game is gone answers ``archive_pruned``
    only while the game was in scope then (within 36 h of its start and before its last
    capture); a game three days out, or one that had left scope, is ``not_captured``."""
    env = archive_env
    capture_schedule(env)
    far = env.provider.list_events(on_date=(T0 + timedelta(days=3)).date())[0]
    env.provider.current = T0 + timedelta(days=8)
    prune_archive(env.engine, env.provider, env.settings)
    with env.session_factory() as db:
        name = env.provider.name
        assert coverage_at(db, name, PREGAME, at(400), env.settings).status == "archive_pruned"
        assert coverage_at(db, name, far.id, at(400), env.settings).status == "not_captured"
        # The last capture (1,800 s) is kept and is complete.
        last = coverage_at(db, name, PREGAME, at(1900), env.settings)
        assert last.status == "captured" and last.captured_at == at(1800)
