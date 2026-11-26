"""Capture passes: the flag, intervals, dedupe, tombstones, scope, the cap, failures, the
append-only guard, data-mode isolation, the lock and the script."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import func, insert, select, text
from sqlalchemy.exc import IntegrityError

from oddvex_api.archive.capture import (
    ADVISORY_LOCK_KEY,
    LIVE_GRACE_HOURS,
    PROP_REFRESH_HOURS,
    UPCOMING_GRACE_HOURS,
    StatusRecord,
    archive_bytes,
    capture_pass,
    capture_status,
    in_scope,
)
from oddvex_api.archive.guard import ArchiveIsAppendOnly
from oddvex_api.archive.prune import prune_archive
from oddvex_api.archive.service import archived_odds, archived_props
from oddvex_api.archive.view import prop_lookback, props_max_gap_seconds
from oddvex_api.config import Settings
from oddvex_api.db import (
    ARCHIVE_MODELS,
    ArchivedEvent,
    ArchivedOdds,
    ArchivedProp,
    ArchivedStatus,
    SnapshotRun,
)
from oddvex_api.providers import Event, OddsSnapshot, PropOffer

from .archive_support import (
    LIVE,
    OTHER_PREGAME,
    PREGAME,
    T0,
    ArchiveEnv,
    archive_env,
    capture_script,
    enable_archive,
    set_quotes,
)
from .conftest import EXTERNAL_DATABASE_URL
from .fakes import ControlledProvider, moneyline

__all__ = ["archive_env"]


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


def test_capture_resumes_once_the_prune_brings_the_archive_under_the_cap(
    archive_env: ArchiveEnv,
) -> None:
    """The cap counts the rows the archive holds, not the size of its files. On PostgreSQL
    a delete followed by a plain VACUUM (what autovacuum does) leaves the files as large as
    before, so a cap measured on file size would never release after the prune."""
    env = archive_env
    for offset in (0, 360, 720):
        set_quotes(env.provider, offset)
        report = env.capture(T0 + timedelta(seconds=offset))
        assert report.odds is not None and report.odds.status == "ok"
    with env.session_factory() as db:
        full_at = archive_bytes(db)
    env.settings = env.settings.model_copy(update={"snapshot_max_bytes": full_at})
    report = env.capture(T0 + timedelta(seconds=1080))
    assert report.full is True
    assert report.odds is not None and report.odds.status == "skipped_full"
    # Eight days on, the prune removes the full-resolution rows of every game.
    env.provider.current = T0 + timedelta(days=8)
    pruned = prune_archive(env.engine, env.provider, env.settings, force=True)
    assert pruned is not None and pruned.status == "ok" and pruned.rows_deleted > 0
    if env.engine.dialect.name == "postgresql":
        with env.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
            for model in ARCHIVE_MODELS:
                c.execute(text(f"VACUUM {model.__tablename__}"))
    with env.session_factory() as db:
        assert archive_bytes(db) < full_at
    report = env.capture(T0 + timedelta(days=8, seconds=360))
    assert report.full is False
    assert report.odds is not None and report.odds.status == "ok"
    assert report.odds.rows_written > 0


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


def test_the_capture_script(archive_env: ArchiveEnv) -> None:
    env = archive_env
    enable_archive(env.session_factory, False)
    off = capture_script(env)
    assert off.returncode == 0, off.stderr
    assert "Snapshot archive is off; nothing captured." in off.stdout
    assert total_rows(env) == 0
    # With the flag off the provider is never built: a replay provider pointed at a
    # missing dataset would fail if it were loaded.
    replay = capture_script(
        env,
        extra={"ODDVEX_DATA_PROVIDER": "replay", "ODDVEX_REPLAY_DATA_PATH": "/nonexistent/replay"},
    )
    assert replay.returncode == 0, replay.stderr
    assert "Snapshot archive is off; nothing captured." in replay.stdout

    enable_archive(env.session_factory)
    dry = capture_script(env, "--dry-run")
    assert dry.returncode == 0 and "Dry run, nothing saved" in dry.stdout, dry.stderr
    assert total_rows(env) == 0

    captured = capture_script(env)
    assert captured.returncode == 0, captured.stderr
    assert "odds ok" in captured.stdout and "props ok" in captured.stdout
    again = capture_script(env)
    assert again.returncode == 0 and "odds not due" in again.stdout, again.stdout

    stats = capture_script(env, "--stats")
    assert stats.returncode == 0 and "Snapshot archive on" in stats.stdout, stats.stderr
    pruned = capture_script(env, "--prune-only", "--force")
    assert pruned.returncode == 0 and "prune ok" in pruned.stdout, pruned.stdout
    # ``--reclaim`` only checks the indexes (PostgreSQL), which are as small as they can
    # be here; on SQLite there is nothing to check. It captures and prunes nothing.
    rows = total_rows(env)
    reclaimed = capture_script(env, "--reclaim")
    assert reclaimed.returncode == 0, reclaimed.stderr
    assert "odds not due; props not due; prune not due" in reclaimed.stdout
    assert "reclaim: nothing to rebuild" in reclaimed.stdout
    assert total_rows(env) == rows


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


class DoubleheaderProvider(ControlledProvider):
    """One player is offered on two games in scope, PREGAME and OTHER_PREGAME, with the
    first game's offers fixed as they were at T0."""

    def __init__(self) -> None:
        super().__init__()
        event = self.get_event(PREGAME)
        assert event is not None
        self.player_id = self.list_players(team_id=event.home_team_id)[0].id
        self.fixed = super().get_prop_offers(self.player_id)
        self.other_line = 0.0

    def get_prop_offers(self, player_id: str, market: str | None = None) -> list[PropOffer]:
        if player_id != self.player_id:
            return super().get_prop_offers(player_id, market)
        offers = [o for o in self.fixed if market is None or o.market == market]
        second = [
            o.model_copy(
                update={
                    "event_id": OTHER_PREGAME,
                    "provider_id": o.provider_id + ":game2",
                    "line": (o.line or 0.0) + 1.0 + self.other_line,
                }
            )
            for o in offers
            if o.event_id == PREGAME
        ]
        return offers + second


