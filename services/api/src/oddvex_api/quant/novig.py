"""Removing the bookmaker margin (vig) from an n-way market."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from .errors import QuantError
from .odds import Number, implied_probability


@dataclass(frozen=True, slots=True)
class NoVigResult:
    implied_probabilities: tuple[float, ...]
    fair_probabilities: tuple[float, ...]
    #: sum(implied) - 1, e.g. 0.0476 for -110/-110.
    overround: float
    #: 1 - 1/sum(implied): the book's theoretical margin on balanced action.
    hold: float
    method: str = "multiplicative"


def no_vig(decimal_prices: Sequence[Number | Decimal]) -> NoVigResult:
    """Multiplicative (proportional) de-vig.

    Each implied probability is divided by the booksum so the fair
    probabilities sum to 1. Requires every outcome of the market (n >= 2).
    """
    if len(decimal_prices) < 2:
        raise QuantError("a market needs at least two outcomes to remove the vig", "invalid_market")
    implied = tuple(implied_probability(price) for price in decimal_prices)
    booksum = sum(implied)
    fair = tuple(p / booksum for p in implied)
    return NoVigResult(
        implied_probabilities=implied,
        fair_probabilities=fair,
        overround=booksum - 1.0,
        hold=1.0 - 1.0 / booksum,
    )
