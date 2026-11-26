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
            "rows from that capture are past retention, or the time is at or before the "
            "keep horizon, where the archive no longer answers."
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
    """One book's quote as it was stored: the latest row at or before the coverage row.
    Quotes are returned only when the coverage status is `captured`."""

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
    quotes: list[ArchivedQuoteOut] = Field(
        description=(
            "Each book's stored quote from the covering capture. Empty unless the coverage "
            "status is `captured`: an older kept capture is not the market at that time."
        )
    )
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


class PropsCoverageOut(BaseModel):
    status: CoverageStatusOut = Field(
        description=(
            "Read from the latest successful props capture at or before the requested time. "
            "`captured`: it is at most two props intervals plus one worker turn before it "
            "(7,320 s with hourly props). `archive_gap`: it is older. `not_captured`: before "
            "the first props capture. `archive_pruned`: the look-back before the time (48 hours "
            "with the default settings) reaches "
            "past the keep horizon. Offers are returned only when `captured`."
        )
    )
    captured_at: datetime | None = Field(
        default=None,
        description="When the latest successful props capture at or before the time ran.",
    )


class ArchivedPropsOut(BaseModel):
    requested_as_of: datetime
    data_mode: DataMode
    coverage: PropsCoverageOut
    offers: list[ArchivedPropOut]
    pruned_event_ids: list[str] = Field(
        default_factory=list,
        description=(
            "The player's games whose offers at the requested time cannot be read back "
            "exactly, because the retention prune kept only their closing offers. Their "
            "offers are left out of `offers`."
        ),
    )


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


class StatusCoverageOut(BaseModel):
    status: Literal["captured", "not_captured", "archive_pruned"] = Field(
        description=(
            "`captured`: the archive holds status records of the event captured at or "
            "before the requested time, and `entries` is the latest of each. "
            "`not_captured`: it holds none. `archive_pruned`: it holds none and the time "
            "is before `kept_from`, so they may have been removed."
        )
    )
    captured_at: datetime | None = Field(
        default=None, description="When the newest of the entries was captured."
    )
    kept_from: datetime | None = Field(
        default=None,
        description=(
            "Status records are kept 400 days. A record that had not changed since before "
            "this time has been removed and is not among `entries`. Null before the "
            "first prune."
        ),
    )


class ArchivedStatusOut(BaseModel):
    requested_as_of: datetime
    data_mode: DataMode
    coverage: StatusCoverageOut
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
    kind: str = Field(description="`odds`, `props`, `status`, `prune` or `reclaim`.")
    captured_at: datetime
    status: str = Field(
        description=(
            "`ok`, `skipped_full` (capture stopped at a limit) or `failed`. A prune is "
            "recorded when it starts (`started`) and again when it ends: `started` as the "
            "latest prune means one is running, or was cut short and will be finished by "
            "the next pass."
        )
    )
    rows_written: int
    rows_deleted: int
    finished_at: datetime | None = Field(default=None, description="Wall-clock time the run ended.")
    indexes_rebuilt: int | None = Field(
        default=None, description="`reclaim` runs: indexes rebuilt to return space to the disk."
    )
    indexes_dropped: int | None = Field(
        default=None,
        description="`reclaim` runs: invalid indexes an interrupted rebuild had left, dropped.",
    )
    indexes_failed: int | None = Field(
        default=None,
        description="`reclaim` runs: rebuilds or drops that failed and wait for a later pass.",
    )
    bytes_freed: int | None = Field(
        default=None, description="`reclaim` runs: bytes the run returned to the disk."
    )


class ArchiveStatsOut(BaseModel):
    enabled: bool
    approx_bytes: int = Field(
        description=(
            "The data the archive holds, as the storage cap counts it: each table's row "
            "count times its measured bytes per row. It falls when the prune deletes rows."
        )
    )
    disk_bytes: int | None = Field(
        default=None,
        description=(
            "PostgreSQL only: the size of the five tables' files with their indexes. The "
            "table files do not shrink after the prune (later rows reuse the freed space); "
            "the index files shrink when a `reclaim` run rebuilds them."
        ),
    )
    max_bytes: int
    max_disk_bytes: int = Field(
        description="PostgreSQL only: capture also stops while `disk_bytes` is at this ceiling."
    )
    retention_days: int
    keep_days: int
    rows: ArchiveRowCountsOut
    last_runs: list[ArchiveRunOut] = Field(
        description=(
            "The latest run of each kind. A `reclaim` run is recorded only when it rebuilt "
            "or dropped an index or failed, so the latest one is the last time index "
            "space was returned to the disk."
        )
    )
