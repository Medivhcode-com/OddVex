"""Grade a structured selection against a final score. Pure: no I/O, no clock.

Conventions (also in ``docs/QUANT_METHODOLOGY.md``):

* ``outcome_key`` is ``home`` / ``away`` / ``draw`` for moneyline, ``home`` / ``away`` for
  spread, ``over`` / ``under`` for total.
* A spread ``line`` is from the perspective of the **selected side**: ``home -3.5`` is
  ``outcome_key="home", line=-3.5`` and the other side of that market is
  ``outcome_key="away", line=+3.5``.
* A total ``line`` is the number of combined points.
* A tie on a 2-way moneyline is a push. On a 3-way moneyline (``three_way=True``) a tie
  wins for ``draw`` and loses for ``home`` and ``away``.
"""

from __future__ import annotations

import math
from decimal import Decimal

from .errors import QuantError

GRADEABLE_MARKETS: tuple[str, ...] = ("moneyline", "spread", "total")
GRADE_RESULTS: tuple[str, ...] = ("won", "lost", "push")
_SIDES = ("home", "away")
_TOTAL_SIDES = ("over", "under")


def valid_outcome_keys(market: str, three_way: bool = False) -> tuple[str, ...]:
    """Outcome keys that can be graded for ``market`` (empty if the market cannot be graded)."""
    if market == "moneyline":
        return (*_SIDES, "draw") if three_way else _SIDES
    if market == "spread":
        return _SIDES
    if market == "total":
        return _TOTAL_SIDES
    return ()


def is_gradeable(market: str | None, outcome_key: str | None, line: object | None) -> bool:
    """Whether a selection carries enough structure to be graded from a final score.

    ``draw`` counts as structurally gradeable for moneyline; whether the event really has
    a 3-way market is checked where the event is known.
    """
    if market is None or outcome_key is None:
        return False
    if outcome_key not in valid_outcome_keys(market, three_way=True):
        return False
    return market == "moneyline" or line is not None


def _line(line: float | Decimal | int | str | None, market: str) -> Decimal:
    if line is None or isinstance(line, bool):
        raise QuantError(f"a {market} selection needs a line", code="invalid_line")
    try:
        value = Decimal(str(line))
    except ArithmeticError as exc:
        raise QuantError("line must be a number", code="invalid_line") from exc
    if not value.is_finite():
        raise QuantError("line must be a finite number", code="invalid_line")
    return value


def _score(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        if isinstance(value, float) and math.isfinite(value) and value == int(value):
            value = int(value)
        else:
            raise QuantError(f"{name} must be a whole number", code="invalid_score")
    if value < 0:
        raise QuantError(f"{name} cannot be negative", code="invalid_score")
    return value


def _sign(value: Decimal | int) -> str:
    if value > 0:
        return "won"
    if value < 0:
        return "lost"
    return "push"


def grade_leg(
    market: str,
    outcome_key: str,
    line: float | Decimal | int | str | None,
    home_score: int,
    away_score: int,
    *,
    three_way: bool = False,
) -> str:
    """Return ``"won"``, ``"lost"`` or ``"push"`` for one selection and a final score."""
    if outcome_key not in valid_outcome_keys(market, three_way):
        if market not in GRADEABLE_MARKETS:
            raise QuantError(f"market {market!r} cannot be graded", code="invalid_market")
        raise QuantError(
            f"outcome {outcome_key!r} is not valid for {market}", code="invalid_outcome"
        )
    home = _score(home_score, "home score")
    away = _score(away_score, "away score")

    if market == "moneyline":
        margin = home - away
        if outcome_key == "draw":
            return "won" if margin == 0 else "lost"
        if margin == 0:
            return "lost" if three_way else "push"
        return _sign(margin if outcome_key == "home" else -margin)

    points = _line(line, market)
    if market == "spread":
        selected, other = (home, away) if outcome_key == "home" else (away, home)
        return _sign(Decimal(selected) + points - Decimal(other))

    difference = Decimal(home + away) - points
    return _sign(difference if outcome_key == "over" else -difference)
