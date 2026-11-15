"""Grading a structured selection against a final score: known values and properties."""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from oddvex_api.quant import (
    GRADE_RESULTS,
    QuantError,
    grade_leg,
    is_gradeable,
    valid_outcome_keys,
)

OPPOSITE = {"won": "lost", "lost": "won", "push": "push"}


# ------------------------------------------------------------------ moneyline
@pytest.mark.parametrize(
    ("outcome", "home", "away", "expected"),
    [
        ("home", 110, 104, "won"),
        ("away", 110, 104, "lost"),
        ("home", 98, 101, "lost"),
        ("away", 98, 101, "won"),
        ("home", 0, 0, "push"),  # tie on a 2-way moneyline
        ("away", 3, 3, "push"),
    ],
)
def test_two_way_moneyline(outcome: str, home: int, away: int, expected: str) -> None:
    assert grade_leg("moneyline", outcome, None, home, away) == expected


@pytest.mark.parametrize(
    ("outcome", "home", "away", "expected"),
    [
        ("home", 2, 1, "won"),
        ("draw", 2, 1, "lost"),
        ("away", 2, 1, "lost"),
        ("home", 1, 1, "lost"),  # a tie loses for both sides when a draw price exists
        ("away", 1, 1, "lost"),
        ("draw", 1, 1, "won"),
        ("draw", 0, 0, "won"),
        ("away", 0, 3, "won"),
        ("draw", 0, 3, "lost"),
    ],
)
def test_three_way_moneyline(outcome: str, home: int, away: int, expected: str) -> None:
    assert grade_leg("moneyline", outcome, None, home, away, three_way=True) == expected


def test_moneyline_ignores_a_line() -> None:
    assert grade_leg("moneyline", "home", -3.5, 100, 99) == "won"


def test_draw_is_not_an_outcome_of_a_two_way_moneyline() -> None:
    with pytest.raises(QuantError) as error:
        grade_leg("moneyline", "draw", None, 1, 1)
    assert error.value.code == "invalid_outcome"


# --------------------------------------------------------------------- spread
@pytest.mark.parametrize(
    ("outcome", "line", "home", "away", "expected"),
    [
        # Home -3.5: home must win by 4 or more.
        ("home", -3.5, 104, 100, "won"),
        ("home", -3.5, 103, 100, "lost"),
        ("home", -3.5, 100, 103, "lost"),
        # The other side of that market is away +3.5.
        ("away", 3.5, 104, 100, "lost"),
        ("away", 3.5, 103, 100, "won"),
        ("away", 3.5, 100, 103, "won"),
        # Away favourite: away -6.5 / home +6.5.
        ("away", -6.5, 90, 97, "won"),
        ("away", -6.5, 91, 97, "lost"),
        ("home", 6.5, 91, 97, "won"),
        ("home", 6.5, 90, 97, "lost"),
        # Integer spreads push when the margin lands on the number.
        ("home", -3, 103, 100, "push"),
        ("away", 3, 103, 100, "push"),
        ("home", -3, 104, 100, "won"),
        ("away", 3, 104, 100, "lost"),
        ("home", -3, 102, 100, "lost"),
        ("away", 3, 102, 100, "won"),
        ("home", 7, 17, 24, "push"),
        ("away", -7, 17, 24, "push"),
        # Pick'em.
        ("home", 0, 21, 21, "push"),
        ("home", 0, 22, 21, "won"),
        ("away", 0, 22, 21, "lost"),
    ],
)
def test_spread_line_is_from_the_selected_side(
    outcome: str, line: float, home: int, away: int, expected: str
) -> None:
    assert grade_leg("spread", outcome, line, home, away) == expected


def test_spread_accepts_decimal_and_string_lines() -> None:
    assert grade_leg("spread", "home", Decimal("-3.50"), 104, 100) == "won"
    assert grade_leg("spread", "home", "-3.5", 103, 100) == "lost"
    assert grade_leg("spread", "home", -3, 103, 100) == "push"


# ---------------------------------------------------------------------- total
@pytest.mark.parametrize(
    ("outcome", "line", "home", "away", "expected"),
    [
        ("over", 224.5, 113, 112, "won"),
        ("under", 224.5, 113, 112, "lost"),
        ("over", 224.5, 112, 112, "lost"),
        ("under", 224.5, 112, 112, "won"),
        ("over", 44, 24, 20, "push"),  # exactly on the number
        ("under", 44, 24, 20, "push"),
        ("over", 44, 24, 21, "won"),
        ("under", 44, 24, 21, "lost"),
        ("over", 2.5, 1, 1, "lost"),
        ("under", 2.5, 1, 1, "won"),
        ("over", 0.5, 0, 0, "lost"),
        ("under", 0.5, 0, 0, "won"),
    ],
)
def test_total(outcome: str, line: float, home: int, away: int, expected: str) -> None:
    assert grade_leg("total", outcome, line, home, away) == expected


