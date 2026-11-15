"""Odds format conversion and implied probability.

Decimal odds are the canonical internal representation: the total return per
1 unit staked, strictly greater than 1. All functions are pure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from fractions import Fraction
from typing import Literal

from .errors import QuantError

OddsFormat = Literal["american", "decimal", "fractional"]

_HUNDRED = Decimal(100)
_ONE = Decimal(1)
_FRACTION_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*$")

Number = int | float | str | Decimal


def to_decimal_number(value: Number, what: str = "value") -> Decimal:
    """Coerce a number-like value to a finite ``Decimal`` without float noise."""
    if isinstance(value, bool):
        raise QuantError(f"{what} must be a number, got a boolean")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise QuantError(f"{what} must be a number, got {value!r}") from exc
    if not result.is_finite():
        raise QuantError(f"{what} must be finite, got {value!r}")
    return result


def validate_decimal_odds(decimal_odds: Number) -> Decimal:
    value = to_decimal_number(decimal_odds, "decimal odds")
    if value <= _ONE:
        raise QuantError(
            f"decimal odds must be greater than 1, got {value}", code="invalid_decimal_odds"
        )
    return value


def validate_probability(probability: float, what: str = "probability") -> float:
    """Probabilities must be strictly inside (0, 1)."""
    try:
        value = float(probability)
    except (TypeError, ValueError) as exc:
        raise QuantError(f"{what} must be a number", code="invalid_probability") from exc
    if not (0.0 < value < 1.0):
        raise QuantError(
            f"{what} must be strictly between 0 and 1, got {probability}",
            code="invalid_probability",
        )
    return value


def american_to_decimal(american: Number) -> Decimal:
    """+150 -> 2.5, -110 -> 1.9090..., +100 / -100 -> 2.0."""
    value = to_decimal_number(american, "american odds")
    if -_HUNDRED < value < _HUNDRED:
        raise QuantError(
            f"american odds must be <= -100 or >= +100, got {value}",
            code="invalid_american_odds",
        )
    if value > 0:
        return _ONE + value / _HUNDRED
    return _ONE + _HUNDRED / -value


def decimal_to_american(decimal_odds: Number) -> int:
    """Nearest whole-number American price. Even money (2.0) is reported as +100."""
    value = validate_decimal_odds(decimal_odds)
    if value >= 2:
        raw = (value - _ONE) * _HUNDRED
    else:
        raw = -_HUNDRED / (value - _ONE)
    rounded = int(raw.quantize(_ONE, rounding=ROUND_HALF_UP))
    if rounded == -100:
        return 100
    return rounded


def fractional_to_decimal(fractional: str) -> Decimal:
    """Parse "5/2" -> 3.5. A bare number such as "2" is read as "2/1"."""
    if not isinstance(fractional, str):
        raise QuantError("fractional odds must be a string like '5/2'", "invalid_fractional_odds")
    text = fractional.strip()
    match = _FRACTION_RE.match(text)
    if match:
        numerator, denominator = Decimal(match.group(1)), Decimal(match.group(2))
    else:
        try:
            numerator, denominator = Decimal(text), _ONE
        except InvalidOperation as exc:
            raise QuantError(
                f"fractional odds must look like '5/2', got {fractional!r}",
                code="invalid_fractional_odds",
            ) from exc
    if not numerator.is_finite() or denominator <= 0 or numerator <= 0:
        raise QuantError(
            f"fractional odds must be a positive ratio, got {fractional!r}",
            code="invalid_fractional_odds",
        )
    return _ONE + numerator / denominator


def decimal_to_fractional(decimal_odds: Number, max_denominator: int = 100) -> str:
    """Reduced fraction closest to the price, e.g. 3.5 -> "5/2", 1.9091 -> "10/11"."""
    value = validate_decimal_odds(decimal_odds)
    fraction = Fraction(value - _ONE).limit_denominator(max_denominator)
    if fraction <= 0:
        # Price too short to express with the allowed denominator.
        fraction = Fraction(1, max_denominator)
    return f"{fraction.numerator}/{fraction.denominator}"


def parse_odds(odds_format: str, value: Number) -> Decimal:
    """Normalise any supported input format to decimal odds."""
    if odds_format == "american":
        number = to_decimal_number(value, "american odds")
        if number != number.to_integral_value():
            raise QuantError(
                f"american odds must be a whole number, got {value}", "invalid_american_odds"
            )
        return american_to_decimal(number)
    if odds_format == "decimal":
        return validate_decimal_odds(value)
    if odds_format == "fractional":
        return fractional_to_decimal(str(value))
    raise QuantError(f"unknown odds format {odds_format!r}", code="invalid_odds_format")


def implied_probability(decimal_odds: Number) -> float:
    """Raw implied probability 1/decimal. Includes the bookmaker margin."""
    return float(_ONE / validate_decimal_odds(decimal_odds))


def probability_to_decimal(probability: float) -> Decimal:
    """Fair decimal price for a probability in (0, 1)."""
    return _ONE / Decimal(str(validate_probability(probability)))


@dataclass(frozen=True, slots=True)
class Price:
    """One price in every display format."""

    american: int
    decimal: Decimal
    fractional: str
    implied_probability: float


def describe_price(decimal_odds: Number) -> Price:
    value = validate_decimal_odds(decimal_odds)
    return Price(
        american=decimal_to_american(value),
        decimal=value,
        fractional=decimal_to_fractional(value),
        implied_probability=implied_probability(value),
    )
