"""Request and response models for alert rules."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..api.schemas import EventSummaryOut
from ..bets.schemas import OutcomeKey
from ..schemas import OddsFormatIn, OddsValue, PriceOut, TeamRef

AlertKind = Literal["price_at_least", "line_move", "game_start", "game_final"]
AlertState = Literal["active", "triggered", "expired", "paused"]
AlertMarket = Literal["moneyline", "spread", "total"]
LineMarket = Literal["spread", "total"]

MAX_ACTIVE_ALERTS = 100
#: Rules of any state kept per user, so triggered and expired rules cannot pile up forever.
MAX_TOTAL_ALERTS = 500
MIN_MINUTES_BEFORE = 5
MAX_MINUTES_BEFORE = 1440

_EVENT_ID = Field(min_length=1, max_length=64, description="Event id from the data routes.")
_TEAM_ID = Field(min_length=1, max_length=64, description="Team id from the data routes.")


class _AlertCreateBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PriceAtLeastAlertCreate(_AlertCreateBase):
    """Fires when the best open, non-stale price for the outcome is at or above `threshold`."""

    kind: Literal["price_at_least"]
    event_id: str = _EVENT_ID
    market: AlertMarket
    outcome_key: OutcomeKey = Field(
        description="moneyline: home, away (or draw where 3-way). spread: home, away. "
        "total: over, under."
    )
    line: float | None = Field(
        default=None,
        ge=-100000,
        le=100000,
        description=(
            "Required for spread and total, not allowed for moneyline. Spread: the handicap "
            "of the selected side. Only books quoting exactly this line are compared."
        ),
    )
    threshold: OddsValue = Field(
        description="The price to reach, in `odds_format`.", examples=[150, "+150", 2.5, "3/2"]
    )
    odds_format: OddsFormatIn = "american"


class LineMoveAlertCreate(_AlertCreateBase):
    """Fires when the consensus line is `min_move` points or more away from where it was
    when the alert was created, in either direction."""

    kind: Literal["line_move"]
    event_id: str = _EVENT_ID
    market: LineMarket
    outcome_key: OutcomeKey = Field(description="spread: home, away. total: over, under.")
    min_move: float = Field(gt=0, le=1000, description="Points.", examples=[1, 1.5])


class _GameAlertCreate(_AlertCreateBase):
    event_id: str | None = Field(default=None, min_length=1, max_length=64)
    team_id: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def _one_subject(self) -> _GameAlertCreate:
        if (self.event_id is None) == (self.team_id is None):
            raise ValueError("provide exactly one of event_id and team_id")
        return self


class GameStartAlertCreate(_GameAlertCreate):
    """Fires when a matching upcoming event starts within `minutes_before` minutes. With
    `team_id` it fires once for each of the team's games and stays active."""

    kind: Literal["game_start"]
    minutes_before: int = Field(ge=MIN_MINUTES_BEFORE, le=MAX_MINUTES_BEFORE)


class GameFinalAlertCreate(_GameAlertCreate):
    """Fires with the final score when a matching event ends. With `team_id` it fires once
    for each of the team's games and stays active."""

    kind: Literal["game_final"]


AlertCreate = Annotated[
    PriceAtLeastAlertCreate | LineMoveAlertCreate | GameStartAlertCreate | GameFinalAlertCreate,
    Field(discriminator="kind"),
]


class AlertUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: Literal["active", "paused"] = Field(
        description=(
            "paused: stop evaluating an active rule. active: resume a paused rule, or re-arm "
            "a triggered one (a line_move rule then takes the current consensus line as its "
            "new baseline)."
        )
    )


class AlertRuleOut(BaseModel):
    id: str
    kind: AlertKind
    state: AlertState = Field(
        description=(
            "active: being evaluated. triggered: fired once and stopped. expired: the event "
            "ended or is no longer available before the rule fired. paused: switched off by "
            "you. Team-scoped rules stay active after firing."
        )
    )
    summary: str = Field(description="One-line, human-readable description of the rule.")
    event_id: str | None = None
    team_id: str | None = None
    market: AlertMarket | None = None
    outcome_key: OutcomeKey | None = None
    line: float | None = None
    threshold: PriceOut | None = Field(default=None, description="price_at_least only.")
    min_move: float | None = Field(default=None, description="line_move only, in points.")
    baseline_line: float | None = Field(
        default=None, description="line_move only: the consensus line when the rule was armed."
    )
    minutes_before: int | None = Field(default=None, description="game_start only.")
    label: str = Field(description="Event or team name captured when the rule was created.")
    league: str | None = None
    created_at: datetime
    updated_at: datetime
    triggered_at: datetime | None = None
    available: bool = Field(
        default=True,
        description="False when the data provider no longer has the event or team.",
    )
    event: EventSummaryOut | None = None
    team: TeamRef | None = None


class AlertListOut(BaseModel):
    items: list[AlertRuleOut]


class AlertEvaluationOut(BaseModel):
    evaluated: int = Field(description="Active rules that were checked.")
    fired: int = Field(description="Times a rule's condition was met in this run.")
    expired: int = Field(description="Rules that expired in this run.")
