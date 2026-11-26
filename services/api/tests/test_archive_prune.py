"""The retention prune: what survives the full-resolution window, how many captures bets
can keep, how coverage reads after it, what goes at the keep horizon, and what a prune
that is cut short, or that runs beside a read, leaves the reads to answer."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import delete, func, select

from oddvex_api.archive import prune as prune_module
from oddvex_api.archive import service as service_module
from oddvex_api.archive import view as view_module
from oddvex_api.archive.capture import StatusRecord, capture_pass, capture_status, new_run
from oddvex_api.archive.placement import placement_prices
from oddvex_api.archive.prune import MAX_ANCHORS_PER_EVENT, prune_archive
from oddvex_api.archive.service import archived_odds, archived_props, archived_status
from oddvex_api.archive.view import ArchiveBusy, coverage_at
from oddvex_api.db import (
    ARCHIVE_MODELS,
    ArchivedEvent,
    ArchivedOdds,
    ArchivedProp,
    ArchivedStatus,
    Bet,
    SnapshotRun,
    User,
)
from oddvex_api.providers import Event, Player, PropOffer

from .archive_support import (
    LIVE,
    OTHER_PREGAME,
    PREGAME,
    PREGAME_2,
    T0,
    USER_BOOKS,
    ArchiveEnv,
    archive_env,
    capture_schedule,
    make_bet,
    make_user,
)
from .fakes import ControlledProvider, moneyline

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

    # The first capture (T0) marks when the game entered scope; the bet placed at +400 s
    # anchors the capture at +360 s; the last upcoming row (+1800 s) is the closing row.
    # The capture at +720 s is gone.
    assert captured(env, ArchivedEvent, PREGAME) == [at(0), at(360), at(1800)]
    assert captured(env, ArchivedOdds, PREGAME) == [at(0), at(360), at(1800)]
    # A game nobody bet on keeps only its first and its closing captures.
    assert captured(env, ArchivedEvent, OTHER_PREGAME) == [at(0), at(1800)]
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

    # Eleven days on, past the 10-day keep horizon: every game's rows go, and with them
    # the capture runs nothing refers to any more. The last successful odds and props
    # captures stay, so a later time still reads when capture last ran.
    env.provider.current = T0 + timedelta(days=11)
    report = prune_archive(env.engine, env.provider, env.settings)
    assert report is not None and report.status == "ok"
    with env.session_factory() as db:
        for model in (ArchivedOdds, ArchivedEvent, ArchivedProp):
            assert db.scalar(select(func.count()).select_from(model)) == 0, model
        runs = sorted(
            db.execute(
                select(SnapshotRun.kind, SnapshotRun.captured_at).where(SnapshotRun.kind != "prune")
            ).tuples()
        )
        assert runs == [("odds", at(360)), ("props", at(360))]
        name = env.provider.name
        # A time before the horizon answers archive_pruned; one after it, with no
        # capture since, a gap.
        assert coverage_at(db, name, PREGAME, at(400), env.settings).status == "archive_pruned"
        later = T0 + timedelta(days=5)
        assert coverage_at(db, name, PREGAME, later, env.settings).status == "archive_gap"
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
    weighs one vote, split over the captures that user anchors."""
    env = archive_env
    times = [at(360 * i) for i in range(12)]  # 0 .. 3,960 s; PREGAME stays upcoming
    for moment in times:
        report = env.capture(moment)
        assert report.odds is not None and report.odds.status == "ok"
    with env.session_factory() as db:
        events = sorted(set(db.scalars(select(ArchivedEvent.event_id))))
        # Per game: its first capture, its closing capture (last upcoming row) and its
        # last capture.
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
            | {
                db.scalar(
                    select(func.min(ArchivedEvent.captured_at)).where(
                        ArchivedEvent.event_id == event_id
                    )
                )
            }
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
    # captures lose; the first capture and the last one (also the closing one) are
    # always kept.
    assert len(kept) <= MAX_ANCHORS_PER_EVENT + 3
    assert kept == sorted({times[i] for i in (3, 4, 5, 6, 7, 9)} | {times[0], times[-1]})
    with env.session_factory() as db:
        odds_times = set(
            db.scalars(select(ArchivedOdds.captured_at).where(ArchivedOdds.event_id == PREGAME))
        )
        # Odds rows are kept only at or before kept captures.
        assert odds_times <= set(kept) | {times[0]}
        # Every other game, bet on only through unstructured legs, keeps only its first,
        # closing and last captures.
        for event_id in events:
            if event_id != PREGAME:
                assert set(captured(env, ArchivedEvent, event_id)) == ends[event_id], event_id
        rows_after = db.scalar(select(func.count()).select_from(ArchivedEvent))
    assert rows_after == sum(len(ends[e]) for e in events if e != PREGAME) + len(kept)
    assert rows_after < rows_before


def test_coverage_past_the_keep_horizon_is_archive_pruned(archive_env: ArchiveEnv) -> None:
    """Past the keep horizon (400 days) capture runs are no longer all kept, so a time
    before it answers ``archive_pruned``, not ``not_captured``."""
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
        for event_id in (PREGAME, OTHER_PREGAME):
            coverage = coverage_at(db, env.provider.name, event_id, at(100), env.settings)
            assert coverage.status == "archive_pruned", event_id
            assert coverage.snapshot is None
        # A time inside the horizon: the last capture before the horizon is still known,
        # so the answer is a gap, not "never captured".
        later = T0 + timedelta(days=200)
        assert coverage_at(db, env.provider.name, PREGAME, later, env.settings).status == (
            "archive_gap"
        )
        # The same on an archive that never captured anything before that time.
        db.execute(delete(SnapshotRun).where(SnapshotRun.kind != "prune"))
        assert coverage_at(db, env.provider.name, PREGAME, later, env.settings).status == (
            "not_captured"
        )
        db.rollback()


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


