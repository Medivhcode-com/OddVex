"""What the bet columns can hold, checked before anything is written.

Prices are stored as ``Numeric(16, 6)`` (``db.models.ODDS``): six decimal places and at
most ten digits before the point. Money is stored as ``Numeric(14, 2)``
(``db.models.MONEY``): cents, and at most twelve digits before the point. A value is
rounded to its column first and then checked, so what is validated is what is stored:

* a price that would be stored as 1.000000 or less is refused (``invalid_decimal_odds``),
* a price longer than the column is refused (``odds_out_of_range``),
* a stake that would be stored as 0.00 is refused (``invalid_stake``),
* a stake and price whose payout is longer than the money column are refused
  (``payout_out_of_range``).

All four are 422. PostgreSQL would refuse the too-long values with an error of its own;
SQLite would store them.

Rows written before these checks can hold a price of 1.000000 or a stake of 0.00.
:func:`shown_odds` is how such a row is read: see there.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from ..errors import ApiError
from ..quant import QuantError, money
from ..schemas import odds_to_decimal

ODDS_QUANTUM = Decimal("0.000001")
#: Shortest and longest price the ``ODDS`` column holds that is still a price (above 1).
MIN_STORED_ODDS = Decimal("1.000001")
MAX_STORED_ODDS = Decimal("9999999999.999999")
#: Largest amount the ``MONEY`` column holds.
MAX_STORED_MONEY = Decimal("999999999999.99")
MIN_STORED_STAKE = Decimal("0.01")


def _too_short(what: str) -> ApiError:
    return ApiError(
        422,
        "invalid_decimal_odds",
        f"{what} is too short to record: in decimal odds it must be at least {MIN_STORED_ODDS}",
        details={"min_decimal_odds": str(MIN_STORED_ODDS)},
    )


def _too_long(what: str) -> ApiError:
    return ApiError(
        422,
        "odds_out_of_range",
        f"{what} is too long to record: in decimal odds it must be at most {MAX_STORED_ODDS}",
        details={"max_decimal_odds": str(MAX_STORED_ODDS)},
    )


def stored_odds(value: Decimal, what: str = "The price") -> Decimal:
    """``value`` rounded to the price column, or a 422 when the column cannot hold it."""
    if not value.is_finite():
        raise _too_long(what)
    # Compared before rounding: quantizing a number with more than 28 digits raises.
    if value > MAX_STORED_ODDS + 1:
        raise _too_long(what)
    rounded = value.quantize(ODDS_QUANTUM, rounding=ROUND_HALF_UP)
    if rounded > MAX_STORED_ODDS:
        raise _too_long(what)
    if rounded < MIN_STORED_ODDS:
        raise _too_short(what)
    return rounded


def user_odds(value: float | str, odds_format: str, what: str = "The price") -> Decimal:
    """A price as typed by a user, as the decimal odds that will be stored.

    Raises ``QuantError`` (422) for a value that is not a price in ``odds_format`` and the
    errors of :func:`stored_odds` for one the column cannot hold.
    """
    try:
        parsed = odds_to_decimal(value, odds_format)
    except QuantError:
        raise
    except ArithmeticError as exc:
        # A number with an exponent too large for decimal arithmetic, such as "1e9999999".
        raise _too_long(what) from exc
    return stored_odds(parsed, what)


def stored_stake(value: float | Decimal) -> Decimal:
    """``value`` rounded to cents, or a 422 when it would be stored as 0.00 or cannot fit."""
    amount = value if isinstance(value, Decimal) else Decimal(str(value))
    if not amount.is_finite() or amount > MAX_STORED_MONEY:
        raise ApiError(
            422,
            "invalid_stake",
            f"The stake is too large to record: it must be at most {MAX_STORED_MONEY}",
            details={"max_stake": str(MAX_STORED_MONEY)},
        )
    rounded = money(amount)
    if rounded < MIN_STORED_STAKE:
        raise ApiError(
            422,
            "invalid_stake",
            f"The stake must be at least {MIN_STORED_STAKE}: a smaller amount rounds to 0.00",
            details={"min_stake": str(MIN_STORED_STAKE)},
        )
    return rounded


def check_money_fits(amount: Decimal, what: str = "The payout") -> None:
    """422 when ``amount`` is longer than the money column."""
    if not amount.is_finite() or abs(amount) > MAX_STORED_MONEY:
        raise ApiError(
            422,
            "payout_out_of_range",
            f"{what} is too large to record: it must be at most {MAX_STORED_MONEY}",
            details={"max_amount": str(MAX_STORED_MONEY)},
        )


def check_payout_fits(stake: Decimal, decimal_odds: Decimal) -> None:
    """422 when ``stake`` at ``decimal_odds`` would pay more than the money column holds."""
    check_money_fits(stake * decimal_odds, "The payout of this stake at this price")


def shown_odds(value: Decimal | float) -> Decimal:
    """A stored price as it is read back: the nearest price the column can validly hold.

    Every price written through the checks above is returned unchanged. A row from before
    them can hold 1.000000 (a very short price that was rounded), and a SQLite database
    one longer than the column; those are read as :data:`MIN_STORED_ODDS` and
    :data:`MAX_STORED_ODDS`. At the four decimal places a response carries, the price
    shown for a stored 1.000000 is 1.0, the stored value. This keeps such a bet in the
    list, the summary, the analytics and the export, so it can be corrected or deleted.
    """
    price = value if isinstance(value, Decimal) else Decimal(str(value))
    if not price.is_finite():
        return MAX_STORED_ODDS if price > 0 else MIN_STORED_ODDS
    return min(max(price, MIN_STORED_ODDS), MAX_STORED_ODDS)
