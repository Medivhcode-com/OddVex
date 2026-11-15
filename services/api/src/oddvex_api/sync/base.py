"""Provider-independent contract for importing a user's bet history.

A real implementation would wrap a vendor-supported, user-authorized
connection (for example an account-linking aggregator). OddVex never asks for
or stores sportsbook credentials and never scrapes a sportsbook.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable


class SyncProviderError(Exception):
    """A provider call failed. ``retryable`` says whether trying again can help."""

    def __init__(self, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class SyncProviderInfo:
    key: str
    name: str
    description: str
    is_mock: bool
    requires_credentials: bool


@dataclass(frozen=True, slots=True)
class Authorization:
    """Result of the user authorizing a connection. ``state`` must never hold credentials."""

    label: str
    state: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExternalLeg:
    selection: str
    market: str
    odds_decimal: Decimal
    league: str | None = None
    event_label: str | None = None
    line: Decimal | None = None
    closing_odds_decimal: Decimal | None = None
    result: str | None = None


@dataclass(frozen=True, slots=True)
class ExternalBet:
    external_bet_id: str
    bet_type: str
    sportsbook: str
    stake: Decimal
    placed_at: datetime
    legs: tuple[ExternalLeg, ...]
    #: None while the bet is open, otherwise a bet result such as "won".
    result: str | None = None
    payout: Decimal | None = None
    settled_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class FetchResult:
    bets: tuple[ExternalBet, ...]
    #: Provider state to persist after a *successful* import (cursor etc.).
    state: dict[str, Any]


@runtime_checkable
class SyncProvider(Protocol):
    """Read-only import of a user's own bet history."""

    info: SyncProviderInfo

    def authorize(self, options: dict[str, Any], now: datetime) -> Authorization:
        """Complete the (provider-specific) authorization and return connection state."""
        ...

    def fetch_bets(self, state: dict[str, Any], now: datetime) -> FetchResult:
        """Return the account's bets. Raises :class:`SyncProviderError` on failure."""
        ...