def test_a_game_whose_rows_straddle_the_cutoff_is_not_pruned_yet(archive_env: ArchiveEnv) -> None:
    """The prune handles a game only once all of its rows are past the 7 days. A prune
    whose cutoff falls between a game's captures leaves every row of it, so a read inside
    the 7 days answers as before."""
    env = archive_env
    capture_schedule(env)
    with env.session_factory() as db:
        before = archived_odds(db, env.provider, env.settings, PREGAME, "moneyline", at(800))
    assert before.coverage.status == "captured"
    env.provider.current = T0 + timedelta(days=7, seconds=600)  # cutoff T0 + 600 s
    report = prune_archive(env.engine, env.provider, env.settings, force=True)
    assert report is not None and report.status == "ok"
    assert at(720) in captured(env, ArchivedEvent, PREGAME)
    with env.session_factory() as db:
        after = archived_odds(db, env.provider, env.settings, PREGAME, "moneyline", at(800))
    assert after.model_dump() == before.model_dump()


def test_one_users_flood_does_not_outrank_other_users_captures(archive_env: ArchiveEnv) -> None:
    """Each user's weight is split over the captures that user anchors on a game. One user
    anchoring captures 0 to 3 weighs a quarter on each; six other users anchoring one
    capture each among 5 to 10 weigh one each, so those six are the kept anchors."""
    env = archive_env
    times = [at(360 * i) for i in range(12)]
    for moment in times:
        env.capture(moment)
    leg = {"event_id": PREGAME, "market": "moneyline", "outcome_key": "home"}
    with env.session_factory() as db:
        flooder = make_user(db, "flood@example.test")
        for i in range(4):
            make_bet(db, flooder, times[i] + timedelta(seconds=10), [leg])
        for i in range(5, 11):
            make_bet(
                db, make_user(db, f"user{i}@example.test"), times[i] + timedelta(seconds=10), [leg]
            )
        db.commit()
    env.provider.current = T0 + timedelta(days=8)
    report = prune_archive(env.engine, env.provider, env.settings)
    assert report is not None and report.status == "ok"
    assert captured(env, ArchivedEvent, PREGAME) == sorted(
        {times[i] for i in range(5, 11)} | {times[0], times[-1]}
    )


def test_a_game_that_entered_scope_after_a_capture_is_not_captured_then(
    archive_env: ArchiveEnv,
) -> None:
    """A game three days out is not in the T0 capture. It enters scope 36 hours before its
    start, is captured, and is pruned. A time covered by the T0 capture still answers
    ``not_captured`` for it, not ``archive_pruned``."""
    env = archive_env
    far = env.provider.list_events(on_date=(T0 + timedelta(days=3)).date())[0]
    env.capture(T0)
    entered = far.start_time - timedelta(hours=35)
    moments = [entered + timedelta(seconds=360 * i) for i in range(3)]
    for moment in moments:
        env.capture(moment)
    assert captured(env, ArchivedEvent, far.id) == moments
    env.provider.current = entered + timedelta(days=8)
    report = prune_archive(env.engine, env.provider, env.settings)
    assert report is not None and report.status == "ok"
    with env.session_factory() as db:
        name = env.provider.name
        assert coverage_at(db, name, far.id, at(100), env.settings).status == "not_captured"
        # Its kept first and last captures are captured; the pruned one between them is
        # archive_pruned.
        statuses = [
            coverage_at(db, name, far.id, moment + timedelta(seconds=60), env.settings).status
            for moment in moments
        ]
        assert statuses == ["captured", "archive_pruned", "captured"]


def test_the_props_read_after_the_prune_never_shows_withdrawn_offers(
    archive_env: ArchiveEnv,
) -> None:
    """The tombstone scenario, then the prune. The read inside the closing capture's
    window answers exactly as before the prune; a read after the game's offers were
    withdrawn still shows none of them, and names the game as pruned rather than serving
    the closing offers as open."""
    env = archive_env
    p = env.provider
    event = p.get_event(PREGAME)
    assert event is not None
    player_id = p.list_players(team_id=event.home_team_id)[0].id
    env.capture(T0)
    p.finish(PREGAME, 3, 2)
    env.capture(at(360))  # the game left scope: every open offer of it is tombstoned
    times = (at(-1), at(60), at(400), at(700))
    with env.session_factory() as db:
        before = {t: archived_props(db, p, env.settings, player_id, None, t) for t in times}
    assert [o for o in before[at(400)].offers if o.event_id == PREGAME] == []
    assert [o for o in before[at(60)].offers if o.event_id == PREGAME]
    assert all(r.pruned_event_ids == [] for r in before.values())

    p.current = T0 + timedelta(days=8)
    report = prune_archive(env.engine, p, env.settings)
    assert report is not None and report.status == "ok"
    with env.session_factory() as db:
        after = {t: archived_props(db, p, env.settings, player_id, None, t) for t in times}
    # Before the first capture: nothing, and nothing was pruned.
    assert after[at(-1)].model_dump() == before[at(-1)].model_dump()
    # Between the closing capture and the next props capture: exactly as before.
    assert after[at(60)].model_dump() == before[at(60)].model_dump()
    # After the tombstones: still no offer of the finished game, and it is named.
    for t in (at(400), at(700)):
        assert [o for o in after[t].offers if o.event_id == PREGAME] == []
        assert PREGAME in after[t].pruned_event_ids
        assert after[t].coverage.status == "captured"


# ------------------------------------------------------------ the keep horizon
class OneGameProvider(ControlledProvider):
    """Only PREGAME is on the schedule and only one of its home team's players has prop
    offers, so a capture is a handful of rows: the tests below are about one game."""

    def __init__(self) -> None:
        super().__init__()
        event = self.get_event(PREGAME)
        assert event is not None
        self.player_id = ControlledProvider.list_players(self, team_id=event.home_team_id)[0].id

    def list_events(
        self, league: str | None = None, status: str | None = None, on_date: date | None = None
    ) -> list[Event]:
        return [e for e in super().list_events(league, status, on_date) if e.id == PREGAME]

    def list_players(
        self, league: str | None = None, team_id: str | None = None, query: str | None = None
    ) -> list[Player]:
        players = super().list_players(league=league, team_id=team_id, query=query)
        return [player for player in players if player.id == self.player_id]


