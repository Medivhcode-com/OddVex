"""A record of graded picks at a flat stake of one unit each. Pure: no I/O, no clock.

Everything here describes picks that were already graded. None of it estimates a future
result, and a win rate from a small sample says little: see :data:`SMALL_SAMPLE`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from .errors import QuantError
from .ev import roi
from .grading import GRADE_RESULTS
from .hitrate import wilson_interval
from .odds import Number, validate_decimal_odds
from .tracker import mean, win_rate

#: Below this many graded picks a record cannot tell skill from luck.
SMALL_SAMPLE = 30

FLAT_STAKE_METHOD = (
    "Flat stake: 1 unit on every graded pick at the price recorded when the pick was "
    "posted. A win returns the decimal price minus 1, a loss returns -1 and a push "
    "returns 0. ROI is the total divided by the units staked, pushes included. Win rate "
    "is wins divided by wins plus losses, with a Wilson 95% interval."
)


def flat_stake_profit(result: str, decimal_odds: Number) -> Decimal:
    """Profit, in units, of one unit staked at ``decimal_odds`` with ``result``."""
    if result not in GRADE_RESULTS:
        raise QuantError(f"result {result!r} cannot be scored", code="invalid_result")
    price = validate_decimal_odds(decimal_odds)
    if result == "won":
        return price - 1
    if result == "lost":
        return Decimal(-1)
    return Decimal(0)


@dataclass(frozen=True, slots=True)
class PickRecord:
    #: Graded picks: wins + losses + pushes.
    picks: int
    wins: int
    losses: int
    pushes: int
    #: wins / (wins + losses); ``None`` when no pick was decided.
    win_rate: float | None
    ci_low: float | None
    ci_high: float | None
    #: Mean decimal price of the graded picks.
    average_decimal_odds: Decimal | None
    #: Units won or lost at 1 unit per graded pick.
    units_profit: Decimal
    #: ``units_profit`` / ``picks``; ``None`` without graded picks.
    flat_stake_roi: float | None
    confidence_level: float = 0.95


def pick_record(graded: Sequence[tuple[str, Number]], z: float = 1.96) -> PickRecord:
    """Summarise ``(result, decimal price)`` pairs of graded picks."""
    results = [result for result, _ in graded]
    wins = results.count("won")
    losses = results.count("lost")
    pushes = results.count("push")
    total_profit = sum((flat_stake_profit(result, price) for result, price in graded), Decimal(0))
    decided = wins + losses
    low, high = wilson_interval(wins, decided, z) if decided else (None, None)
    return PickRecord(
        picks=len(graded),
        wins=wins,
        losses=losses,
        pushes=pushes,
        win_rate=win_rate(wins, losses),
        ci_low=low,
        ci_high=high,
        average_decimal_odds=mean([validate_decimal_odds(price) for _, price in graded]),
        units_profit=total_profit,
        flat_stake_roi=roi(total_profit, len(graded)),
    )