def test_a_player_with_two_games_in_scope_keeps_both_games_offers(
    archive_env: ArchiveEnv,
) -> None:
    env = archive_env
    p = DoubleheaderProvider()
    env.provider = p
    env.capture(T0)
    where = (ArchivedProp.player_id == p.player_id,)
    first = count(env, ArchivedProp, *where, ArchivedProp.event_id == PREGAME)
    assert first > 0
    assert count(env, ArchivedProp, *where, ArchivedProp.event_id == OTHER_PREGAME) == first
    # Only the second game's offers change: the first game's rows stay as they were,
    # with no overwrite and no tombstone.
    p.other_line = 0.5
    env.capture(T0 + timedelta(seconds=360))
    assert count(env, ArchivedProp, *where, ArchivedProp.event_id == PREGAME) == first
    assert count(env, ArchivedProp, *where, ArchivedProp.event_id == OTHER_PREGAME) == 2 * first
    second = ArchivedProp.captured_at == T0 + timedelta(seconds=360)
    assert count(env, ArchivedProp, *where, second) == first  # all of them the second game's
    with env.session_factory() as db:
        read = archived_props(db, p, env.settings, p.player_id, None, T0 + timedelta(seconds=400))
    by_game: dict[str, set[Any]] = {}
    for offer in read.offers:
        by_game.setdefault(offer.event_id, set()).add((offer.market, offer.line))
    assert set(by_game) == {PREGAME, OTHER_PREGAME}
    assert len(by_game[PREGAME]) == len(by_game[OTHER_PREGAME])


