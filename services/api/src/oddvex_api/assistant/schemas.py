from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

AssistantIntent = Literal[
    "compare_odds",
    "explain_ev",
    "explain_no_vig",
    "player_trend",
    "line_movement",
    "bet_summary",
    "help",
    "fallback",
]


class AssistantQueryRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)


class AssistantSourceOut(BaseModel):
    label: str
    as_of: datetime
    data_mode: str = Field(description="synthetic | calculation | user")


class AssistantSuggestionOut(BaseModel):
    label: str
    href: str = Field(description="A web app route, e.g. /app/games/{event_id}.")


class AssistantResponse(BaseModel):
    intent: AssistantIntent
    answer: str
    data: dict[str, Any] | None = Field(
        default=None,
        description="The structured facts the answer was written from. Null when none apply.",
    )
    sources: list[AssistantSourceOut]
    suggestions: list[AssistantSuggestionOut]
    disclaimer: str
