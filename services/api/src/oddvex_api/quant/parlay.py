"""Parlay pricing and bet settlement math."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from .errors import QuantError
from .ev import money, validate_stake
from .odds import Number, to_decimal_number, validate_decimal_odds, validate_probability

LegResult = Literal["pending", "won", "lost", "push", "void", "half_won", "half_lost"]
BetResult = Literal["won", "lost", "push", "void", "half_won", "half_lost", "cashout"]

LEG_RESULTS: frozenset[str] = frozenset(
    {"pending", "won", "lost", "push", "void", "half_won", "half_lost"}
)
BET_RESULTS: frozenset[str] = frozenset(
    {"won", "lost", "push", "void", "half_won", "half_lost", "cashout"}
)

INDEPENDENCE_NOTE = (
    "assumes independence: the legs are from distinct events and their win "
    "probabilities were multiplied"
)

_ONE = Decimal(1)
_HALF = Decimal("0.5")


@dataclass(frozen=True, slots=True)
class ParlayLeg:
    decimal_odds: Decimal
    event_id: str | None = None
    win_probability: float | None = None
    result: str = "pending"
    label: str | None = None


@dataclass(frozen=True, slots=True)
class ParlayResult:
    #: Product of the prices of all legs still in the parlay (pushed/void legs drop out).
    combined_decimal: Decimal
    active_legs: int
    dropped_legs: int
    #: Only set when every active leg has a win probability and all legs are from distinct events.
    combined_probability: float | None
    probability_note: str
    correlation_warnings: list[str] = field(default_factory=list)
    payout: Decimal | None = None
    profit: Decimal | None = None


def _leg_factor(leg: ParlayLeg) -> Decimal | None:
    """Multiplier a leg contributes to the parlay price; ``None`` means the leg lost."""
    price = validate_decimal_odds(leg.decimal_odds)
    if leg.result in ("pending", "won"):
        return price
    if leg.result in ("push", "void"):
        return _ONE
    if leg.result == "half_won":
        return _ONE + (price - _ONE) / 2
    if leg.result == "half_lost":
        return _HALF
    if leg.result == "lost":
        return None
    raise QuantError(f"unknown leg result {leg.result!r}", code="invalid_leg_result")


def combine_parlay(legs: Sequence[ParlayLeg], stake: Number | None = None) -> ParlayResult:
    """Combined price of a parlay, plus a combined probability when that is defensible.

    The combined *price* is always the product of the leg prices. A combined
    *probability* is only returned when every active leg carries a win
    probability and every leg is from a different, known event. Legs from the
    same event are correlated, so multiplying their probabilities would be
    wrong; in that case ``combined_probability`` is ``None`` and
    ``correlation_warnings`` explains why.
    """
    if not legs:
        raise QuantError("a parlay needs at least one leg", code="invalid_parlay")
    combined = _ONE
    dropped = 0
    for leg in legs:
        if leg.result not in LEG_RESULTS:
            raise QuantError(f"unknown leg result {leg.result!r}", code="invalid_leg_result")
        factor = _leg_factor(leg)
        if leg.result in ("push", "void"):
            dropped += 1
        # A lost leg keeps its quoted price here; settlement is handled by settle_parlay.
        combined *= factor if factor is not None else leg.decimal_odds
        if leg.win_probability is not None:
            validate_probability(leg.win_probability, "leg win probability")

    active = [leg for leg in legs if leg.result not in ("push", "void")]
    warnings: list[str] = []
    counts = Counter(leg.event_id for leg in active if leg.event_id)
    for event_id, count in sorted(counts.items()):
        if count > 1:
            warnings.append(
                f"{count} legs are from the same event ({event_id}); their outcomes are "
                "correlated, so leg probabilities cannot be multiplied"
            )
    unknown = sum(1 for leg in active if not leg.event_id)
    if unknown and len(active) > 1:
        warnings.append(
            f"{unknown} leg(s) have no event_id, so independence between legs cannot be verified"
        )

    probability: float | None = None
    if not active:
        note = "no active legs remain"
    elif warnings:
        note = "not computed: legs may be correlated"
    elif any(leg.win_probability is None for leg in active):
        note = "not computed: a win probability is required for every leg"
    else:
        probability = 1.0
        for leg in active:
            probability *= float(leg.win_probability)  # type: ignore[arg-type]
        note = INDEPENDENCE_NOTE

    total_payout: Decimal | None = None
    total_profit: Decimal | None = None
    if stake is not None:
        stake_value = validate_stake(stake)
        total_payout = money(stake_value * combined)
        total_profit = money(stake_value * combined - stake_value)
    return ParlayResult(
        combined_decimal=combined,
        active_legs=len(active),
        dropped_legs=dropped,
        combined_probability=probability,
        probability_note=note,
        correlation_warnings=warnings,
        payout=total_payout,
        profit=total_profit,
    )


@dataclass(frozen=True, slots=True)
class Settlement:
    result: str
    #: Total amount returned to the bettor (stake included where applicable).
    payout: Decimal
    #: payout - stake.
    profit: Decimal
    effective_decimal: Decimal | None = None


def settle_bet(
    stake: Number,
    decimal_odds: Number,
    result: str,
    cashout_amount: Number | None = None,
) -> Settlement:
    """Settlement of a single price.

    * won: stake * decimal
    * lost: 0
    * push / void: stake returned
    * half_won: half the stake wins, half is returned
    * half_lost: half the stake is returned
    * cashout: the agreed amount is returned (requires ``cashout_amount``)
    """
    stake_value = validate_stake(stake)
    price = validate_decimal_odds(decimal_odds)
    if result == "won":
        returned = stake_value * price
    elif result == "lost":
        returned = Decimal(0)
    elif result in ("push", "void"):
        returned = stake_value
    elif result == "half_won":
        returned = stake_value / 2 * price + stake_value / 2
    elif result == "half_lost":
        returned = stake_value / 2
    elif result == "cashout":
        if cashout_amount is None:
            raise QuantError("cashout requires a cashout amount", code="invalid_cashout")
        returned = to_decimal_number(cashout_amount, "cashout amount")
        if returned < 0:
            raise QuantError("cashout amount cannot be negative", code="invalid_cashout")
    else:
        raise QuantError(f"unknown settlement result {result!r}", code="invalid_result")
    returned = money(returned)
    return Settlement(
        result=result,
        payout=returned,
        profit=money(returned - stake_value),
        effective_decimal=price,
    )


def settle_parlay(stake: Number, legs: Sequence[ParlayLeg]) -> Settlement:
    """Settle a parlay from its leg results.

    Any lost leg loses the parlay. Pushed and void legs drop out (price 1.0).
    Half-won / half-lost legs contribute their single-bet return per unit.
    If every leg was void the parlay is void; if only pushes/voids remain it is
    a push. Raises if any leg is still pending and no leg has lost.
    """
    if not legs:
        raise QuantError("a parlay needs at least one leg", code="invalid_parlay")
    stake_value = validate_stake(stake)
    results = [leg.result for leg in legs]
    for leg in legs:
        validate_decimal_odds(leg.decimal_odds)
        if leg.result not in LEG_RESULTS:
            raise QuantError(f"unknown leg result {leg.result!r}", code="invalid_leg_result")
    if "lost" in results:
        return Settlement("lost", Decimal("0.00"), money(-stake_value), Decimal(0))
    if "pending" in results:
        raise QuantError(
            "cannot settle a parlay while legs are pending", code="parlay_legs_pending"
        )
    combined = _ONE
    for leg in legs:
        factor = _leg_factor(leg)
        assert factor is not None
        combined *= factor
    returned = money(stake_value * combined)
    if all(r == "void" for r in results):
        status = "void"
    elif all(r in ("push", "void") for r in results):
        status = "push"
    elif all(r in ("won", "push", "void") for r in results):
        status = "won"
    elif returned > stake_value:
        status = "half_won"
    elif returned < stake_value:
        status = "half_lost"
    else:
        status = "push"
    return Settlement(status, returned, money(returned - stake_value), combined)
