"""Stable internal contract between OddVex and any sports data provider.

Every record carries provenance (``provider``, ``provider_id``, ``fetched_at``)
so that data can always be traced back to where and when it was obtained.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

EventStatus = Literal["upcoming", "live", "final"]
MarketKey = Literal["moneyline", "spread", "total"]
OfferStatus = Literal["open", "suspended", "unavailable", "closed"]

EVENT_MARKETS: tuple[str, ...] = ("moneyline", "spread", "total")


class ProviderRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    provider_id: str
    fetched_at: datetime


class League(ProviderRecord):
    id: str
    key: str
    name: str
    sport: str
    has_draw: bool
    markets: list[str]
    prop_markets: list[str]


class Sportsbook(ProviderRecord):
    id: str
    key: str
    name: str


class Team(ProviderRecord):
    id: str
    league: str
    name: str
    city: str
    nickname: str
    abbreviation: str


class Player(ProviderRecord):
    id: str
    league: str
    team_id: str
    name: str
    position: str
    jersey_number: int
    prop_markets: list[str]


class Score(BaseModel):
    model_config = ConfigDict(frozen=True)

    home: int
    away: int


class Event(ProviderRecord):
    id: str
    league: str
    home_team_id: str
    away_team_id: str
    start_time: datetime
    status: EventStatus
    score: Score | None = None
    period_text: str | None = None
    markets: list[str]


class OddsOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    name: str
    line: float | None = None
    price_american: int


class OddsSnapshot(ProviderRecord):
    """One sportsbook's current quote for one market of one event."""

    event_id: str
    market: str
    sportsbook_id: str
    status: OfferStatus
    last_updated: datetime | None
    outcomes: list[OddsOutcome]


class LinePoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    price_american: int
    line: float | None = None


class LineSeries(ProviderRecord):
    event_id: str
    market: str
    sportsbook_id: str
    outcome_key: str
    outcome_name: str
    points: list[LinePoint]


class GameLogEntry(ProviderRecord):
    player_id: str
    event_id: str
    game_time: datetime
    opponent_team_id: str
    is_home: bool
    stats: dict[str, float]


class PropOffer(ProviderRecord):
    player_id: str
    event_id: str
    market: str
    sportsbook_id: str
    status: OfferStatus
    last_updated: datetime | None
    line: float | None = None
    over_american: int | None = None
    under_american: int | None = None


class ProviderHealth(BaseModel):
    provider: str
    data_mode: str
    status: Literal["ok", "degraded", "down"]
    checked_at: datetime
    detail: str


@runtime_checkable
class SportsDataProvider(Protocol):
    """Read-only sports data source. Implementations must not place wagers."""

    name: str
    data_mode: str

    def now(self) -> datetime: ...

    def health(self) -> ProviderHealth: ...

    def list_leagues(self) -> list[League]: ...

    def list_sportsbooks(self) -> list[Sportsbook]: ...

    def list_teams(self, league: str | None = None) -> list[Team]: ...

    def get_team(self, team_id: str) -> Team | None: ...

    def list_players(
        self, league: str | None = None, team_id: str | None = None, query: str | None = None
    ) -> list[Player]: ...

    def get_player(self, player_id: str) -> Player | None: ...

    def list_events(
        self,
        league: str | None = None,
        status: str | None = None,
        on_date: date | None = None,
    ) -> list[Event]: ...

    def get_event(self, event_id: str) -> Event | None: ...

    def get_odds(self, event_id: str, market: str) -> list[OddsSnapshot]: ...

    def get_line_history(self, event_id: str, market: str) -> list[LineSeries]: ...

    def get_player_game_log(self, player_id: str, limit: int | None = None) -> list[GameLogEntry]: ...

    def next_event_for_team(self, team_id: str) -> Event | None: ...

    def get_prop_offers(self, player_id: str, market: str | None = None) -> list[PropOffer]: ...