def test_a_game_leaving_scope_tombstones_its_offers(archive_env: ArchiveEnv) -> None:
    env = archive_env
    p = env.provider
    event = p.get_event(PREGAME)
    assert event is not None
    player_id = p.list_players(team_id=event.home_team_id)[0].id
    env.capture(T0)
    with env.session_factory() as db:
        before = archived_props(db, p, env.settings, player_id, None, T0 + timedelta(seconds=60))
    assert before.offers and {o.status for o in before.offers} >= {"open"}
    stored = count(env, ArchivedProp, ArchivedProp.event_id == PREGAME)
    open_keys = count(
        env, ArchivedProp, ArchivedProp.event_id == PREGAME, ArchivedProp.status != "unavailable"
    )
    # The game goes final and leaves scope: every stored offer of it gets a tombstone,
    # and the props read no longer shows the finished game's offers as open.
    p.finish(PREGAME, 3, 2)
    env.capture(T0 + timedelta(seconds=360))
    tombstones = count(
        env,
        ArchivedProp,
        ArchivedProp.event_id == PREGAME,
        ArchivedProp.status == "unavailable",
        ArchivedProp.captured_at == T0 + timedelta(seconds=360),
    )
    assert tombstones == open_keys
    with env.session_factory() as db:
        after = archived_props(db, p, env.settings, player_id, None, T0 + timedelta(seconds=400))
        # As of before the game left scope, the offers read back as they were.
        earlier = archived_props(db, p, env.settings, player_id, None, T0 + timedelta(seconds=60))
    assert [o for o in after.offers if o.event_id == PREGAME] == []
    assert earlier.offers == before.offers
    # A second pass writes no further tombstones.
    env.capture(T0 + timedelta(seconds=720))
    assert count(env, ArchivedProp, ArchivedProp.event_id == PREGAME) == stored + open_keys


class _Schedule:
    def __init__(self, events: list[Event]) -> None:
        self.events = events

    def list_events(self) -> list[Event]:
        return self.events


def test_a_game_still_upcoming_long_after_its_start_leaves_scope(
    archive_env: ArchiveEnv,
) -> None:
    """A postponed game the provider never updates is captured for at most
    ``UPCOMING_GRACE_HOURS`` after its start time."""
    env = archive_env
    event = env.provider.get_event(PREGAME)
    assert event is not None and event.status == "upcoming"
    now = T0
    inside = event.model_copy(
        update={"id": "delayed", "start_time": now - timedelta(hours=UPCOMING_GRACE_HOURS)}
    )
    outside = event.model_copy(
        update={
            "id": "stuck",
            "start_time": now - timedelta(hours=UPCOMING_GRACE_HOURS, seconds=1),
        }
    )
    found = in_scope(_Schedule([event, inside, outside]), now, env.settings)  # type: ignore[arg-type]
    assert [e.id for e in found] == [PREGAME, "delayed"]


def test_a_game_still_live_long_after_its_start_leaves_scope(archive_env: ArchiveEnv) -> None:
    """A game the provider keeps calling ``live`` would never leave scope, and the prune
    reduces a game only once its last capture has aged out: its rows would stay at full
    resolution and grow until the cap stopped capture for every game. It is captured for
    at most ``LIVE_GRACE_HOURS`` after its start time, and then leaves like any other:
    its prop offers are tombstoned and the prune handles it."""
    env = archive_env
    live = env.provider.get_event(LIVE)
    assert live is not None and live.status == "live"
    now = T0
    inside = live.model_copy(
        update={"id": "long", "start_time": now - timedelta(hours=LIVE_GRACE_HOURS)}
    )
    outside = live.model_copy(
        update={"id": "stuck", "start_time": now - timedelta(hours=LIVE_GRACE_HOURS, seconds=1)}
    )
    found = in_scope(_Schedule([live, inside, outside]), now, env.settings)  # type: ignore[arg-type]
    assert [e.id for e in found] == [LIVE, "long"]