# ----------------------------------------------------------------- validation
@pytest.mark.parametrize(
    ("args", "code"),
    [
        (("player_points", "over", 22.5, 1, 1), "invalid_market"),
        (("moneyline", "over", None, 1, 1), "invalid_outcome"),
        (("spread", "draw", -1.5, 1, 1), "invalid_outcome"),
        (("spread", "over", -1.5, 1, 1), "invalid_outcome"),
        (("total", "home", 2.5, 1, 1), "invalid_outcome"),
        (("spread", "home", None, 1, 1), "invalid_line"),
        (("total", "over", None, 1, 1), "invalid_line"),
        (("total", "over", float("nan"), 1, 1), "invalid_line"),
        (("total", "over", float("inf"), 1, 1), "invalid_line"),
        (("total", "over", "abc", 1, 1), "invalid_line"),
        (("spread", "home", True, 1, 1), "invalid_line"),
        (("moneyline", "home", None, -1, 1), "invalid_score"),
        (("moneyline", "home", None, 1, -2), "invalid_score"),
        (("moneyline", "home", None, 1.5, 1), "invalid_score"),
        (("moneyline", "home", None, True, 1), "invalid_score"),
    ],
)
def test_invalid_input_raises_a_quant_error(args: tuple, code: str) -> None:
    with pytest.raises(QuantError) as error:
        grade_leg(*args)
    assert error.value.code == code


def test_valid_outcome_keys() -> None:
    assert valid_outcome_keys("moneyline") == ("home", "away")
    assert valid_outcome_keys("moneyline", three_way=True) == ("home", "away", "draw")
    assert valid_outcome_keys("spread", three_way=True) == ("home", "away")
    assert valid_outcome_keys("total") == ("over", "under")
    assert valid_outcome_keys("player_points") == ()


@pytest.mark.parametrize(
    ("market", "outcome", "line", "expected"),
    [
        ("moneyline", "home", None, True),
        ("moneyline", "draw", None, True),
        ("moneyline", "over", None, False),
        ("moneyline", None, None, False),
        ("spread", "home", -3.5, True),
        ("spread", "home", 0, True),
        ("spread", "home", None, False),
        ("spread", "draw", -3.5, False),
        ("total", "over", 44.5, True),
        ("total", "under", None, False),
        ("player_points", "over", 22.5, False),
        (None, "home", None, False),
    ],
)
def test_is_gradeable(
    market: str | None, outcome: str | None, line: float | None, expected: bool
) -> None:
    assert is_gradeable(market, outcome, line) is expected


# ----------------------------------------------------------------- properties
scores = st.integers(min_value=0, max_value=300)
half_points = st.integers(min_value=-120, max_value=120).map(lambda n: n / 2)
total_lines = st.integers(min_value=1, max_value=1200).map(lambda n: n / 2)


@given(home=scores, away=scores)
def test_two_way_moneyline_sides_are_opposite(home: int, away: int) -> None:
    result = grade_leg("moneyline", "home", None, home, away)
    assert result in GRADE_RESULTS
    assert grade_leg("moneyline", "away", None, home, away) == OPPOSITE[result]
    assert (result == "push") == (home == away)


@given(home=scores, away=scores)
def test_three_way_moneyline_has_exactly_one_winner_and_no_push(home: int, away: int) -> None:
    results = [
        grade_leg("moneyline", key, None, home, away, three_way=True)
        for key in ("home", "draw", "away")
    ]
    assert results.count("won") == 1 and results.count("lost") == 2


@given(home=scores, away=scores, line=half_points)
def test_spread_sides_are_opposite_and_swapping_teams_mirrors(
    home: int, away: int, line: float
) -> None:
    result = grade_leg("spread", "home", line, home, away)
    assert grade_leg("spread", "away", -line, home, away) == OPPOSITE[result]
    assert grade_leg("spread", "away", line, away, home) == result
    assert (result == "push") == (home + line == away)
    if line != int(line):
        assert result != "push"  # a half-point line cannot push


@given(home=scores, away=scores, line=half_points)
def test_spread_zero_line_agrees_with_two_way_moneyline(home: int, away: int, line: float) -> None:
    for side in ("home", "away"):
        assert grade_leg("spread", side, 0, home, away) == grade_leg(
            "moneyline", side, None, home, away
        )


@given(home=scores, away=scores, line=total_lines)
def test_total_sides_are_opposite_and_symmetric_in_the_teams(
    home: int, away: int, line: float
) -> None:
    over = grade_leg("total", "over", line, home, away)
    assert grade_leg("total", "under", line, home, away) == OPPOSITE[over]
    assert grade_leg("total", "over", line, away, home) == over
    assert (over == "push") == (home + away == line)
    assert (over == "won") == (home + away > line)


@given(home=scores, away=scores, line=half_points, extra=st.integers(min_value=1, max_value=50))
def test_a_better_line_or_score_never_hurts(home: int, away: int, line: float, extra: int) -> None:
    rank = {"lost": 0, "push": 1, "won": 2}
    base = rank[grade_leg("spread", "home", line, home, away)]
    assert rank[grade_leg("spread", "home", line + extra, home, away)] >= base
    assert rank[grade_leg("spread", "home", line, home + extra, away)] >= base
    total = abs(line) + 0.5
    over = rank[grade_leg("total", "over", total, home, away)]
    assert rank[grade_leg("total", "over", total, home + extra, away)] >= over
    assert rank[grade_leg("total", "under", total, home + extra, away)] <= 2 - over
