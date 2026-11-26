"""Response models of the snapshot archive routes."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from ..api.schemas import EventOddsOut
from ..schemas import DataMode, PriceOut, SportsbookRef

CoverageStatusOut = Literal["captured", "not_captured", "archive_gap", "archive_pruned"]
LegReason = Literal[
    "leg_not_structured",
    "not_captured",
    "archive_gap",
    "archive_pruned",
    "stale_at_placement",
    "no_usable_quote",
    "none_at_your_books",
    "books_unknown",
]


class CoverageOut(BaseModel):
    status: CoverageStatusOut = Field(
        description=(
            "`captured`: the archive holds this event's state from the latest capture at "
            "or before the requested time, at most `snapshot_max_gap_seconds` before it. "
            "`not_captured`: before the first capture, or the event was not in scope then. "
            "`archive_gap`: capture was not running then. `archive_pruned`: the event's "
            "rows from that capture are past retention."
        )
    )
    captured_at: datetime | None = Field(
        default=None,
        description="When the latest event row at or before the requested time was captured.",
    )
    run_id: int | None = None


class ArchivedOutcomeOut(BaseModel):
    key: str
    name: str
    line: float | None = None
    price: PriceOut


class ArchivedQuoteOut(BaseModel):
    """One book's quote as it was stored: the latest row at or before the coverage row."""

    sportsbook: SportsbookRef
    status: Literal["open", "suspended", "unavailable", "closed"] = Field(
        description="The provider's status as captured."
    )
    last_updated: datetime | None = None
    captured_at: datetime
    fetched_at: datetime
    provider: str
    provider_id: str
    outcomes: list[ArchivedOutcomeOut]


class ArchivedOddsOut(BaseModel):
    requested_as_of: datetime
    coverage: CoverageOut
    data_mode: DataMode
    quotes: list[ArchivedQuoteOut]
    odds: EventOddsOut | None = Field(
        default=None,
        description=(
            "The odds comparison as of the requested time, from the same code as the live "
            "board with the stale thresholds in force at capture. Only when the coverage "
            "status is `captured`."
        ),
    )


class ArchivedPropOut(BaseModel):
    sportsbook: SportsbookRef
    event_id: str
    market: str
    status: Literal["open", "suspended", "unavailable", "closed"]
    last_updated: datetime | None = None
    line: float | None = None
    over: PriceOut | None = None
    under: PriceOut | None = None
    captured_at: datetime
    fetched_at: datetime
    provider: str
    provider_id: str


class ArchivedPropsOut(BaseModel):
    requested_as_of: datetime
    data_mode: DataMode
    offers: list[ArchivedPropOut]


class ArchivedStatusEntryOut(BaseModel):
    kind: Literal["lineup", "injury", "news", "weather"]
    status: str
    source: str
    reported_at: datetime | None = None
    captured_at: datetime
    event_id: str | None = None
    team_id: str | None = None
    player_id: str | None = None
    provider: str
    provider_id: str


class ArchivedStatusOut(BaseModel):
    requested_as_of: datetime
    data_mode: DataMode
    entries: list[ArchivedStatusEntryOut] = Field(
        description="The latest record per subject and kind captured at or before the time."
    )


class ArchivedBestOut(BaseModel):
    price: PriceOut
    sportsbook: SportsbookRef
    line: float | None = None
    captured_at: datetime
    last_updated: datetime | None = None


class LegPlacementPriceOut(BaseModel):
    leg_id: str
    position: int
    event_id: str | None = None
    market: str
    outcome_key: str | None = None
    line: float | None = None
    your_price: PriceOut = Field(description="The price recorded on the leg.")
    status: Literal["priced", "cannot_price"]
    reason: LegReason | None = Field(
        default=None,
        description=(
            "Why the leg cannot be priced: `leg_not_structured` (no event, market, outcome "
            "or line to match), a coverage status, `stale_at_placement` (every open quote "
            "was too old when the bet was placed), `no_usable_quote`, or, when a price "
            "existed but not at your books, `none_at_your_books` or `books_unknown` (the "
            "same value as `your_books_reason`; `best_overall` then holds that price). "
            "Null only when priced."
        ),
    )
    coverage: CoverageOut | None = None
    best_overall: ArchivedBestOut | None = None
    best_at_your_books: ArchivedBestOut | None = None
    your_books_reason: Literal["books_unknown", "none_at_your_books"] | None = None


class BetPlacementPricesOut(BaseModel):
    bet_id: str
    placed_at: datetime
    books: list[str] = Field(description="The sportsbook keys counted as your books.")
    books_source: Literal["query", "bets", "none"] = Field(
        description=(
            "`query`: the `books` parameter. `bets`: the books of your own recorded bets "
            "that match a sportsbook of the data provider. `none`: neither."
        )
    )
    data_mode: DataMode
    legs: list[LegPlacementPriceOut]


class ArchiveRowCountsOut(BaseModel):
    odds: int
    props: int
    events: int
    status: int
    runs: int


class ArchiveRunOut(BaseModel):
    kind: str
    captured_at: datetime
    status: str
    rows_written: int
    rows_deleted: int


class ArchiveStatsOut(BaseModel):
    enabled: bool
    approx_bytes: int = Field(
        description=(
            "PostgreSQL: the five tables with their indexes. SQLite: rows times 400 bytes."
        )
    )
    max_bytes: int
    retention_days: int
    keep_days: int
    rows: ArchiveRowCountsOut
    last_runs: list[ArchiveRunOut] = Field(description="The latest run of each kind.")
