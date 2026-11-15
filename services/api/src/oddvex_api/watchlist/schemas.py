from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from ..api.schemas import EventSummaryOut, PlayerOut
from ..schemas import TeamRef

WatchlistKind = Literal["team", "player", "event"]

MAX_WATCHLIST_ITEMS = 200


class WatchlistItemCreate(BaseModel):
    kind: WatchlistKind
    ref_id: str = Field(
        min_length=1, max_length=64, description="Team, player or event id from the data routes."
    )


class WatchlistItemOut(BaseModel):
    id: str
    kind: WatchlistKind
    ref_id: str
    label: str = Field(description="Display name captured when the item was added.")
    league: str | None = None
    created_at: datetime
    available: bool = Field(
        default=True,
        description=(
            "False when the data provider no longer has the referenced entity (for example "
            "an old event). `team`, `player` and `event` are then all null."
        ),
    )
    team: TeamRef | None = None
    player: PlayerOut | None = None
    event: EventSummaryOut | None = None


class WatchlistOut(BaseModel):
    items: list[WatchlistItemOut]
