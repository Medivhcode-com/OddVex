"""Calculator endpoints: thin wrappers over :mod:`oddvex_api.quant` that show their working."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..errors import ERROR_RESPONSES
from ..quant import (
    ParlayLeg,
    ProbabilityStatus,
    closing_line_value,
    combine_parlay,
    decimal_to_american,
    expected_value,
    no_vig,
    probability_to_decimal,
)
from ..schemas import OddsFormatIn, OddsValue, PriceOut, odds_to_decimal, price_out

router = APIRouter(prefix="/quant", tags=["quant"], responses=ERROR_RESPONSES)

EV_CAVEAT = (
    "EV depends entirely on the win probability you enter. OddVex does not estimate that "
    "probability and does not claim any predictive edge."
)


def _fmt(value: Decimal | float, places: int = 4) -> str:
    return f"{float(value):.{places}f}"


def _pct(value: float, places: int = 2) -> str:
    return f"{value * 100:.{places}f}%"


def _american(value: int) -> str:
    return f"+{value}" if value > 0 else str(value)


def _conversion_step(value: OddsValue, odds_format: str, decimal: Decimal) -> str:
    if odds_format == "american":
        american = decimal_to_american(decimal)
        if american > 0:
            return f"American {_american(american)}: decimal = 1 + {american}/100 = {_fmt(decimal)}"
        return f"American {american}: decimal = 1 + 100/{abs(american)} = {_fmt(decimal)}"
    if odds_format == "fractional":
        return f"Fractional {value}: decimal = 1 + {value} = {_fmt(decimal)}"
    return f"Decimal {_fmt(decimal)} (already decimal odds)"


# -------------------------------------------------------------------- convert
class ConvertRequest(BaseModel):
    odds: OddsValue = Field(examples=[-110, "+150", 2.5, "5/2"])
    odds_format: OddsFormatIn = "american"


class ConvertResponse(BaseModel):
    price: PriceOut
    steps: list[str]


@router.post(
    "/convert",
    response_model=ConvertResponse,
    operation_id="quant_convert",
    summary="Convert a price between American, decimal and fractional",
)
def quant_convert(body: ConvertRequest) -> ConvertResponse:
    decimal = odds_to_decimal(body.odds, body.odds_format)
    price = price_out(decimal)
    return ConvertResponse(
        price=price,
        steps=[
            _conversion_step(body.odds, body.odds_format, decimal),
            f"American = {_american(price.american)} (nearest whole number)",
            f"Fractional = {price.fractional} (reduced, denominator up to 100)",
            f"Implied probability = 1 / {_fmt(decimal)} = {_pct(price.implied_probability)} "
            "(includes the bookmaker margin)",
        ],
    )


# --------------------------------------------------------------------- no-vig
class NoVigRequest(BaseModel):
    odds: list[OddsValue] = Field(
        min_length=2,
        max_length=20,
        description="Every outcome of one market.",
        examples=[[-110, -110]],
    )
    odds_format: OddsFormatIn = "american"
    labels: list[str] | None = Field(default=None, description="Optional outcome names.")


class NoVigOutcomeOut(BaseModel):
    label: str
    price: PriceOut
    implied_probability: float
    no_vig_probability: float
    fair_price: PriceOut = Field(description="The price with the margin removed.")


class NoVigResponse(BaseModel):
    outcomes: list[NoVigOutcomeOut]
    overround: float = Field(description="Sum of implied probabilities minus 1.")
    hold: float = Field(description="1 - 1/sum(implied probabilities).")
    method: Literal["multiplicative"]
    steps: list[str]


@router.post(
    "/no-vig",
    response_model=NoVigResponse,
    operation_id="quant_no_vig",
    summary="Remove the bookmaker margin from an n-way market (proportional method)",
)
def quant_no_vig(body: NoVigRequest) -> NoVigResponse:
    decimals = [odds_to_decimal(value, body.odds_format) for value in body.odds]
    labels = list(body.labels or [])
    labels += [f"Outcome {i + 1}" for i in range(len(labels), len(decimals))]
    result = no_vig(decimals)
    booksum = 1.0 + result.overround
    steps = [
        f"{label}: implied = 1 / {_fmt(decimal)} = {_pct(implied)}"
        for label, decimal, implied in zip(
            labels, decimals, result.implied_probabilities, strict=False
        )
    ]
    steps.append(
        "Sum of implied probabilities = "
        + " + ".join(_pct(p) for p in result.implied_probabilities)
        + f" = {_pct(booksum)}"
    )
    steps.append(f"Overround = {_pct(booksum)} - 100% = {_pct(result.overround)}")
    steps.append(f"Hold = 1 - 1/{booksum:.4f} = {_pct(result.hold)}")
    steps += [
        f"{label}: no-vig = {_pct(implied)} / {_pct(booksum)} = {_pct(fair)}"
        for label, implied, fair in zip(
            labels, result.implied_probabilities, result.fair_probabilities, strict=False
        )
    ]
    return NoVigResponse(
        outcomes=[
            NoVigOutcomeOut(
                label=label,
                price=price_out(decimal),
                implied_probability=round(implied, 6),
                no_vig_probability=round(fair, 6),
                fair_price=price_out(probability_to_decimal(fair)),
            )
            for label, decimal, implied, fair in zip(
                labels,
                decimals,
                result.implied_probabilities,
                result.fair_probabilities,
                strict=False,
            )
        ],
        overround=round(result.overround, 6),
        hold=round(result.hold, 6),
        method="multiplicative",
        steps=steps,
    )


# ------------------------------------------------------------------------- EV
class EVRequest(BaseModel):
    odds: OddsValue = Field(examples=["+150"])
    odds_format: OddsFormatIn = "american"
    win_probability: float = Field(
        description="Your own estimate, strictly between 0 and 1.", examples=[0.45]
    )
    stake: float = Field(default=1.0, gt=0, le=1_000_000)


class EVResponse(BaseModel):
    price: PriceOut
    win_probability: float
    stake: float
    ev_per_unit: float = Field(description="Expected profit per 1 unit staked.")
    ev_percent: float
    expected_profit: float = Field(description="Expected profit for the stake given.")
    breakeven_probability: float
    edge: float = Field(description="win_probability - breakeven_probability.")
    steps: list[str]
    caveat: str


@router.post(
    "/ev",
    response_model=EVResponse,
    operation_id="quant_ev",
    summary="Expected value of a price for a win probability you supply",
)
def quant_ev(body: EVRequest) -> EVResponse:
    decimal = odds_to_decimal(body.odds, body.odds_format)
    result = expected_value(body.win_probability, decimal, body.stake)
    p = result.win_probability
    return EVResponse(
        price=price_out(decimal),
        win_probability=p,
        stake=body.stake,
        ev_per_unit=round(result.ev_per_unit, 6),
        ev_percent=round(result.ev_percent, 4),
        expected_profit=float(result.expected_profit),
        breakeven_probability=round(result.breakeven_probability, 6),
        edge=round(result.edge, 6),
        steps=[
            _conversion_step(body.odds, body.odds_format, decimal),
            f"Profit per unit if it wins = {_fmt(decimal)} - 1 = {_fmt(decimal - 1)}",
            f"EV per unit = p x profit - (1 - p) = {p:.4f} x {_fmt(decimal - 1)} - {1 - p:.4f} "
            f"= {result.ev_per_unit:+.4f}",
            f"EV% = {result.ev_percent:+.2f}%",
            f"Break-even probability = 1 / {_fmt(decimal)} = {_pct(result.breakeven_probability)}",
            f"Expected profit on a {body.stake:.2f} stake = {float(result.expected_profit):+.2f}",
        ],
        caveat=EV_CAVEAT,
    )


# --------------------------------------------------------------------- parlay
class ParlayLegIn(BaseModel):
    odds: OddsValue
    odds_format: OddsFormatIn = "american"
    label: str | None = Field(default=None, max_length=200)
    event_id: str | None = Field(
        default=None,
        max_length=64,
        description="Legs sharing an event_id are treated as correlated.",
    )
    win_probability: float | None = Field(default=None, description="Optional, in (0, 1).")
    result: Literal["pending", "won", "push", "void"] = Field(
        default="pending", description="Pushed and void legs drop out of the parlay."
    )


class ParlayRequest(BaseModel):
    legs: list[ParlayLegIn] = Field(min_length=1, max_length=20)
    stake: float | None = Field(default=None, gt=0, le=1_000_000)


class ParlayLegOut(BaseModel):
    label: str
    price: PriceOut
    result: str
    event_id: str | None = None
    counted: bool = Field(description="False when the leg pushed or was voided.")


class ParlayResponse(BaseModel):
    legs: list[ParlayLegOut]
    combined_price: PriceOut | None = Field(
        description="Null when every leg pushed or was voided (the stake is returned)."
    )
    combined_decimal: float
    active_legs: int
    dropped_legs: int
    stake: float | None = None
    payout: float | None = None
    profit: float | None = None
    combined_probability: float | None = Field(
        description=(
            "Only computed when every active leg has a win probability and the active legs "
            "are from distinct known events (a single active leg needs no `event_id`). "
            "Assumes independence. `probability_status` says why it is null."
        )
    )
    probability_status: ProbabilityStatus = Field(
        description=(
            "Why `combined_probability` is or is not there, as a fixed value a client can "
            "map to its own wording. `computed`: every active leg had a `win_probability` "
            "and the active legs are from distinct known events, so the probabilities were "
            "multiplied (assumes independence). A single active leg has nothing to be "
            "correlated with, so it counts as distinct with or without an `event_id`. "
            "`needs_leg_probabilities`: the same holds for the events, but at least one "
            "active leg has no `win_probability`. `same_event_legs`: two or more active "
            "legs share an `event_id`, so their results are correlated. `unverified_legs`: "
            "there are several active legs and at least one has no `event_id`, so "
            "independence cannot be checked. `no_active_legs`: every leg pushed or was voided. "
            "`combined_probability` is a number only for `computed` and null for every other "
            "value. Precedence when several apply: `no_active_legs`, then `same_event_legs`, "
            "then `unverified_legs`, then `needs_leg_probabilities`, then `computed`."
        )
    )
    probability_note: str = Field(
        description=(
            "The same reason as a sentence, kept for older clients. New clients should "
            "choose their wording from `probability_status`."
        )
    )
    correlation_warnings: list[str] = Field(
        description=(
            "One sentence per reason the legs may be correlated: an `event_id` shared by "
            "several active legs, or active legs without an `event_id`. Empty otherwise."
        )
    )
    steps: list[str] = Field(
        description=(
            "The worked calculation, one line per step: each leg, the combined decimal, the "
            "payout when a stake was given, and the combined probability only when one was "
            "computed (`probability_status` is `computed`)."
        )
    )


@router.post(
    "/parlay",
    response_model=ParlayResponse,
    operation_id="quant_parlay",
    summary="Combined parlay price and payout",
)
def quant_parlay(body: ParlayRequest) -> ParlayResponse:
    decimals = [odds_to_decimal(leg.odds, leg.odds_format) for leg in body.legs]
    labels = [leg.label or f"Leg {i + 1}" for i, leg in enumerate(body.legs)]
    result = combine_parlay(
        [
            ParlayLeg(
                decimal_odds=decimal,
                event_id=leg.event_id,
                win_probability=leg.win_probability,
                result=leg.result,
                label=label,
            )
            for leg, decimal, label in zip(body.legs, decimals, labels, strict=True)
        ],
        stake=body.stake,
    )
    steps: list[str] = []
    factors: list[str] = []
    for leg, decimal, label in zip(body.legs, decimals, labels, strict=True):
        if leg.result in ("push", "void"):
            steps.append(f"{label}: {leg.result}, dropped (counts as 1.0000)")
        else:
            steps.append(f"{label}: decimal {_fmt(decimal)}")
            factors.append(_fmt(decimal))
    steps.append(
        "Combined decimal = "
        + (" x ".join(factors) if factors else "1.0000 (no active legs)")
        + f" = {_fmt(result.combined_decimal)}"
    )
    if body.stake is not None and result.payout is not None and result.profit is not None:
        steps.append(
            f"Payout = {body.stake:.2f} x {_fmt(result.combined_decimal)} = "
            f"{float(result.payout):.2f} (profit {float(result.profit):+.2f})"
        )
    if result.combined_probability is not None:
        steps.append(
            "Combined probability = "
            + " x ".join(
                f"{leg.win_probability:.4f}"
                for leg in body.legs
                if leg.win_probability is not None and leg.result not in ("push", "void")
            )
            + f" = {_pct(result.combined_probability)} (assumes independence)"
        )
    # Without a combined probability the working ends here: the reason is in
    # ``probability_status`` and ``probability_note``, not in a step that computes nothing.
    return ParlayResponse(
        legs=[
            ParlayLegOut(
                label=label,
                price=price_out(decimal),
                result=leg.result,
                event_id=leg.event_id,
                counted=leg.result not in ("push", "void"),
            )
            for leg, decimal, label in zip(body.legs, decimals, labels, strict=True)
        ],
        combined_price=price_out(result.combined_decimal) if result.combined_decimal > 1 else None,
        combined_decimal=round(float(result.combined_decimal), 4),
        active_legs=result.active_legs,
        dropped_legs=result.dropped_legs,
        stake=body.stake,
        payout=float(result.payout) if result.payout is not None else None,
        profit=float(result.profit) if result.profit is not None else None,
        combined_probability=(
            round(result.combined_probability, 6)
            if result.combined_probability is not None
            else None
        ),
        probability_status=result.probability_status,
        probability_note=result.probability_note,
        correlation_warnings=result.correlation_warnings,
        steps=steps,
    )


# ------------------------------------------------------------------------ CLV
class CLVRequest(BaseModel):
    odds: OddsValue = Field(description="The price you took.")
    closing_odds: OddsValue = Field(description="Closing price of the same selection.")
    closing_opposite_odds: OddsValue | None = Field(
        default=None,
        description="Closing price of the other side of a two-way market (enables no-vig CLV).",
    )
    odds_format: OddsFormatIn = "american"


class CLVResponse(BaseModel):
    price: PriceOut
    closing_price: PriceOut
    clv: float = Field(description="decimal_taken / decimal_closing - 1, as a fraction.")
    clv_percent: float
    beat_close: bool
    closing_no_vig_probability: float | None = None
    no_vig_probability_delta: float | None = Field(
        default=None,
        description="No-vig closing probability minus the implied probability of your price.",
    )
    ev_at_close_percent: float | None = Field(
        default=None,
        description="EV% of your price if the no-vig close were the true probability.",
    )
    steps: list[str]


@router.post(
    "/clv",
    response_model=CLVResponse,
    operation_id="quant_clv",
    summary="Closing line value of a price against the close",
)
def quant_clv(body: CLVRequest) -> CLVResponse:
    taken = odds_to_decimal(body.odds, body.odds_format)
    closing = odds_to_decimal(body.closing_odds, body.odds_format)
    opposite = (
        odds_to_decimal(body.closing_opposite_odds, body.odds_format)
        if body.closing_opposite_odds is not None
        else None
    )
    result = closing_line_value(taken, closing, opposite)
    steps = [
        f"Price taken: decimal {_fmt(taken)}",
        f"Closing price: decimal {_fmt(closing)}",
        f"CLV = {_fmt(taken)} / {_fmt(closing)} - 1 = {result.clv_percent:+.2f}%",
    ]
    if result.closing_no_vig_probability is not None and opposite is not None:
        implied_taken = float(1 / taken)
        steps += [
            f"No-vig closing probability from {_fmt(closing)} and {_fmt(opposite)} = "
            f"{_pct(result.closing_no_vig_probability)}",
            f"Implied probability of the price taken = 1 / {_fmt(taken)} = {_pct(implied_taken)}",
            f"Probability delta = {_pct(result.closing_no_vig_probability)} - "
            f"{_pct(implied_taken)} = {(result.no_vig_probability_delta or 0) * 100:+.2f} points",
        ]
    else:
        steps.append("No-vig comparison skipped: closing price of the other side not supplied")
    return CLVResponse(
        price=price_out(taken),
        closing_price=price_out(closing),
        clv=round(result.clv_percent / 100, 6),
        clv_percent=round(result.clv_percent, 4),
        beat_close=result.beat_close,
        closing_no_vig_probability=(
            round(result.closing_no_vig_probability, 6)
            if result.closing_no_vig_probability is not None
            else None
        ),
        no_vig_probability_delta=(
            round(result.no_vig_probability_delta, 6)
            if result.no_vig_probability_delta is not None
            else None
        ),
        ev_at_close_percent=(
            round(result.ev_at_close_percent, 4) if result.ev_at_close_percent is not None else None
        ),
        steps=steps,
    )
