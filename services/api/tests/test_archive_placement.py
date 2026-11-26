"""P0.1 "Done when": any stored bet joins to the best price across the user's books at its
placement time.

Captures run at T0, T0+360 s, T0+720 s and T0+1800 s (a 1,080 s gap after the third, above
the 840 s limit). Every leg of every fixture bet must come back either ``priced``, with the
best price overall and at the user's books equal to a hand-worked literal, or
``cannot_price`` with a named reason. The literals follow from ``PREGAME_QUOTES`` and the
other tables in ``archive_support.py``: the latest capture at or before ``placed_at``,
staleness judged at ``placed_at`` (``oldmill`` is stale, ``kestrel`` is suspended), only
the user's books (northline, summit) in ``best_at_your_books``, and the leg's own line for
spread and total.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from oddvex_api.archive.placement import CANNOT_PRICE_REASONS, placement_prices
from oddvex_api.archive.prune import prune_archive

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
    # Only blueharbor quotes -2.5, and the user does not hold it.
    "spread_off_the_consensus_line": (
        at(400),
        [leg(PREGAME, "spread", "home", -2.5)],
        [("cannot_price", None, "none_at_your_books", ("blueharbor", 210))],
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
}
#: Created after the prune, inside the pruned window, on a game no earlier bet anchors.
AFTER_PRUNE = (
    at(100),
    [leg(OTHER_PREGAME, "moneyline", "home")],
    [("cannot_price", "archive_pruned", None, None)],
)


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
    assert answer.reason in CANNOT_PRICE_REASONS or answer.your_books_reason, name
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

        # A bet recorded after the prune, at a time whose rows are gone.
        placed_at, legs, expected = AFTER_PRUNE
        bets["after_prune"] = make_bet(db, user, placed_at, legs)
        db.commit()
        for answer, want in zip(evaluate("after_prune"), expected, strict=True):
            check(answer, want, "after_prune")