def _capture_with_a_steady_book(env: ArchiveEnv, offset: int) -> None:
    """northline changes at every capture; summit keeps one price and one
    ``last_updated``, so its only stored row is the first capture's."""
    env.provider.set_odds(
        PREGAME,
        "moneyline",
        [
            ("northline", "open", 30, moneyline(-120 - offset // 100, -110)),
            ("summit", "open", 30 + offset, moneyline(-130, 120)),
        ],
    )
    report = env.capture(at(offset))
    assert report.odds is not None and report.odds.status == "ok"


def test_the_keep_horizon_never_takes_a_carried_forward_quote_from_a_kept_capture(
    archive_env: ArchiveEnv,
) -> None:
    """Regression (review round 3). A kept capture holds rows older than itself: a quote
    unchanged since an earlier capture is stored once. When the keep horizon falls between
    that old row and the capture, the row must stay, or a stored bet is priced from fewer
    books with coverage ``captured``. A game's rows leave together, once its last capture
    is past the horizon; from then on the answer is ``archive_pruned`` with no quotes."""
    env = archive_env
    env.provider = OneGameProvider()
    env.settings = env.settings.model_copy(update={"snapshot_keep_days": 10})
    for offset in (0, 360, 720):
        _capture_with_a_steady_book(env, offset)
    with env.session_factory() as db:
        bet_id = make_bet(
            db,
            make_user(db),
            at(730),
            [{"event_id": PREGAME, "market": "moneyline", "outcome_key": "away"}],
        ).id
        db.commit()
    env.provider.current = T0 + timedelta(days=8)
    report = prune_archive(env.engine, env.provider, env.settings)
    assert report is not None and report.status == "ok"

    def read() -> tuple[Any, ...]:
        with env.session_factory() as db:
            odds = archived_odds(db, env.provider, env.settings, PREGAME, "moneyline", at(730))
            bet = db.get(Bet, bet_id)
            assert bet is not None
            (leg,) = placement_prices(db, env.provider, env.settings, bet, ["northline", "summit"])
            rows = sorted(
                db.execute(
                    select(ArchivedOdds.sportsbook_id, ArchivedOdds.captured_at).where(
                        ArchivedOdds.event_id == PREGAME, ArchivedOdds.market == "moneyline"
                    )
                ).tuples()
            )
        return odds.model_dump(), leg.model_dump(), rows

    odds, leg, rows = before = read()
    assert odds["coverage"]["status"] == "captured"
    assert [q["sportsbook"]["key"] for q in odds["quotes"]] == ["northline", "summit"]
    # The best away price is summit's +120, a row captured at T0 and carried forward.
    assert leg["status"] == "priced"
    assert leg["best_at_your_books"]["sportsbook"]["key"] == "summit"
    assert leg["best_at_your_books"]["price"]["american"] == 120
    assert leg["best_at_your_books"]["captured_at"] == at(0)
    assert ("summit", at(0)) in rows

    # The keep horizon passes summit's row (T0) but not the capture it belongs to (720 s).
    env.provider.current = T0 + timedelta(days=10, seconds=400)
    report = prune_archive(env.engine, env.provider, env.settings, force=True)
    assert report is not None and report.status == "ok"
    assert read() == before
    assert orphan_rows(env) == 0

    # Once the game's last capture is past the horizon, everything of it goes together.
    env.provider.current = T0 + timedelta(days=10, seconds=800)
    report = prune_archive(env.engine, env.provider, env.settings, force=True)
    assert report is not None and report.status == "ok"
    odds, leg, rows = read()
    assert rows == []
    assert captured(env, ArchivedEvent, PREGAME) == []
    assert odds["coverage"]["status"] == "archive_pruned"
    assert odds["quotes"] == [] and odds["odds"] is None
    assert (leg["status"], leg["reason"]) == ("cannot_price", "archive_pruned")
    assert leg["best_overall"] is None and leg["best_at_your_books"] is None
    assert orphan_rows(env) == 0


class SteadyPropsProvider(OneGameProvider):
    """The one player is offered on PREGAME with the offers fixed as they were at T0,
    except that the first offer's line moves by ``bump``."""

    def __init__(self) -> None:
        super().__init__()
        self.fixed = [o for o in super().get_prop_offers(self.player_id) if o.event_id == PREGAME]
        self.bump = 0.0

    def get_prop_offers(self, player_id: str, market: str | None = None) -> list[PropOffer]:
        if player_id != self.player_id:
            return super().get_prop_offers(player_id, market)
        offers = [
            o.model_copy(update={"line": (o.line or 0.0) + self.bump}) if i == 0 else o
            for i, o in enumerate(self.fixed)
        ]
        return [o for o in offers if market is None or o.market == market]


def test_the_keep_horizon_never_leaves_part_of_a_games_props_readable(
    archive_env: ArchiveEnv,
) -> None:
    """Regression (review round 3), props. One offer moves at the second capture; the
    others are stored once, at T0. When the keep horizon falls between T0 and the later
    rows, the game's prop rows all stay (they leave with the game), and the read never
    answers ``captured`` with only part of the game's offers."""
    env = archive_env
    env.settings = env.settings.model_copy(update={"snapshot_keep_days": 10})
    p = SteadyPropsProvider()
    env.provider = p
    keys = len(p.fixed)
    assert keys > 1
    env.capture(at(0))
    p.bump = 0.5
    env.capture(at(360))
    env.capture(at(720))
    where = (ArchivedProp.player_id == p.player_id, ArchivedProp.event_id == PREGAME)

    def stored() -> list[datetime]:
        with env.session_factory() as db:
            return sorted(db.scalars(select(ArchivedProp.captured_at).where(*where)))

    def read() -> Any:
        with env.session_factory() as db:
            return archived_props(db, p, env.settings, p.player_id, None, at(400))

    assert stored() == [at(0)] * keys + [at(360)]
    full = read()
    assert full.coverage.status == "captured" and len(full.offers) == keys

    p.current = T0 + timedelta(days=8)
    report = prune_archive(env.engine, p, env.settings)
    assert report is not None and report.status == "ok"
    # The closing offers: each offer's latest row at or before the closing capture.
    assert stored() == [at(0)] * (keys - 1) + [at(360)]
    assert read().model_dump() == full.model_dump()

    # The keep horizon passes the T0 rows but not the game's last capture (720 s).
    p.current = T0 + timedelta(days=10, seconds=200)
    report = prune_archive(env.engine, p, env.settings, force=True)
    assert report is not None and report.status == "ok"
    assert stored() == [at(0)] * (keys - 1) + [at(360)]
    after = read()
    if after.coverage.status == "captured":
        assert after.model_dump() == full.model_dump()
    else:
        assert after.coverage.status == "archive_pruned" and after.offers == []
    assert orphan_rows(env) == 0

    # Past the game's last capture: its prop rows go with its event rows.
    p.current = T0 + timedelta(days=10, seconds=800)
    report = prune_archive(env.engine, p, env.settings, force=True)
    assert report is not None and report.status == "ok"
    assert stored() == [] and captured(env, ArchivedEvent, PREGAME) == []
    after = read()
    assert after.coverage.status == "archive_pruned" and after.offers == []
    assert orphan_rows(env) == 0


# ----------------------------------------------- the pruned-props read, edge by edge
def _finished_game_with_one_moved_offer(env: ArchiveEnv) -> tuple[SteadyPropsProvider, int]:
    """Captures at 0, 360, 720 and 1,080 s; one offer moves at 720 s; the game is final by
    1,440 s, when its offers are tombstoned. So the closing capture is at 1,080 s and the
    first props capture after it at 1,440 s."""
    p = SteadyPropsProvider()
    env.provider = p
    env.capture(at(0))
    env.capture(at(360))
    p.bump = 0.5
    env.capture(at(720))
    env.capture(at(1080))
    p.finish(PREGAME, 3, 2)
    env.capture(at(1440))
    return p, len(p.fixed)


def _props_of_the_game(env: ArchiveEnv, p: SteadyPropsProvider, moment: datetime) -> Any:
    with env.session_factory() as db:
        read = archived_props(db, p, env.settings, p.player_id, None, moment)
    return [o.model_dump() for o in read.offers if o.event_id == PREGAME], read.pruned_event_ids


def test_an_offer_that_moved_before_the_closing_capture_withholds_the_game_for_earlier_times(
    archive_env: ArchiveEnv,
) -> None:
    """After the prune each offer keeps its latest row at or before the closing capture.
    For the offer that moved at 720 s that row is later than a read at 400 s, so the
    game's offers at 400 s can no longer be read back whole: they are left out and the
    game is named, never served without the moved offer. A read at 800 s, after the
    move, is still exact."""
    env = archive_env
    p, keys = _finished_game_with_one_moved_offer(env)
    before = {moment: _props_of_the_game(env, p, moment) for moment in (at(400), at(800))}
    assert [len(offers) for offers, _ in before.values()] == [keys, keys]
    assert before[at(400)][0] != before[at(800)][0]
    p.current = T0 + timedelta(days=8)
    report = prune_archive(env.engine, p, env.settings)
    assert report is not None and report.status == "ok"
    assert _props_of_the_game(env, p, at(400)) == ([], [PREGAME])
    assert _props_of_the_game(env, p, at(800)) == (before[at(800)][0], [])


def test_the_pruned_props_read_at_the_first_props_capture_after_the_closing_one(
    archive_env: ArchiveEnv,
) -> None:
    """The kept closing offers are the answer up to, but not at, the first props capture
    after the closing capture: at that capture (1,440 s) the offers were withdrawn."""
    env = archive_env
    p, keys = _finished_game_with_one_moved_offer(env)
    us = timedelta(microseconds=1)
    before = {moment: _props_of_the_game(env, p, moment) for moment in (at(1440) - us, at(1440))}
    assert len(before[at(1440) - us][0]) == keys and before[at(1440)] == ([], [])
    p.current = T0 + timedelta(days=8)
    report = prune_archive(env.engine, p, env.settings)
    assert report is not None and report.status == "ok"
    assert _props_of_the_game(env, p, at(1440) - us) == before[at(1440) - us]
    assert _props_of_the_game(env, p, at(1440)) == ([], [PREGAME])


class MovedGameProvider(SteadyPropsProvider):
    """PREGAME's start time can be moved; while moved it is upcoming until finished."""

    def __init__(self) -> None:
        self.moved_to: datetime | None = None
        super().__init__()

    def _apply(self, event: Event | None) -> Event | None:
        event = super()._apply(event)
        if event is None or event.id != PREGAME or self.moved_to is None:
            return event
        if event.status == "final" and PREGAME in self._finished:
            return event
        return event.model_copy(
            update={
                "start_time": self.moved_to,
                "status": "upcoming",
                "score": None,
                "period_text": None,
                "score_updated_at": None,
            }
        )


def test_a_game_whose_start_moved_after_it_entered_scope_is_still_named_as_pruned(
    archive_env: ArchiveEnv,
) -> None:
    """Regression (review round 3, a remark): the game enters scope with one start time,
    is moved 50 hours on (out of scope: its offers are tombstoned), comes back into scope
    and is played. After the prune only its first, closing and last captures remain, and
    the closing ones carry the new start time. A read in its first stay must still say
    that the game's offers can no longer be read back, not drop the game silently: the
    kept first capture is the evidence that it was in scope then."""
    env = archive_env
    p = MovedGameProvider()
    env.provider = p
    keys = len(p.fixed)
    env.capture(at(0))
    env.capture(at(360))
    p.moved_to = T0 + timedelta(hours=50)
    env.capture(at(720))  # out of scope: the offers are tombstoned
    back = T0 + timedelta(hours=15)
    env.capture(back)  # within 36 hours of the new start: in scope again
    env.capture(back + timedelta(seconds=360))
    p.finish(PREGAME, 3, 2)
    env.capture(back + timedelta(seconds=720))
    assert captured(env, ArchivedEvent, PREGAME) == [
        at(0),
        at(360),
        back,
        back + timedelta(seconds=360),
    ]
    before = _props_of_the_game(env, p, at(400))
    assert len(before[0]) == keys and before[1] == []

    p.current = back + timedelta(days=8)
    report = prune_archive(env.engine, p, env.settings)
    assert report is not None and report.status == "ok"
    assert captured(env, ArchivedEvent, PREGAME) == [at(0), back + timedelta(seconds=360)]
    assert _props_of_the_game(env, p, at(400)) == ([], [PREGAME])
    # The odds read knows the same from the kept first and last captures.
    with env.session_factory() as db:
        name = p.name
        assert coverage_at(db, name, PREGAME, at(100), env.settings).status == "captured"
        assert coverage_at(db, name, PREGAME, at(400), env.settings).status == "archive_pruned"


def test_a_pruned_game_that_comes_back_into_scope_is_not_read_as_whole(
    archive_env: ArchiveEnv,
) -> None:
    """Found by the reference model (tests/test_archive_model.py) in round 4. A game is
    captured, moved three days on (out of scope), pruned, and then comes back into scope:
    its newest rows are fresh again, but its first stay still holds only the kept
    captures. A read in that first stay must answer as for any pruned game: the pruned
    capture is ``archive_pruned``, and the closing offers are not shown as open after
    they were withdrawn. (Retention is one day here: the synthetic schedule lists a game
    for three days after its date.)"""
    env = archive_env
    env.settings = env.settings.model_copy(update={"snapshot_retention_days": 1})
    p = MovedGameProvider()
    env.provider = p
    for offset in (0, 360, 720):
        env.capture(at(offset))
    p.moved_to = T0 + timedelta(days=3)
    env.capture(at(1080))  # out of scope: its offers are tombstoned
    before = _props_of_the_game(env, p, at(1100))
    assert before == ([], [])

    p.current = T0 + timedelta(days=1, hours=2)
    report = prune_archive(env.engine, p, env.settings)
    assert report is not None and report.status == "ok"
    assert captured(env, ArchivedEvent, PREGAME) == [at(0), at(720)]

    back = T0 + timedelta(days=2)  # within 36 hours of the new start
    env.capture(back)
    env.capture(back + timedelta(seconds=360))
    assert captured(env, ArchivedEvent, PREGAME)[-1] == back + timedelta(seconds=360)
    with env.session_factory() as db:
        name = p.name
        statuses = {
            offset: coverage_at(db, name, PREGAME, at(offset), env.settings).status
            for offset in (100, 400, 800)
        }
    assert statuses == {100: "captured", 400: "archive_pruned", 800: "captured"}
    # After the tombstones of the first stay: none of its offers, and the game is named.
    assert _props_of_the_game(env, p, at(1100)) == ([], [PREGAME])
    # In the second stay the game reads whole again.
    again = _props_of_the_game(env, p, back + timedelta(seconds=400))
    assert len(again[0]) == len(p.fixed) and again[1] == []


# ------------------------------------------- a prune that is cut short, or races a read
GAMES = (PREGAME, PREGAME_2, OTHER_PREGAME, LIVE)
REFUSALS = {"not_captured", "archive_gap", "archive_pruned"}


class FourGamesProvider(ControlledProvider):
    """The four games the hand-written quotes are for, and two players of PREGAME's home
    team: a prune here is twelve deletes and one more for the capture runs, so it can be
    cut after every one of them in turn."""

    def __init__(self) -> None:
        super().__init__()
        event = self.get_event(PREGAME)
        assert event is not None
        home = ControlledProvider.list_players(self, team_id=event.home_team_id)
        self.player_ids = [player.id for player in home[:2]]

    def list_events(
        self, league: str | None = None, status: str | None = None, on_date: date | None = None
    ) -> list[Event]:
        return [e for e in super().list_events(league, status, on_date) if e.id in GAMES]

    def list_players(
        self, league: str | None = None, team_id: str | None = None, query: str | None = None
    ) -> list[Player]:
        players = super().list_players(league=league, team_id=team_id, query=query)
        return [player for player in players if player.id in self.player_ids]


class WorkerKilled(BaseException):
    """The worker is killed in the middle of a prune (a deploy replaces its container):
    no handler runs, nothing more is recorded, open work is rolled back."""


class ConnectionDropped(ConnectionError):
    """The prune's connection drops: an error the pass catches and records as failed."""


#: Times asked about: inside each capture's coverage, in the gap before the last one
#: (720 s to 1,800 s is 1,080 s), and after PREGAME left scope at 2,160 s.
WATCHED_TIMES = (10, 400, 730, 1600, 1810, 2200)
LATE_BET_LEGS = [{"event_id": PREGAME, "market": "moneyline", "outcome_key": "away"}]


def _five_captures(env: ArchiveEnv) -> FourGamesProvider:
    """Captures at T0 + 0, 360, 720 and 1,800 s with the hand-written quotes, then PREGAME
    is final and a capture at 2,160 s tombstones its prop offers."""
    p = FourGamesProvider()
    env.provider = p
    capture_schedule(env)
    p.finish(PREGAME, 3, 2)
    report = env.capture(at(2160))
    assert report.props is not None and report.props.status == "ok"
    return p


def _watched(env: ArchiveEnv, bet_ids: list[str]) -> dict[tuple[Any, ...], Any]:
    """Every answer a prune could change: the odds of each game around each capture, the
    two players' props, and the placement prices of the given bets."""
    p = env.provider
    assert isinstance(p, FourGamesProvider)
    found: dict[tuple[Any, ...], Any] = {}
    with env.session_factory() as db:
        for event_id in GAMES:
            for market in ("moneyline", "spread") if event_id == PREGAME else ("moneyline",):
                for seconds in WATCHED_TIMES:
                    odds = archived_odds(db, p, env.settings, event_id, market, at(seconds))
                    found[("odds", event_id, market, seconds)] = odds.model_dump(mode="json")
        for player_id in p.player_ids:
            for seconds in WATCHED_TIMES:
                props = archived_props(db, p, env.settings, player_id, None, at(seconds))
                found[("props", player_id, seconds)] = props.model_dump(mode="json")
        for bet_id in bet_ids:
            bet = db.get(Bet, bet_id)
            assert bet is not None
            (leg,) = placement_prices(db, p, env.settings, bet, USER_BOOKS)
            answer = leg.model_dump(mode="json")
            answer.pop("leg_id")
            found[("bet", bet.placed_at)] = answer
    return found


def _agrees_with(truth: dict[tuple[Any, ...], Any], found: dict[tuple[Any, ...], Any]) -> None:
    """Safety: an answer of ``captured`` or ``priced`` is exactly the one given before any
    prune. Anything else is a refusal with a named reason and no quotes: the reason the
    truth gave, or ``archive_pruned``."""
    for key, answer in found.items():
        true = truth[key]
        if key[0] == "odds":
            status = answer["coverage"]["status"]
            if status == "captured":
                assert answer == true, key
            else:
                assert answer["quotes"] == [] and answer["odds"] is None, key
                assert status in {true["coverage"]["status"], "archive_pruned"}, (key, status)
        elif key[0] == "props":
            status = answer["coverage"]["status"]
            if status != "captured":
                assert status in REFUSALS and answer["offers"] == [], key
                assert status in {true["coverage"]["status"], "archive_pruned"}, (key, status)
                continue
            assert true["coverage"] == answer["coverage"], key
            named = set(answer["pruned_event_ids"])
            games = {o["event_id"] for o in answer["offers"] + true["offers"]}
            assert not named & {o["event_id"] for o in answer["offers"]}, key
            for event_id in games - named:
                mine = [o for o in answer["offers"] if o["event_id"] == event_id]
                theirs = [o for o in true["offers"] if o["event_id"] == event_id]
                assert mine == theirs, (key, event_id)
        else:
            if answer["status"] == "priced" or answer["best_overall"] is not None:
                assert answer == true, key
            else:
                assert answer["best_at_your_books"] is None, key
                assert answer["reason"] in {true["reason"], "archive_pruned"}, (key, answer)


def _prune_cut_after(
    env: ArchiveEnv, monkeypatch: pytest.MonkeyPatch, deletes: int, *, kill: bool
) -> str:
    """One forced prune that stops at its delete number ``deletes`` (counted from 0), as a
    dropped connection or as a killed worker. ``"cut"`` or, when the prune had fewer
    deletes than that and ran to its end, its status."""
    done = 0
    real = prune_module._delete_ids

    def delete_or_stop(session: Any, model: Any, ids: Any) -> int:
        nonlocal done
        if done == deletes:
            raise WorkerKilled() if kill else ConnectionDropped("connection lost")
        done += 1
        return real(session, model, ids)

    with monkeypatch.context() as patch:
        patch.setattr(prune_module, "_delete_ids", delete_or_stop)
        try:
            summary = prune_archive(env.engine, env.provider, env.settings, force=True)
        except WorkerKilled:
            return "cut"
    assert summary is not None
    if summary.status == "failed":
        assert summary.detail == {"error": "ConnectionDropped"}
        return "cut"
    return summary.status


def _prune_runs(env: ArchiveEnv) -> list[str]:
    with env.session_factory() as db:
        return list(
            db.scalars(
                select(SnapshotRun.status)
                .where(SnapshotRun.kind == "prune")
                .order_by(SnapshotRun.id)
            )
        )


def test_a_prune_cut_short_after_any_delete_never_changes_an_answer(
    archive_env: ArchiveEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression (review round 4, blocking). The prune deleted a game's odds rows, its
    prop rows and its event rows in three commits, and recorded its cutoffs only at the
    end. Cut between them (a deploy replaces the worker, a connection drops), a capture
    still had its event row, the coverage record, without its quotes: the odds read
    answered ``captured`` and a bet was ``priced`` from an older capture's rows, for good
    once a bet recorded meanwhile made the next prune keep that capture. And a prune cut
    after it had reduced a game left the reads not knowing: the game's closing prop
    offers were served as open.

    Here the prune is cut after every one of its deletes in turn, alternately as an error
    the pass records and as a killed worker, with a late bet recorded after every cut and
    then another prune. After every step no odds, props or placement answer is
    ``captured`` or ``priced`` with anything but what the archive answered before any
    prune. Then the same at the keep horizon."""
    env = archive_env
    env.settings = env.settings.model_copy(update={"snapshot_keep_days": 10})
    p = _five_captures(env)
    with env.session_factory() as db:
        late_user = make_user(db, "late@example.test")
        db.commit()
        late_user_id = late_user.id
        # The true answer for a bet placed at 730 s, from a bet that is never stored.
        probe = make_bet(db, late_user, at(730), LATE_BET_LEGS)
        (leg,) = placement_prices(db, p, env.settings, probe, USER_BOOKS)
        true_leg = leg.model_dump(mode="json")
        true_leg.pop("leg_id")
        db.rollback()
    truth = _watched(env, [])
    truth[("bet", at(730))] = true_leg
    assert true_leg["status"] == "priced" and true_leg["coverage"]["captured_at"].startswith(
        "2026-03-14T19:42"
    )
    assert truth[("odds", PREGAME, "moneyline", 730)]["coverage"]["status"] == "captured"
    for player_id in p.player_ids:
        closing = truth[("props", player_id, 1810)]["offers"]
        assert [o for o in closing if o["event_id"] == PREGAME]
        assert truth[("props", player_id, 2200)]["pruned_event_ids"] == []
        assert not [
            o for o in truth[("props", player_id, 2200)]["offers"] if o["event_id"] == PREGAME
        ]

    def rows_of(event_id: str) -> tuple[int, int, int]:
        with env.session_factory() as db:
            return tuple(  # type: ignore[return-value]
                db.scalar(select(func.count()).select_from(m).where(m.event_id == event_id))
                for m in (ArchivedEvent, ArchivedOdds, ArchivedProp)
            )

    late_bets: list[str] = []
    earlier = len(_prune_runs(env))  # the captures' own passes pruned, with nothing to do
    states = {event_id: [rows_of(event_id)] for event_id in GAMES}
    p.current = T0 + timedelta(days=8)
    cuts = 0
    while True:
        outcome = _prune_cut_after(env, monkeypatch, cuts, kill=cuts % 2 == 1)
        for event_id in GAMES:
            if rows_of(event_id) != states[event_id][-1]:
                states[event_id].append(rows_of(event_id))
        if outcome != "cut":
            break
        cuts += 1
        _agrees_with(truth, _watched(env, late_bets))
        # A bet recorded late (an import), before the next prune finishes the work.
        with env.session_factory() as db:
            user = db.get(User, late_user_id)
            assert user is not None
            late_bets.append(make_bet(db, user, at(730), LATE_BET_LEGS).id)
            db.commit()
        _agrees_with(truth, _watched(env, late_bets))
        p.current += timedelta(seconds=120)
    assert outcome == "ok"
    # Four games of three deletes each, and one for the capture runs.
    assert cuts == 3 * len(GAMES) + 1
    # A game went from whole to reduced in one step: wherever the prune was cut, no game
    # was ever seen with some of its tables reduced and others not.
    for event_id, seen in states.items():
        assert len(seen) == 2, (event_id, seen)
        before, after = seen
        assert after[0] < before[0] and after[1] < before[1] and after[2] <= before[2], seen
    runs = _prune_runs(env)[earlier:]
    assert runs.count("started") == cuts + 1 and runs.count("ok") == 1
    assert runs.count("failed") == (cuts + 1) // 2  # a killed worker records nothing
    after = _watched(env, late_bets)
    _agrees_with(truth, after)
    # The work is done, and what the prune keeps is still served. The first late bet was
    # recorded while its capture (720 s) was still whole, so that capture is its anchor.
    assert captured(env, ArchivedEvent, PREGAME) == [at(0), at(720), at(1800)]
    assert captured(env, ArchivedEvent, OTHER_PREGAME) == [at(0), at(2160)]
    assert after[("bet", at(730))] == true_leg
    assert after[("odds", PREGAME, "moneyline", 10)] == truth[("odds", PREGAME, "moneyline", 10)]
    assert after[("odds", PREGAME, "moneyline", 400)]["coverage"]["status"] == "archive_pruned"
    for player_id in p.player_ids:
        # The closing offers are the answer until the tombstones; after them none is
        # shown and the game is named.
        assert after[("props", player_id, 1810)] == truth[("props", player_id, 1810)]
        assert after[("props", player_id, 2200)]["pruned_event_ids"] == [PREGAME]
    assert orphan_rows(env) == 0

    # The keep horizon (10 days here), past every game's last capture: each game's rows
    # go together, and a cut inside a game, between two games or before the capture runs
    # go leaves no answer from before the horizon. A game that has gone is not looked at
    # again, so the next cut is counted from the first game still there.
    def events_held() -> int:
        with env.session_factory() as db:
            return int(db.scalar(select(func.count()).select_from(ArchivedEvent)) or 0)

    p.current = T0 + timedelta(days=10, seconds=2500)
    cuts, position, held = 0, 0, events_held()
    while True:
        outcome = _prune_cut_after(env, monkeypatch, position, kill=cuts % 2 == 0)
        if outcome != "cut":
            break
        cuts += 1
        position = 1 if events_held() < held else position + 1
        held = events_held()
        found = _watched(env, late_bets)
        _agrees_with(truth, found)
        assert {
            answer["coverage"]["status"] for key, answer in found.items() if key[0] != "bet"
        } == {"archive_pruned"}
        assert found[("bet", at(730))]["reason"] == "archive_pruned"
        p.current += timedelta(seconds=120)
    # Before each of a game's three deletes, for four games, and before the capture runs go.
    assert outcome == "ok" and cuts == 3 * len(GAMES) + 1
    for model in (ArchivedEvent, ArchivedOdds, ArchivedProp):
        with env.session_factory() as db:
            assert db.scalar(select(func.count()).select_from(model)) == 0
    assert orphan_rows(env) == 0


@pytest.mark.parametrize("started", ["inside the read", "before the read"])
@pytest.mark.parametrize("read", ["odds", "bet", "props"])
def test_a_prune_that_lands_inside_a_read_does_not_change_its_answer(
    archive_env: ArchiveEnv, monkeypatch: pytest.MonkeyPatch, read: str, started: str
) -> None:
    """A read is several statements, and on PostgreSQL each sees what was committed when
    it began. Here a prune reduces the game after the read has found the capture that
    covers T and before it reads that capture's rows: a whole prune that starts and ends
    in that moment, or one that had started (and said how far it would go) before the
    read began and reaches the game then.

    - Odds at 730 s, and the placement prices of a bet placed then: the covering capture
      (720 s) is one the prune does not keep, so the quotes read afterwards are the
      first capture's. The read notices (a prune started; the capture is no longer held)
      and is made again: ``archive_pruned``, never ``captured`` or ``priced`` with the
      opening quotes.
    - Props at 2,200 s, after PREGAME's offers were withdrawn: the prune removes the
      tombstones before the rows are read, so the kept closing offers look open, and the
      read began when no prune had ever run. Made again, it names the game as pruned."""
    env = archive_env
    p = _five_captures(env)
    player_id = p.player_ids[0]
    with env.session_factory() as db:
        before = archived_odds(db, p, env.settings, PREGAME, "moneyline", at(730))
        props_before = archived_props(db, p, env.settings, player_id, None, at(2200))
        # A bet that is never stored, so no prune keeps its capture.
        bet = make_bet(db, make_user(db), at(730), LATE_BET_LEGS)
        (leg_before,) = placement_prices(db, p, env.settings, bet, USER_BOOKS)
        db.rollback()
    assert before.coverage.status == "captured" and before.coverage.captured_at == at(720)
    assert leg_before.status == "priced"
    assert props_before.coverage.status == "captured" and props_before.pruned_event_ids == []
    p.current = T0 + timedelta(days=8)
    real_odds_rows = view_module.latest_odds_rows
    real_prop_rows = view_module.latest_prop_rows
    pruned: list[str] = []

    if read == "props" and started == "inside the read":
        # As in the archive's first hour: no prune has run yet. (The captures' own passes
        # ran one each, with nothing to do; their records are removed here.) Otherwise the
        # props read, which looks at the prune records after its rows, needs no second
        # reading for this.
        with env.session_factory() as db:
            db.execute(delete(SnapshotRun).where(SnapshotRun.kind == "prune"))
            db.commit()
    plan = None
    if started == "before the read":
        # What ``prune_pass`` does first: the cutoffs, recorded and committed.
        with env.session_factory() as db:
            plan = prune_module.plan_prune(db, env.settings, p.current)
            begun = new_run(p, env.settings, "prune", p.current, status="started")
            begun.prune_cutoff, begun.keep_cutoff = plan.cutoff, plan.keep_cutoff
            db.add(begun)
            db.commit()

    def prune_first() -> None:
        if pruned:
            return
        if plan is None:
            summary = prune_archive(env.engine, p, env.settings, force=True)
            assert summary is not None
            pruned.append(summary.status)
        else:
            with env.session_factory() as db:
                assert prune_module.prune_rows(db, env.settings, plan).deleted > 0
            pruned.append("running")

    def odds_rows_after_a_prune(*args: Any) -> Any:
        prune_first()
        return real_odds_rows(*args)

    def prop_rows_after_a_prune(*args: Any) -> Any:
        prune_first()
        return real_prop_rows(*args)

    monkeypatch.setattr(view_module, "latest_odds_rows", odds_rows_after_a_prune)
    monkeypatch.setattr(service_module, "latest_odds_rows", odds_rows_after_a_prune)
    monkeypatch.setattr(view_module, "latest_prop_rows", prop_rows_after_a_prune)
    with env.session_factory() as db:
        if read == "odds":
            odds = archived_odds(db, p, env.settings, PREGAME, "moneyline", at(730))
            assert odds.coverage.status == "archive_pruned"
            assert odds.quotes == [] and odds.odds is None
        elif read == "bet":
            (leg,) = placement_prices(db, p, env.settings, bet, USER_BOOKS)
            assert (leg.status, leg.reason) == ("cannot_price", "archive_pruned")
            assert leg.best_overall is None and leg.best_at_your_books is None
        else:
            props = archived_props(db, p, env.settings, player_id, None, at(2200))
            assert props.coverage.status == "captured"
            assert [o for o in props.offers if o.event_id == PREGAME] == []
            assert props.pruned_event_ids == [PREGAME]
    assert pruned == (["ok"] if plan is None else ["running"])
    assert captured(env, ArchivedEvent, PREGAME) == [at(0), at(1800)]


def test_a_read_that_a_prune_disturbs_every_time_gives_up(
    archive_env: ArchiveEnv, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read is made again at most ``READ_ATTEMPTS`` times; after that it refuses to
    answer (the routes turn this into 503 ``archive_busy``). One prune can disturb a read
    three times at most, so this is not expected in operation."""
    env = archive_env
    p = _five_captures(env)
    readings = iter(range(1000))
    monkeypatch.setattr(view_module, "prune_marker", lambda session: next(readings))
    with env.session_factory() as db:
        with pytest.raises(ArchiveBusy):
            archived_odds(db, p, env.settings, PREGAME, "moneyline", at(10))
        with pytest.raises(ArchiveBusy):
            archived_props(db, p, env.settings, p.player_ids[0], None, at(10))
        bet = make_bet(db, make_user(db), at(730), LATE_BET_LEGS)
        with pytest.raises(ArchiveBusy):
            placement_prices(db, p, env.settings, bet, USER_BOOKS)
        db.rollback()
    # Each was made the full number of times, with two readings of the marker each.
    assert next(readings) == 3 * 2 * view_module.READ_ATTEMPTS


def test_status_rows_leave_at_the_keep_horizon(archive_env: ArchiveEnv) -> None:
    """Each status record goes by its own age at the keep horizon (10 days here): the one
    from T0 is gone eleven days on, the one from day 3 stays, the status capture run
    nothing refers to any more goes too, and the read says from when records are kept."""
    env = archive_env
    env.settings = env.settings.model_copy(update={"snapshot_keep_days": 10})
    env.capture(T0)
    for days, status in ((0, "questionable"), (3, "out")):
        env.provider.current = T0 + timedelta(days=days)
        with env.session_factory() as db:
            run = capture_status(
                db,
                env.provider,
                env.settings,
                [
                    StatusRecord(
                        provider="synthetic",
                        provider_id=f"injury:day{days}",
                        fetched_at=env.provider.current,
                        event_id=PREGAME,
                        player_id=f"plr_day{days}",
                        kind="injury",
                        status=status,  # type: ignore[arg-type]
                        source="Fictional Desk",
                    )
                ],
            )
            assert run is not None and run.status == "ok"
    env.provider.current = T0 + timedelta(days=11)
    summary = prune_archive(env.engine, env.provider, env.settings, force=True)
    assert summary is not None and summary.status == "ok"
    with env.session_factory() as db:
        assert list(db.scalars(select(ArchivedStatus.captured_at))) == [T0 + timedelta(days=3)]
        status_runs = list(
            db.scalars(select(SnapshotRun.captured_at).where(SnapshotRun.kind == "status"))
        )
        answer = archived_status(db, env.provider, env.settings, PREGAME, T0 + timedelta(days=5))
        earlier = archived_status(db, env.provider, env.settings, PREGAME, T0 + timedelta(hours=1))
    assert status_runs == [T0 + timedelta(days=3)]
    assert [entry.player_id for entry in answer.entries] == ["plr_day3"]
    assert answer.coverage.status == "captured"
    assert answer.coverage.kept_from == T0 + timedelta(days=1)
    assert earlier.coverage.status == "archive_pruned" and earlier.entries == []
    assert orphan_rows(env) == 0


def test_the_props_read_refuses_where_its_look_back_reaches_past_the_keep_horizon(
    archive_env: ArchiveEnv,
) -> None:
    """A time just after the keep horizon is still answered from a props capture before
    it, when the game was in scope; but the horizon has taken the game's rows. The read
    must say so (``archive_pruned``), not answer ``captured`` with the game's offers
    silently missing: the check covers the whole look-back, not only T itself."""
    env = archive_env
    env.settings = env.settings.model_copy(update={"snapshot_keep_days": 10})
    p = SteadyPropsProvider()
    env.provider = p
    env.capture(at(0))
    env.capture(at(360))
    with env.session_factory() as db:
        before = archived_props(db, p, env.settings, p.player_id, None, at(500))
    assert before.coverage.status == "captured" and len(before.offers) == len(p.fixed)
    # The horizon (now less 10 days) falls at 400 s: after the game's last capture, so
    # its rows go, and before the time asked about.
    p.current = T0 + timedelta(days=10, seconds=400)
    summary = prune_archive(env.engine, p, env.settings, force=True)
    assert summary is not None and summary.status == "ok"
    assert captured(env, ArchivedProp, PREGAME) == []
    with env.session_factory() as db:
        after = archived_props(db, p, env.settings, p.player_id, None, at(500))
    assert after.coverage.status == "archive_pruned"
    assert after.offers == [] and after.pruned_event_ids == []
