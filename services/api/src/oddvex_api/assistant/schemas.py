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
    "support",
]

AssistantSupportCase = Literal["crisis", "distress", "underage"]


class AssistantQueryRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)


class AssistantSourceOut(BaseModel):
    label: str
    as_of: datetime
    data_mode: str = Field(description="synthetic | calculation | user")


class AssistantSuggestionOut(BaseModel):
    label: str
    href: str = Field(
        description=(
            "A web route: an app screen such as /app/games/{event_id}, /login, or the "
            "/responsible-gambling page."
        )
    )


class AssistantSupportOut(BaseModel):
    case: AssistantSupportCase = Field(
        description=(
            "Which responsible-gambling reply this is. crisis: self-harm or crisis language; "
            "the answer gives only the 988 line, 911 and the gambling helpline. distress: "
            "distress about gambling; the answer gives the helpline and the app's own "
            "reminder and tracking tools. underage: the user said they are under 21; the "
            "answer says OddVex is for adults 21 and over."
        )
    )


class AssistantResponse(BaseModel):
    intent: AssistantIntent
    answer: str = Field(
        description=(
            "The reply. Every answer that is not a support reply ends with one sentence giving "
            "the gambling helpline and the crisis line."
        )
    )
    data: dict[str, Any] | None = Field(
        default=None,
        description="The structured facts the answer was written from. Null when none apply.",
    )
    sources: list[AssistantSourceOut]
    suggestions: list[AssistantSuggestionOut]
    disclaimer: str
    support: AssistantSupportOut | None = Field(
        default=None,
        description=(
            "Set when the answer is a responsible-gambling support reply (intent support), "
            "so a client can present it differently. Such an answer has no data and no "
            "sources. Null for every other answer."
        ),
    )