class DelayedGameProvider(ControlledProvider):
    """PREGAME keeps being pushed back: always upcoming, ten hours ahead of the clock, and
    the only game on the schedule. One player is offered on it, with the offers fixed as
    they were at T0."""

    def __init__(self) -> None:
        super().__init__()
        event = super().get_event(PREGAME)
        assert event is not None
        self.event = event
        self.player_id = self.list_players(team_id=event.home_team_id)[0].id
        self.fixed = [o for o in super().get_prop_offers(self.player_id) if o.event_id == PREGAME]

    def _delayed(self) -> Event:
        return self.event.model_copy(
            update={"status": "upcoming", "start_time": self.current + timedelta(hours=10)}
        )

    def list_events(
        self, league: str | None = None, status: str | None = None, on_date: Any = None
    ) -> list[Event]:
        return [self._delayed()]

    def get_event(self, event_id: str) -> Event | None:
        return self._delayed() if event_id == PREGAME else None

    def get_prop_offers(self, player_id: str, market: str | None = None) -> list[PropOffer]:
        if player_id != self.player_id:
            return []
        return [o for o in self.fixed if market is None or o.market == market]


def test_an_unchanged_offer_is_stored_again_once_a_day_so_the_props_read_keeps_it(
    archive_env: ArchiveEnv,
) -> None:
    """The props read looks back 48 hours. A game that keeps being pushed back stays in
    scope longer than that with the same offers; each unchanged offer is stored again
    once its latest row is ``PROP_REFRESH_HOURS`` old, so the read still finds it."""
    env = archive_env
    p = DelayedGameProvider()
    env.provider = p
    env.settings = env.settings.model_copy(update={"snapshot_props_interval_seconds": 3600})
    keys = len(p.fixed)
    assert keys > 0
    where = (ArchivedProp.player_id == p.player_id, ArchivedProp.event_id == PREGAME)
    for hour in range(51):
        report = env.capture(T0 + timedelta(hours=hour))
        assert report.props is not None and report.props.status == "ok"
    with env.session_factory() as db:
        written = sorted(db.scalars(select(ArchivedProp.captured_at).where(*where).distinct()))
    assert written == [T0 + timedelta(hours=h) for h in range(0, 51, PROP_REFRESH_HOURS)]
    assert count(env, ArchivedProp, *where) == keys * len(written)
    with env.session_factory() as db:
        read = archived_props(
            db, p, env.settings, p.player_id, None, T0 + timedelta(hours=50, minutes=30)
        )
    assert read.coverage.status == "captured"
    assert len(read.offers) == keys
    assert {o.captured_at for o in read.offers} == {T0 + timedelta(hours=48)}


@pytest.mark.parametrize("props_interval", [360, 3600])
@pytest.mark.parametrize("horizon", [12, 14, 36])
def test_an_offer_unchanged_for_a_day_is_read_at_every_capture_horizon(
    archive_env: ArchiveEnv, horizon: int, props_interval: int
) -> None:
    """Regression (review round 4, blocking). The props read looked back the capture
    horizon plus 12 hours; an unchanged offer is stored again only at the first props
    capture after its row is 24 hours old. With a horizon of 14 hours or less the
    look-back was shorter than that, so between the row's 24th hour and the next props
    capture the read answered ``captured`` without the offer.

    The worst case: the offers are stored at T0, and the next props capture runs one
    second before they are 24 hours old, so it stores nothing. That capture covers reads
    up to the props gap limit after it, when the rows are almost 24 hours and the gap
    limit old. Every offer must still be there, at every allowed horizon; one
    microsecond later the answer is a gap."""
    env = archive_env
    env.settings = env.settings.model_copy(
        update={
            "snapshot_horizon_hours": horizon,
            "snapshot_props_interval_seconds": props_interval,
        }
    )
    p = DelayedGameProvider()  # one game, always ten hours ahead: in scope at every horizon
    env.provider = p
    keys = len(p.fixed)
    second = T0 + timedelta(hours=PROP_REFRESH_HOURS, seconds=-1)
    for moment in (T0, second):
        report = env.capture(moment)
        assert report.props is not None and report.props.status == "ok"
    where = (ArchivedProp.player_id == p.player_id, ArchivedProp.event_id == PREGAME)
    with env.session_factory() as db:
        assert set(db.scalars(select(ArchivedProp.captured_at).where(*where))) == {T0}
    gap = timedelta(seconds=props_max_gap_seconds(env.settings))
    assert gap == timedelta(seconds=2 * props_interval + 120)
    last_covered = second + gap
    assert last_covered - T0 <= prop_lookback(env.settings)
    with env.session_factory() as db:
        at_capture = archived_props(db, p, env.settings, p.player_id, None, second)
        at_the_edge = archived_props(db, p, env.settings, p.player_id, None, last_covered)
        past_it = archived_props(
            db, p, env.settings, p.player_id, None, last_covered + timedelta(microseconds=1)
        )
    for read in (at_capture, at_the_edge):
        assert read.coverage.status == "captured" and read.coverage.captured_at == second
        assert len(read.offers) == keys and {o.captured_at for o in read.offers} == {T0}
    # The gap limit itself is inside: one microsecond more is a gap, with no offers.
    assert past_it.coverage.status == "archive_gap" and past_it.offers == []


