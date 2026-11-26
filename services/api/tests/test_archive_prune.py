"""The retention prune: what survives the full-resolution window, how many captures bets
can keep, how coverage reads after it, and what goes at the keep horizon."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select

from oddvex_api.archive.capture import capture_pass
from oddvex_api.archive.placement import placement_prices
from oddvex_api.archive.prune import MAX_ANCHORS_PER_EVENT, prune_archive
from oddvex_api.archive.service import archived_odds, archived_props
from oddvex_api.archive.view import coverage_at
from oddvex_api.db import (
    ARCHIVE_MODELS,
    ArchivedEvent,
    ArchivedOdds,
    ArchivedProp,
    Bet,
    SnapshotRun,
)
from oddvex_api.providers import Event, PropOffer

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


class SteadyPropsProvider(ControlledProvider):
    """One player is offered on PREGAME with the offers fixed as they were at T0, except
    that the first offer's line moves by ``bump``."""

    def __init__(self) -> None:
        super().__init__()
        event = self.get_event(PREGAME)
        assert event is not None
        self.player_id = self.list_players(team_id=event.home_team_id)[0].id
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
