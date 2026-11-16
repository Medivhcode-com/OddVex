"""Response models for the sports-data routes (events, odds, players, props)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from ..schemas import BestPriceOut, PriceOut, SportsbookRef, TeamRef

LeagueKey = Literal["nba", "nfl", "mlb", "nhl", "soccer"]
EventStatus = Literal["live", "upcoming", "final"]
EventMarket = Literal["moneyline", "spread", "total"]
BookStatus = Literal["open", "suspended", "unavailable"]
PropWindow = Literal["5", "10", "20", "season"]
PropSplit = Literal["all", "home", "away", "vs_opponent"]
DataMode = Literal["synthetic"]


class HealthOut(BaseModel):
    status: Literal["ok"]
    version: str
    data_mode: DataMode
    server_time: datetime


class MetaOut(BaseModel):
    data_mode: DataMode = Field(description="All sports data is synthetic in this build.")
    provider: str
    version: str
    server_time: datetime
    notice: str = Field(description="Plain-language statement about the data shown.")


class LeagueOut(BaseModel):
    key: LeagueKey
    name: str
    sport: str
    has_draw: bool = Field(description="True when the moneyline is 3-way (home/draw/away).")
    markets: list[EventMarket]
    prop_markets: list[str]


class SportsbookOut(BaseModel):
    key: str
    name: str


class ScoreOut(BaseModel):
    home: int
    away: int


class BestMoneylineOut(BaseModel):
    """Best open, non-stale moneyline price per side. ``draw`` is only set for 3-way markets."""

    home: BestPriceOut | None = None
    away: BestPriceOut | None = None
    draw: BestPriceOut | None = None


class EventSummaryOut(BaseModel):
    id: str
    league: LeagueKey
    home_team: TeamRef
    away_team: TeamRef
    start_time: datetime
    status: EventStatus
    score: ScoreOut | None = None
    status_detail: str | None = Field(
        default=None, description='Period / clock text for live events, "Final" for finished ones.'
    )
    best_moneyline: BestMoneylineOut | None = None


class PlayerOut(BaseModel):
    id: str
    name: str
    league: LeagueKey
    team: TeamRef
    position: str
    jersey_number: int
    prop_markets: list[str]


class EventDetailOut(EventSummaryOut):
    league_name: str
    has_draw: bool
    available_markets: list[EventMarket]
    players: list[PlayerOut] = Field(description="Players on either team with prop research.")
    as_of: datetime
    data_mode: DataMode


class OddsOutcomeOut(BaseModel):
    key: str = Field(description="home | away | draw | over | under")
    name: str
    line: float | None = None
    price: PriceOut
    is_best: bool = Field(
        description=(
            "Best price for this outcome among open, non-stale books. For spread and total "
            "only books quoting the consensus line are compared."
        )
    )


class BookOddsOut(BaseModel):
    sportsbook: SportsbookRef
    status: BookStatus
    last_updated: datetime | None = None
    is_stale: bool
    outcomes: list[OddsOutcomeOut]


class ConsensusOutcomeOut(BaseModel):
    key: str
    name: str
    no_vig_probability: float = Field(
        description="Mean of each book's no-vig (proportional) probability. Not a prediction."
    )


class ConsensusOut(BaseModel):
    outcomes: list[ConsensusOutcomeOut]
    books_used: int
    line: float | None = Field(
        default=None,
        description=(
            "Most common line among open, non-stale books (home line for spread, total "
            "points for totals). Null for moneyline."
        ),
    )


class BookHoldOut(BaseModel):
    sportsbook_key: str
    hold: float = Field(description="1 - 1/sum(implied probabilities), as a fraction.")


class BestOutcomeOut(BaseModel):
    outcome_key: str
    sportsbook_key: str
    price: PriceOut
    line: float | None = None


class EventOddsOut(BaseModel):
    event: EventSummaryOut
    market: EventMarket
    as_of: datetime
    data_mode: DataMode
    stale_after_seconds: int = Field(
        description="Quotes older than this are flagged stale and excluded from best price."
    )
    books: list[BookOddsOut]
    consensus: ConsensusOut
    holds: list[BookHoldOut]
    best: list[BestOutcomeOut]


class LinePointOut(BaseModel):
    timestamp: datetime
    line: float | None = None
    price: PriceOut


class LineSeriesOut(BaseModel):
    sportsbook: SportsbookRef
    outcome_key: str
    outcome_name: str
    points: list[LinePointOut]


class LineHistoryOut(BaseModel):
    event: EventSummaryOut
    market: EventMarket
    as_of: datetime
    data_mode: DataMode
    series: list[LineSeriesOut]


class PlayerDetailOut(PlayerOut):
    next_event: EventSummaryOut | None = None
    opponent: TeamRef | None = None
    as_of: datetime
    data_mode: DataMode


class PropOfferOut(BaseModel):
    sportsbook: SportsbookRef
    status: BookStatus
    line: float | None = None
    over: PriceOut | None = None
    under: PriceOut | None = None
    last_updated: datetime | None = None
    is_stale: bool
    is_best_over: bool
    is_best_under: bool


class GameLogEntryOut(BaseModel):
    event_id: str
    date: datetime
    opponent: TeamRef
    is_home: bool
    value: float
    result: Literal["over", "under", "push"] = Field(
        description="The stat value compared with ``hit_rate.line``."
    )


class HitRateOut(BaseModel):
    line: float = Field(description="The line the game log was graded against.")
    line_source: Literal["consensus", "season_median"] = Field(
        description=(
            "consensus: the most common line currently offered. season_median: no book is "
            "offering the market, so the half-point nearest the season median is used."
        )
    )
    over_count: int
    under_count: int
    pushes: int = Field(description="Games that landed exactly on the line; excluded from rate.")
    sample_size: int = Field(description="Games counted in the rate (pushes excluded).")
    rate: float | None = Field(
        default=None, description="over_count / sample_size. Historical frequency only."
    )
    ci_low: float | None = Field(default=None, description="Wilson 95% interval, lower bound.")
    ci_high: float | None = Field(default=None, description="Wilson 95% interval, upper bound.")


class AveragesOut(BaseModel):
    window: float | None = Field(default=None, description="Mean over the returned game log.")
    season: float | None = None
    home: float | None = None
    away: float | None = None
    vs_opponent: float | None = None


class PlayerPropsOut(BaseModel):
    player: PlayerOut
    market: str
    available_markets: list[str]
    window: PropWindow
    split: PropSplit
    next_event: EventSummaryOut | None = None
    opponent: TeamRef | None = None
    offers: list[PropOfferOut]
    consensus_line: float | None = None
    game_log: list[GameLogEntryOut]
    hit_rate: HitRateOut
    averages: AveragesOut
    caveat: str
    as_of: datetime
    data_mode: DataMode


class PropBoardRowOut(BaseModel):
    player: PlayerOut
    event: EventSummaryOut
    market: str
    consensus_line: float | None = None
    best_over: BestPriceOut | None = None
    best_under: BestPriceOut | None = None
    l10_hit_rate: float | None = Field(
        default=None,
        description="Share of the last 10 games over the consensus line. Not a prediction.",
    )
    l10_over_count: int
    l10_sample: int = Field(description="Games in the last-10 rate (pushes excluded).")


# --------------------------------------------------------------- value screen
class ValueRowOut(BaseModel):
    event: EventSummaryOut
    market: EventMarket
    outcome_key: str
    outcome_name: str
    line: float | None = Field(
        default=None, description="The line this outcome is quoted at (spread and total)."
    )
    best_price: PriceOut = Field(description="Best open, non-stale price for the outcome.")
    sportsbook: SportsbookRef = Field(description="The sportsbook offering that price.")
    consensus_probability: float = Field(
        description=(
            "Mean no-vig probability of the outcome over the other books at the same line. "
            "The sportsbook with the best price is not part of it."
        )
    )
    books_in_consensus: int = Field(description="Books in that mean (at least 2).")
    edge: float = Field(
        description=(
            "Expected value per 1 unit staked at the best price if the consensus "
            "probability were the true probability, as a fraction. Not a forecast."
        )
    )
    breakeven_probability: float = Field(
        description="1 / decimal price: the probability at which the best price has zero EV."
    )
    last_updated: datetime | None = Field(
        default=None, description="When the sportsbook last updated the best price."
    )
    stale_after_seconds: int = Field(
        description="A quote older than this is stale and is not on this screen."
    )


class ValueScreenOut(BaseModel):
    rows: list[ValueRowOut] = Field(description="Largest edge first.")
    min_edge: float
    as_of: datetime
    data_mode: DataMode
    method: str = Field(description="How the numbers are computed.")
    caveat: str = Field(description="What this screen does not tell you.")
