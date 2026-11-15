"""Request and response models for the bet tracker."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from ..schemas import OddsFormatIn, OddsValue, PriceOut

BetType = Literal["straight", "parlay", "sgp", "future"]
BetStatus = Literal["pending", "settled"]
BetResult = Literal["won", "lost", "push", "void", "half_won", "half_lost", "cashout"]
LegResult = Literal["won", "lost", "push", "void", "half_won", "half_lost"]
BetSource = Literal["manual", "sync"]
BetStatusFilter = Literal[
    "pending", "settled", "won", "lost", "push", "void", "half_won", "half_lost", "cashout"
]

OutcomeKey = Literal["home", "away", "draw", "over", "under"]
SettledBy = Literal["user", "auto"]
BetSort = Literal["placed_at", "-placed_at", "stake", "-stake", "profit", "-profit"]
AutoSettleSkipReason = Literal[
    "not_gradeable", "event_not_final", "event_unavailable", "manual_result_required"
]

MAX_STAKE = 1_000_000


class BetLegIn(BaseModel):
    selection: str = Field(min_length=1, max_length=200, examples=["Harbor City Tides -3.5"])
    market: str = Field(min_length=1, max_length=40, examples=["spread"])
    league: str | None = Field(default=None, max_length=32, examples=["nba"])
    event_id: str | None = Field(default=None, max_length=64)
    event_label: str | None = Field(default=None, max_length=200)
    line: float | None = Field(
        default=None,
        ge=-100000,
        le=100000,
        description=(
            "Spread: the handicap of the selected side (home -3.5 is `-3.5`, the away side "
            "of that market is `+3.5`). Total: the points line."
        ),
    )
    outcome_key: OutcomeKey | None = Field(
        default=None,
        description=(
            "Structured selection. With `event_id`, a `market` of moneyline, spread or total "
            "and (for spread and total) `line`, the leg can be graded automatically from the "
            "final score. moneyline: home, away, or draw where the league has a 3-way "
            "market. spread: home or away. total: over or under."
        ),
    )
    odds: OddsValue = Field(examples=[-110, "+150", 2.5, "5/2"])
    odds_format: OddsFormatIn = "american"
    closing_odds: OddsValue | None = Field(
        default=None, description="Closing price of the same selection, in `odds_format`."
    )
    closing_opposite_odds: OddsValue | None = Field(
        default=None, description="Closing price of the other side (enables no-vig CLV)."
    )


def _check_leg_count(bet_type: str, count: int) -> None:
    if bet_type in ("straight", "future") and count != 1:
        raise ValueError(f"a {bet_type} bet has exactly one leg")
    if bet_type in ("parlay", "sgp") and count < 2:
        raise ValueError(f"a {bet_type} bet needs at least two legs")


class BetCreate(BaseModel):
    bet_type: BetType = "straight"
    legs: list[BetLegIn] = Field(min_length=1, max_length=20)
    stake: float = Field(gt=0, le=MAX_STAKE)
    sportsbook: str = Field(min_length=1, max_length=80)
    placed_at: AwareDatetime | None = Field(default=None, description="Defaults to now.")
    notes: str | None = Field(default=None, max_length=2000)
    odds: OddsValue | None = Field(
        default=None,
        description=(
            "Optional price for the whole bet, for when the book's price differs from the "
            "product of the legs (typical for same-game parlays)."
        ),
    )
    odds_format: OddsFormatIn = "american"

    @model_validator(mode="after")
    def _legs_match_type(self) -> BetCreate:
        _check_leg_count(self.bet_type, len(self.legs))
        return self


class LegClosingOddsIn(BaseModel):
    leg_id: str
    closing_odds: OddsValue
    closing_opposite_odds: OddsValue | None = None
    odds_format: OddsFormatIn = "american"


class BetUpdate(BaseModel):
    """Partial update. Stake, legs, odds and bet type can only change while the bet is pending."""

    bet_type: BetType | None = None
    legs: list[BetLegIn] | None = Field(default=None, min_length=1, max_length=20)
    stake: float | None = Field(default=None, gt=0, le=MAX_STAKE)
    sportsbook: str | None = Field(default=None, min_length=1, max_length=80)
    placed_at: AwareDatetime | None = None
    notes: str | None = Field(default=None, max_length=2000)
    odds: OddsValue | None = None
    odds_format: OddsFormatIn = "american"
    closing_odds: list[LegClosingOddsIn] | None = Field(
        default=None, description="Record closing prices on existing legs (allowed any time)."
    )


class LegResultIn(BaseModel):
    leg_id: str
    result: LegResult


class BetSettleRequest(BaseModel):
    result: BetResult | None = Field(
        default=None,
        description="Required unless `leg_results` grades every leg of a multi-leg bet.",
    )
    cashout_amount: float | None = Field(
        default=None, ge=0, le=100_000_000, description="Amount returned. Required for cashout."
    )
    leg_results: list[LegResultIn] | None = Field(
        default=None,
        description=(
            "Per-leg results. For a parlay priced from its legs the bet result and payout are "
            "derived from them (pushed and void legs drop out)."
        ),
    )
    settled_at: AwareDatetime | None = Field(default=None, description="Defaults to now.")

    @model_validator(mode="after")
    def _needs_something(self) -> BetSettleRequest:
        if self.result is None and not self.leg_results:
            raise ValueError("provide a result or leg_results")
        if self.result == "cashout" and self.cashout_amount is None:
            raise ValueError("cashout_amount is required when result is cashout")
        return self


class BetLegOut(BaseModel):
    id: str
    position: int
    selection: str
    market: str
    league: str | None = None
    event_id: str | None = None
    event_label: str | None = None
    line: float | None = None
    price: PriceOut
    closing_price: PriceOut | None = None
    clv: float | None = Field(
        default=None, description="decimal_taken / decimal_closing - 1, as a fraction."
    )
    result: LegResult | None = None
    outcome_key: OutcomeKey | None = None
    gradeable: bool = Field(
        default=False,
        description="True when the leg has event_id, a gradeable market, outcome_key and line.",
    )


class BetOut(BaseModel):
    id: str
    bet_type: BetType
    status: BetStatus
    result: BetResult | None = None
    sport: str = Field(description='League shared by every leg, "multi", or "unknown".')
    sportsbook: str
    stake: float
    combined_price: PriceOut
    combined_decimal_odds: float
    odds_source: Literal["legs", "override"] = Field(
        description="legs: product of the leg prices. override: a price supplied for the bet."
    )
    potential_payout: float = Field(description="Stake x combined decimal odds.")
    potential_profit: float
    payout: float | None = Field(default=None, description="Amount returned once settled.")
    profit: float | None = None
    clv: float | None = Field(
        default=None,
        description="Closing line value as a fraction; null unless every leg has a closing price.",
    )
    notes: str | None = None
    placed_at: datetime
    settled_at: datetime | None = None
    settled_by: SettledBy | None = Field(
        default=None,
        description=(
            "user: settled by hand. auto: graded from final scores by auto-settle. Null "
            "while pending and for bets that were imported already settled."
        ),
    )
    source: BetSource
    sync_connection_id: str | None = None
    external_bet_id: str | None = None
    legs: list[BetLegOut]
    created_at: datetime
    updated_at: datetime


class AutoSettleSkipOut(BaseModel):
    bet_id: str
    reason: AutoSettleSkipReason = Field(
        description=(
            "not_gradeable: a leg has no structured selection. event_not_final: a leg's "
            "event has not finished. event_unavailable: the data provider no longer has a "
            "leg's event. manual_result_required: the bet carries its own price and a leg "
            "pushed, so the payout cannot be derived."
        )
    )


class AutoSettleOut(BaseModel):
    checked: int = Field(description="Pending bets examined.")
    settled: list[BetOut]
    skipped: list[AutoSettleSkipOut]


class BetTotalsOut(BaseModel):
    staked: float = Field(description="Total staked on settled bets, void bets excluded.")
    profit: float
    roi: float | None = Field(default=None, description="profit / staked, as a fraction.")
    wins: int = Field(description="Settled bets with a positive profit.")
    losses: int = Field(description="Settled bets with a negative profit.")
    pushes: int = Field(description="Settled bets with zero profit (pushes and voids).")
    pending_count: int
    pending_exposure: float = Field(description="Total stake on pending bets.")
    avg_clv: float | None = Field(
        default=None, description="Mean CLV (fraction) over bets that have closing prices."
    )
    clv_sample: int = Field(description="Bets included in avg_clv.")
    settled_count: int


class BreakdownRowOut(BaseModel):
    key: str
    bets: int
    staked: float
    profit: float
    roi: float | None = None


class TimelinePointOut(BaseModel):
    date: date
    cumulative_profit: float


class BetSummaryOut(BaseModel):
    totals: BetTotalsOut
    by_sport: list[BreakdownRowOut]
    by_market: list[BreakdownRowOut]
    by_sportsbook: list[BreakdownRowOut]
    by_bet_type: list[BreakdownRowOut]
    timeline: list[TimelinePointOut] = Field(
        description="Cumulative profit by settlement date (UTC), oldest first."
    )
    note: str
