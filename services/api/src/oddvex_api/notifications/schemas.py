"""Request and response models for notifications, their preferences and the staking reminder."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

NotificationKind = Literal[
    "price_alert",
    "line_move",
    "game_start",
    "game_final",
    "bet_settled",
    "sync_finished",
    "stake_reminder",
]
NOTIFICATION_KINDS: tuple[str, ...] = get_args(NotificationKind)

MAX_NOTIFICATIONS = 500
MAX_WEEKLY_STAKE_THRESHOLD = 1_000_000


class NotificationOut(BaseModel):
    id: str
    kind: NotificationKind
    title: str
    body: str
    href: str | None = Field(
        default=None,
        description="Web route to open, e.g. `/app/games/{event_id}?market=spread`.",
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Small object for deep links; the keys depend on `kind` (`event_id`, `alert_id`, "
            "`market`, `price_american`, `line`, `bet_id`, `run_id`, ...)."
        ),
    )
    created_at: datetime
    read_at: datetime | None = None


class NotificationListOut(BaseModel):
    items: list[NotificationOut]
    unread_count: int = Field(description="All of your unread notifications, not just this page.")
    next_before: str | None = Field(
        default=None,
        description="Pass as `before` to get the next (older) page. Null on the last page.",
    )


class UnreadCountOut(BaseModel):
    unread_count: int


class MarkAllReadOut(BaseModel):
    updated: int = Field(description="Notifications that were unread and are now read.")


class InAppPreferencesOut(BaseModel):
    """One switch per notification kind. All default to true."""

    price_alert: bool = True
    line_move: bool = True
    game_start: bool = True
    game_final: bool = True
    bet_settled: bool = True
    sync_finished: bool = True
    stake_reminder: bool = True


class NotificationPreferencesOut(BaseModel):
    in_app: InAppPreferencesOut = Field(
        description=(
            "In-app delivery per kind. A disabled kind creates no notification; alert rules "
            "still change state."
        )
    )


class InAppPreferencesIn(BaseModel):
    """Kinds left out keep their current value."""

    model_config = ConfigDict(extra="forbid")

    price_alert: bool | None = None
    line_move: bool | None = None
    game_start: bool | None = None
    game_final: bool | None = None
    bet_settled: bool | None = None
    sync_finished: bool | None = None
    stake_reminder: bool | None = None


class NotificationPreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    in_app: InAppPreferencesIn


class StakeReminderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weekly_stake_threshold: float | None = Field(
        gt=0,
        le=MAX_WEEKLY_STAKE_THRESHOLD,
        description="Total stake per week at which you want a reminder. Null turns it off.",
    )


class StakeReminderOut(BaseModel):
    """A reminder, never a limit: bets are always saved."""

    weekly_stake_threshold: float | None = Field(
        default=None, description="Null means the reminder is off."
    )
    staked_this_week: float = Field(
        description=(
            "Sum of the stakes of your bets placed in the current ISO week (Monday to "
            "Sunday, UTC). Void bets are excluded."
        )
    )
    week_start: datetime = Field(description="Monday 00:00 UTC of the current week.")
    exceeded: bool = Field(
        description="True when a threshold is set and `staked_this_week` is at or above it."
    )
