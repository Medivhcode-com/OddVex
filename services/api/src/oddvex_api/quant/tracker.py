"""Descriptive statistics for a bet history. Pure functions, no I/O.

Everything here describes results that already happened. None of it estimates a future
result.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from .errors import QuantError
from .odds import Number, decimal_to_american, to_decimal_number

#: (key, label) of each American-odds band, shortest prices first.
ODDS_BANDS: tuple[tuple[str, str], ...] = (
    ("-200_or_shorter", "-200 or shorter"),
    ("-199_to_-110", "-199 to -110"),
    ("-109_to_+100", "-109 to +100"),
    ("+101_to_+200", "+101 to +200"),
    ("longer_than_+200", "Longer than +200"),
)

#: Upper bounds (exclusive) between CLV buckets, as fractions, and each bucket's label.
CLV_BOUNDS: tuple[float, ...] = (-0.05, -0.02, 0.0, 0.02, 0.05)
CLV_BUCKETS: tuple[tuple[str, str], ...] = (
    ("below_-5", "Below -5%"),
    ("-5_to_-2", "-5% to -2%"),
    ("-2_to_0", "-2% to 0%"),
    ("0_to_2", "0% to 2%"),
    ("2_to_5", "2% to 5%"),
    ("5_or_more", "5% or more"),
)

#: Upper bounds (exclusive) between stake buckets, in currency units.
STAKE_BOUNDS: tuple[int, ...] = (10, 25, 50, 100)
STAKE_BUCKETS: tuple[tuple[str, str], ...] = (
    ("under_10", "Under $10"),
    ("10_to_25", "$10 to $24.99"),
    ("25_to_50", "$25 to $49.99"),
    ("50_to_100", "$50 to $99.99"),
    ("100_or_more", "$100 or more"),
)


def odds_band(decimal_odds: Number) -> str:
    """Key of the :data:`ODDS_BANDS` entry a price falls in, by its American price.

    The American price is the nearest whole number, with even money as +100, so a price
    is always at or below -101 or at or above +100.
    """
    american = decimal_to_american(decimal_odds)
    if american <= -200:
        index = 0
    elif american <= -110:
        index = 1
    elif american <= 100:
        index = 2
    elif american <= 200:
        index = 3
    else:
        index = 4
    return ODDS_BANDS[index][0]


def bucket_index(value: Number, upper_bounds: Sequence[Number]) -> int:
    """Index of the bucket ``value`` falls in: bucket ``i`` holds values below
    ``upper_bounds[i]`` and at or above the previous bound; the last bucket is open-ended.
    """
    number = to_decimal_number(value)
    bounds = [to_decimal_number(bound, "bound") for bound in upper_bounds]
    if any(later <= earlier for earlier, later in zip(bounds, bounds[1:], strict=False)):
        raise QuantError("bucket bounds must be strictly increasing")
    for index, bound in enumerate(bounds):
        if number < bound:
            return index
    return len(bounds)


def win_rate(wins: int, losses: int) -> float | None:
    """Wins divided by decided bets (wins + losses). ``None`` when nothing was decided."""
    if wins < 0 or losses < 0:
        raise QuantError("wins and losses cannot be negative")
    decided = wins + losses
    return wins / decided if decided else None


def mean(values: Sequence[Number]) -> Decimal | None:
    """Arithmetic mean, or ``None`` for an empty sequence."""
    if not values:
        return None
    numbers = [to_decimal_number(value) for value in values]
    return sum(numbers, Decimal(0)) / len(numbers)


@dataclass(frozen=True, slots=True)
class Streaks:
    longest_win: int
    longest_loss: int
    #: "win", "loss" or "none" (no decided bet yet).
    current_kind: str
    current_length: int


def streaks(profits: Sequence[Number]) -> Streaks:
    """Winning and losing runs over profits in settlement order, oldest first.

    A positive profit is a win and a negative one a loss. A zero profit (push, void)
    neither extends nor ends a run.
    """
    longest_win = longest_loss = run = 0
    kind = "none"
    for value in profits:
        amount = to_decimal_number(value, "profit")
        if amount == 0:
            continue
        outcome = "win" if amount > 0 else "loss"
        run = run + 1 if outcome == kind else 1
        kind = outcome
        if kind == "win":
            longest_win = max(longest_win, run)
        else:
            longest_loss = max(longest_loss, run)
    return Streaks(longest_win, longest_loss, kind, run)
