"""Payout, profit, ROI and expected value."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from .errors import QuantError
from .odds import Number, to_decimal_number, validate_decimal_odds, validate_probability

CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    """Round a monetary amount to cents, half up.

    ``QuantError`` (``amount_out_of_range``) when the amount has more digits than decimal
    arithmetic holds (28) or is not finite.
    """
    try:
        if value.is_finite():
            return value.quantize(CENT, rounding=ROUND_HALF_UP)
    except ArithmeticError:
        pass
    raise QuantError("the amount is too large to compute", code="amount_out_of_range")


def validate_stake(stake: Number) -> Decimal:
    value = to_decimal_number(stake, "stake")
    if value <= 0:
        raise QuantError(f"stake must be greater than 0, got {value}", code="invalid_stake")
    return value


def payout(stake: Number, decimal_odds: Number) -> Decimal:
    """Total return (stake included) of a winning bet."""
    return money(validate_stake(stake) * validate_decimal_odds(decimal_odds))


def profit(stake: Number, decimal_odds: Number) -> Decimal:
    """Net profit of a winning bet."""
    return money(validate_stake(stake) * (validate_decimal_odds(decimal_odds) - 1))


def roi(total_profit: Number, total_staked: Number) -> float | None:
    """Profit divided by amount staked. ``None`` when nothing was staked."""
    staked = to_decimal_number(total_staked, "total staked")
    if staked < 0:
        raise QuantError("total staked cannot be negative", code="invalid_stake")
    if staked == 0:
        return None
    return float(to_decimal_number(total_profit, "total profit") / staked)


@dataclass(frozen=True, slots=True)
class EVResult:
    win_probability: float
    decimal_odds: Decimal
    #: Expected profit per 1 unit staked.
    ev_per_unit: float
    #: ``ev_per_unit`` expressed as a percentage of stake.
    ev_percent: float
    #: Expected profit for the given stake, in currency units.
    expected_profit: Decimal
    #: Win probability at which the price has zero EV (1/decimal).
    breakeven_probability: float
    #: win_probability - breakeven_probability.
    edge: float


def expected_value(win_probability: float, decimal_odds: Number, stake: Number = 1) -> EVResult:
    """EV = p * (decimal - 1) - (1 - p).

    The result is only as good as ``win_probability``; this function does not
    estimate it.
    """
    p = validate_probability(win_probability, "win probability")
    price = validate_decimal_odds(decimal_odds)
    stake_value = validate_stake(stake)
    p_dec = Decimal(str(p))
    ev_unit = p_dec * (price - 1) - (1 - p_dec)
    breakeven = float(1 / price)
    return EVResult(
        win_probability=p,
        decimal_odds=price,
        ev_per_unit=float(ev_unit),
        ev_percent=float(ev_unit * 100),
        expected_profit=money(ev_unit * stake_value),
        breakeven_probability=breakeven,
        edge=p - breakeven,
    )
