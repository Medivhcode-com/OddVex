"""Closing line value (CLV)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .novig import no_vig
from .odds import Number, implied_probability, validate_decimal_odds


@dataclass(frozen=True, slots=True)
class CLVResult:
    bet_decimal: Decimal
    closing_decimal: Decimal
    #: (bet_decimal / closing_decimal - 1) * 100. Positive = better than the close.
    clv_percent: float
    beat_close: bool
    #: Fair closing probability of the selection (needs the closing opposite price).
    closing_no_vig_probability: float | None = None
    #: closing_no_vig_probability - implied probability of the price taken.
    no_vig_probability_delta: float | None = None
    #: EV% of the price taken if the no-vig close were the true probability.
    ev_at_close_percent: float | None = None


def closing_line_value(
    bet_decimal: Number,
    closing_decimal: Number,
    closing_opposite_decimal: Number | None = None,
) -> CLVResult:
    """Compare the price taken with the closing price of the same selection.

    When the closing price of the other side of a two-way market is supplied
    the close is de-vigged and a probability-based CLV is returned as well.
    """
    bet = validate_decimal_odds(bet_decimal)
    close = validate_decimal_odds(closing_decimal)
    clv_pct = float((bet / close - 1) * 100)
    fair: float | None = None
    delta: float | None = None
    ev_close: float | None = None
    if closing_opposite_decimal is not None:
        opposite = validate_decimal_odds(closing_opposite_decimal)
        fair = no_vig([close, opposite]).fair_probabilities[0]
        delta = fair - implied_probability(bet)
        ev_close = (fair * float(bet) - 1.0) * 100
    return CLVResult(
        bet_decimal=bet,
        closing_decimal=close,
        clv_percent=clv_pct,
        beat_close=bet > close,
        closing_no_vig_probability=fair,
        no_vig_probability_delta=delta,
        ev_at_close_percent=ev_close,
    )