def test_the_props_look_back_covers_the_refresh_at_every_allowed_setting() -> None:
    """The look-back is the horizon plus the game, and never less than the refresh age
    plus the props gap limit. The default (36 hours) is the documented 48 hours."""
    assert Settings(_env_file=None).snapshot_prop_lookback_seconds == 48 * 3600
    for horizon in range(1, 169):
        for interval in (60, 360, 3600, 86_400):
            settings = Settings(
                _env_file=None,
                snapshot_horizon_hours=horizon,
                snapshot_props_interval_seconds=interval,
            )
            lookback = settings.snapshot_prop_lookback_seconds
            gap = settings.snapshot_props_max_gap_seconds
            assert gap == 2 * interval + 120
            assert lookback >= PROP_REFRESH_HOURS * 3600 + gap, (horizon, interval)
            assert lookback >= (horizon + 12) * 3600, (horizon, interval)
            assert prop_lookback(settings) == timedelta(seconds=lookback)
    assert Settings(_env_file=None, snapshot_horizon_hours=12).snapshot_prop_lookback_seconds == (
        24 * 3600 + 7320
    )


def test_archive_settings_that_cannot_work_together_are_refused(archive_env: ArchiveEnv) -> None:
    """With a keep period no longer than the props look-back every archived props read
    would answer ``archive_pruned``. The application refuses to start with such settings
    and the capture script does nothing."""
    assert Settings(_env_file=None).snapshot_settings_problem() is None
    # 48 hours of look-back at the default horizon: two days of keeping is not more.
    short = Settings(_env_file=None, snapshot_keep_days=2, snapshot_retention_days=1)
    problem = short.snapshot_settings_problem()
    assert problem is not None and "ODDVEX_SNAPSHOT_KEEP_DAYS" in problem
    with pytest.raises(RuntimeError, match="ODDVEX_SNAPSHOT_KEEP_DAYS"):
        short.validate_for_startup()
    # Three days is; and so is a shorter keep period under a longer retention.
    assert Settings(_env_file=None, snapshot_keep_days=3).snapshot_settings_problem() is None
    assert Settings(_env_file=None, snapshot_keep_days=1).snapshot_settings_problem() is None
    week = Settings(_env_file=None, snapshot_horizon_hours=168, snapshot_keep_days=7)
    assert week.snapshot_settings_problem() is not None  # 180 hours of look-back
    refused = capture_script(
        archive_env,
        "--force",
        extra={"ODDVEX_SNAPSHOT_KEEP_DAYS": "2", "ODDVEX_SNAPSHOT_RETENTION_DAYS": "1"},
    )
    assert refused.returncode == 2 and "ODDVEX_SNAPSHOT_KEEP_DAYS" in refused.stderr
    assert total_rows(archive_env) == 0
