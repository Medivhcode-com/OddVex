"""P0.1 "Done when": any stored bet joins to the best price across the user's books at its
placement time.

Captures run at T0, T0+360 s, T0+720 s and T0+1800 s (a 1,080 s gap after the third, above
the 840 s limit). Every leg of every fixture bet must come back either ``priced``, with the
best price overall and at the user's books equal to a hand-worked literal, or
``cannot_price`` with a named reason. The literals follow from ``PREGAME_QUOTES`` and the
other tables in ``archive_support.py``: the latest capture at or before ``placed_at``,
staleness judged at ``placed_at`` (``oldmill`` is stale, ``kestrel`` is suspended), only
the user's books (northline, summit) in ``best_at_your_books``, and the leg's own line for
spread and total. After the prune, bets recorded late answer from the latest capture at or
before their ``placed_at`` or ``archive_pruned``, never from an older kept capture.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from oddvex_api.archive.placement import CANNOT_PRICE_REASONS, placement_prices
from oddvex_api.archive.prune import prune_archive
from oddvex_api.archive.service import archived_odds

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
from .fakes import moneyline

__all__ = ["archive_env"]

US = timedelta(microseconds=1)


def at(seconds: float) -> Any:
    return T0 + timedelta(seconds=seconds)


def leg(event_id: str, market: str, outcome_key: str | None, line: float | None = None) -> Any:
    return {"event_id": event_id, "market": market, "outcome_key": outcome_key, "line": line}


#: name -> (placed_at, legs, expected per leg). Expected is either
#: ("priced", (overall book, overall american), (your book, your american), captured offset)
#: or ("cannot_price", reason, your_books_reason).
CASES: dict[str, tuple[Any, list[Any], list[tuple[Any, ...]]]] = {
    # C0: home northline -120, cardinal -110, summit -125; oldmill (stale) and kestrel
    # (suspended) are higher but excluded.
    "moneyline_inside_coverage": (
        at(100),
        [leg(PREGAME, "moneyline", "home")],
        [("priced", ("cardinal", -110), ("northline", -120), 0)],
    ),
    # Exactly at a capture: that capture counts (at or before).
    "exactly_at_a_capture": (
        at(360),
        [leg(PREGAME, "moneyline", "home")],
        [("priced", ("northline", -115), ("northline", -115), 360)],
    ),
    # 1 microsecond before the capture at 360 s: the earlier capture.
    "one_microsecond_before_a_capture": (
        at(360) - US,
        [leg(PREGAME, "moneyline", "home")],
        [("priced", ("cardinal", -110), ("northline", -120), 0)],
    ),
    # C1 spread at -1.5: northline +145, cardinal +140, summit +150 (blueharbor is on -2.5).
    "spread_on_the_consensus_line": (
        at(400),
        [leg(PREGAME, "spread", "home", -1.5)],
        [("priced", ("summit", 150), ("summit", 150), 360)],
    ),
    # Only blueharbor quotes -2.5, and the user does not hold it: a named reason, with
    # the price that did exist in best_overall.
    "spread_off_the_consensus_line": (
        at(400),
        [leg(PREGAME, "spread", "home", -2.5)],
        [("cannot_price", "none_at_your_books", "none_at_your_books", ("blueharbor", 210))],
    ),
    # C2 total 5.5: northline -115, summit +100 (cardinal is on 6.0).
    "total_over": (
        at(800),
        [leg(PREGAME, "total", "over", 5.5)],
        [("priced", ("summit", 100), ("summit", 100), 720)],
    ),
    # C2 away: northline -110, cardinal -115, summit -108. MLB home: northline -160,
    # summit -150, cardinal -135.
    "two_leg_parlay": (
        at(750),
        [leg(PREGAME, "moneyline", "away"), leg(PREGAME_2, "moneyline", "home")],
        [
            ("priced", ("summit", -108), ("summit", -108), 720),
            ("priced", ("cardinal", -135), ("summit", -150), 720),
        ],
    ),
    "before_the_first_capture": (
        at(-60),
        [leg(PREGAME, "moneyline", "home")],
        [("cannot_price", "not_captured", None, None)],
    ),
    # 900 s after the capture at 720 s, with the next one at 1800 s.
    "inside_the_gap": (
        at(1620),
        [leg(PREGAME, "moneyline", "home")],
        [("cannot_price", "archive_gap", None, None)],
    ),
    # 840 s after the capture at 720 s: still covered; the quotes are 850 s old (< 900 s).
    "at_the_edge_of_the_gap": (
        at(1560),
        [leg(PREGAME, "moneyline", "home")],
        [("priced", ("cardinal", -105), ("northline", -110), 720)],
    ),
    "unstructured_prop_leg": (
        at(100),
        [
            {
                "event_id": PREGAME,
                "market": "player_points",
                "outcome_key": None,
                "line": 22.5,
                "selection": "Player points over 22.5",
            }
        ],
        [("cannot_price", "leg_not_structured", None, None)],
    ),
    # C0 away: northline +100, cardinal -105, summit +105; oldmill +130 (stale) and
    # kestrel +120 (suspended) are excluded. Placed at a book the provider does not have.
    "best_price_on_a_stale_or_suspended_book": (
        at(100),
        [leg(PREGAME, "moneyline", "away")],
        [("priced", ("summit", 105), ("summit", 105), 0)],
    ),
    # Live: the quotes of the capture at 720 s were 10 s old; placed 200 s later they are
    # 210 s old, past the 120 s live limit.
    "live_bet_long_after_its_quotes": (
        at(920),
        [leg(LIVE, "moneyline", "home")],
        [("cannot_price", "stale_at_placement", None, None)],
    ),
    # The other game: the same quotes at every capture (northline -140, summit -135). This
    # bet anchors the capture at T0 for the prune.
    "anchor_on_the_other_game": (
        at(100),
        [leg(OTHER_PREGAME, "moneyline", "home")],
        [("priced", ("summit", -135), ("summit", -135), 0)],
    ),
}
#: Recorded after the prune, on the other game. Only the capture at T0 was kept for it
#: (by the bet above, plus its last capture at 1,800 s).
AFTER_PRUNE: dict[str, tuple[Any, list[Any], list[tuple[Any, ...]]]] = {
    # The latest capture at or before 400 s is the one at 360 s, and it was pruned. The
    # kept capture at T0 must not stand in for it, even though no quote changed.
    "late_bet_after_a_pruned_capture": (
        at(400),
        [leg(OTHER_PREGAME, "moneyline", "home")],
        [("cannot_price", "archive_pruned", None, None)],
    ),
    # The latest capture at or before 200 s is the kept one at T0: priced from it, as it
    # was before the prune.
    "late_bet_on_a_kept_capture": (
        at(200),
        [leg(OTHER_PREGAME, "moneyline", "home")],
        [("priced", ("summit", -135), ("summit", -135), 0)],
    ),
}


def check(answer: Any, expected: tuple[Any, ...], name: str) -> None:
    assert answer.status in ("priced", "cannot_price"), name
    if expected[0] == "priced":
        _, overall, yours, offset = expected
        assert answer.status == "priced", (name, answer)
        assert answer.reason is None, name
        assert answer.coverage.status == "captured", name
        assert answer.coverage.captured_at == at(offset), name
        assert answer.best_overall is not None and answer.best_at_your_books is not None, name
        assert (answer.best_overall.sportsbook.key, answer.best_overall.price.american) == overall
        assert (
            answer.best_at_your_books.sportsbook.key,
            answer.best_at_your_books.price.american,
        ) == yours, name
        assert answer.best_at_your_books.sportsbook.key in USER_BOOKS, name
        # The quote used was captured at or before placement, and was not stale then.
        for best in (answer.best_overall, answer.best_at_your_books):
            assert best.captured_at == at(offset), name
            assert best.line == answer.line, name
        return
    _, reason, your_books_reason, overall = expected
    assert answer.status == "cannot_price", (name, answer)
    assert answer.reason == reason, (name, answer.reason)
    assert answer.your_books_reason == your_books_reason, name
    assert answer.reason in CANNOT_PRICE_REASONS, name
    assert answer.best_at_your_books is None, name
    if overall is None:
        assert answer.best_overall is None, name
    else:
        assert answer.best_overall is not None
        assert (answer.best_overall.sportsbook.key, answer.best_overall.price.american) == overall


def test_every_stored_bet_joins_to_the_best_price_at_your_books_at_placement_time(
    archive_env: ArchiveEnv,
) -> None:
    env = archive_env
    capture_schedule(env)
    with env.session_factory() as db:
        user = make_user(db)
        bets = {}
        for name, (placed_at, legs, _) in CASES.items():
            book = "Mystery Book" if name == "best_price_on_a_stale_or_suspended_book" else "Summit"
            bets[name] = make_bet(db, user, placed_at, legs, sportsbook=book)
        db.commit()

        def evaluate(name: str) -> list[Any]:
            bet = bets[name]
            answers = placement_prices(db, env.provider, env.settings, bet, USER_BOOKS)
            # One answer per leg, in leg order: no leg is left unanswered.
            assert [a.leg_id for a in answers] == [leg.id for leg in bet.legs], name
            return answers

        before_prune = {name: evaluate(name) for name in CASES}
        for name, (_, _, expected) in CASES.items():
            for answer, want in zip(before_prune[name], expected, strict=True):
                check(answer, want, name)

        # Eight days on, the full-resolution rows are pruned. Closing rows and the rows
        # each stored bet anchors are kept, so every stored bet still joins the same way.
        env.provider.current = T0 + timedelta(days=8)
        report = prune_archive(env.engine, env.provider, env.settings, force=True)
        assert report is not None and report.status == "ok" and report.rows_deleted > 0
        db.expire_all()
        for name in CASES:
            assert evaluate(name) == before_prune[name], name

        # Bets recorded after the prune: each answers from the latest capture at or
        # before its placed_at, or archive_pruned when that capture's rows are gone.
        for name, (placed_at, legs, _) in AFTER_PRUNE.items():
            bets[name] = make_bet(db, user, placed_at, legs, sportsbook="Summit")
        db.commit()
        for name, (_, _, expected) in AFTER_PRUNE.items():
            for answer, want in zip(evaluate(name), expected, strict=True):
                check(answer, want, name)


def test_an_in_play_bet_after_kickoff_is_not_priced_with_a_pregame_quote(
    archive_env: ArchiveEnv,
) -> None:
    """The kickoff falls between two captures. The last capture before it says
    ``upcoming``, but a bet placed after the start time is judged by the 120 s live limit,
    not the 900 s pregame one, both in placement prices and in the as-of odds."""
    env = archive_env
    p = env.provider
    event = p.get_event(PREGAME_2)
    assert event is not None
    start = event.start_time  # 20:00, T0 + 1,800 s
    quotes = [
        ("northline", "open", 10, moneyline(-160, 140)),
        ("summit", "open", 10, moneyline(-150, 130)),
    ]
    for offset in (0, 360, 720, 1080, 1440, 1700):  # the last is 100 s before the start
        p.set_odds(PREGAME_2, "moneyline", quotes)
        report = env.capture(at(offset))
        assert report.odds is not None and report.odds.status == "ok"
    with env.session_factory() as db:
        user = make_user(db)
        # 50 s before the start the quotes are 160 s old: fine before the start.
        before = make_bet(
            db, user, start - timedelta(seconds=50), [leg(PREGAME_2, "moneyline", "home")]
        )
        # 50 s and 150 s after it they are 160 s and 260 s old: past the live limit.
        after = [
            make_bet(db, user, start + timedelta(seconds=s), [leg(PREGAME_2, "moneyline", "home")])
            for s in (50, 150)
        ]
        db.commit()
        (priced,) = placement_prices(db, p, env.settings, before, USER_BOOKS)
        check(priced, ("priced", ("summit", -150), ("summit", -150), 1700), "before_kickoff")
        for bet in after:
            (answer,) = placement_prices(db, p, env.settings, bet, USER_BOOKS)
            check(answer, ("cannot_price", "stale_at_placement", None, None), "after_kickoff")
            # The coverage row is the pregame capture, kept as captured.
            assert answer.coverage is not None and answer.coverage.captured_at == at(1700)
        odds = archived_odds(
            db, p, env.settings, PREGAME_2, "moneyline", start + timedelta(seconds=150)
        )
    assert odds.odds is not None
    assert odds.odds.event.status == "upcoming"  # as captured; only the threshold changes
    assert odds.odds.stale_after_seconds == 120
    assert all(book.is_stale for book in odds.odds.books)
    assert odds.odds.best == []
