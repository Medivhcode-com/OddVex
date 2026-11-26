"""Snapshot archive routes (P0.1). Additive, read-only.

Every user route needs sign-in and answers ``404 feature_disabled`` while the
``snapshot_archive`` flag is off. The placement-price route is owner-scoped: another
user's bet answers 404 exactly like a missing one. The admin statistics route is not
behind the flag, so an administrator can see the archive's size whatever its state.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request

from ..api.admin import audit_admin_read
from ..api.schemas import EventMarket
from ..db import Bet
from ..deps import AdminDep, CurrentUserDep, DbDep, ProviderDep, SettingsDep
from ..errors import AUTH_ERROR_RESPONSES, ApiError, ErrorResponse, not_found
from ..flags.service import require_flag
from ..providers.base import MAX_CLOCK_SKEW_SECONDS
from . import service
from .capture import FLAG
from .placement import placement_prices, resolve_books
from .schemas import (
    ArchivedOddsOut,
    ArchivedPropsOut,
    ArchivedStatusOut,
    ArchiveStatsOut,
    BetPlacementPricesOut,
)
from .view import ArchiveBusy

_FLAGGED: dict[int | str, dict[str, Any]] = {
    **AUTH_ERROR_RESPONSES,
    404: {"model": ErrorResponse, "description": "The feature is switched off, or not found"},
}
router = APIRouter(tags=["archive"], responses=_FLAGGED)
admin_router = APIRouter(prefix="/admin", tags=["admin"], responses=AUTH_ERROR_RESPONSES)
_FLAG = [Depends(require_flag(FLAG))]

AsOfQuery = Annotated[
    datetime,
    Query(
        description=(
            "The time to read the archive as of: ISO 8601 with an offset, for example "
            "`2026-03-14T19:30:00Z`. Only rows captured at or before it are returned."
        )
    ),
]


_BUSY: dict[int | str, dict[str, Any]] = {
    503: {
        "model": ErrorResponse,
        "description": "The retention prune kept changing the rows this read needs; try again",
    }
}


def _read[T](read: Callable[[], T]) -> T:
    """An archive read gives up rather than answer from rows a prune changed under it
    (``view.settled``). It is made four times first. For one game one prune can disturb
    a read three times at most, so the odds and props reads do not give up in operation;
    the placement prices of a parlay read every leg's game, and a prune that reduces a
    different leg's game during each attempt can use the four up. The answer is then
    this refusal with ``Retry-After``, never a price."""
    try:
        return read()
    except ArchiveBusy:
        raise ApiError(
            503,
            "archive_busy",
            "The archive is being pruned. Try again in a moment.",
            headers={"Retry-After": "5"},
        ) from None


def _as_of(value: datetime, provider: ProviderDep) -> datetime:
    if value.tzinfo is None:
        raise ApiError(422, "as_of_without_offset", "as_of needs a time zone offset, such as Z")
    if value > provider.now() + timedelta(seconds=MAX_CLOCK_SKEW_SECONDS):
        raise ApiError(422, "as_of_in_future", "as_of is in the future")
    return value


@router.get(
    "/archive/events/{event_id}/odds",
    response_model=ArchivedOddsOut,
    operation_id="get_archived_event_odds",
    summary="One event's archived odds as of a time",
    description=(
        "Every book's quote for one market as captured at or before `as_of`, the coverage "
        "of the event then, and the odds comparison as of `as_of`; quotes and comparison "
        "only when the event is covered. Behind the `snapshot_archive` flag."
    ),
    dependencies=_FLAG,
    responses=_BUSY,
)
def get_archived_event_odds(
    event_id: str,
    market: Annotated[EventMarket, Query()],
    as_of: AsOfQuery,
    user: CurrentUserDep,
    db: DbDep,
    provider: ProviderDep,
    settings: SettingsDep,
) -> ArchivedOddsOut:
    moment = _as_of(as_of, provider)
    return _read(lambda: service.archived_odds(db, provider, settings, event_id, market, moment))


@router.get(
    "/archive/players/{player_id}/props",
    response_model=ArchivedPropsOut,
    operation_id="get_archived_player_props",
    summary="One player's archived prop offers as of a time",
    description=(
        "The latest offer per game, market and book captured at or before `as_of`, for "
        "each of the player's games with an offer in the look-back before it (48 hours "
        "with the default settings), and the "
        "props coverage then. A game whose offers were all withdrawn or that had left "
        "scope is left out. A game the retention prune has reduced to its closing offers "
        "is served only where those are still the answer; otherwise its offers are left "
        "out and its id is listed in `pruned_event_ids`: for any time from the game's "
        "first capture to one look-back after its last, the times between two listings "
        "of a game that was postponed and listed again included. A props capture holds "
        "the games of the odds capture made in the same pass. Behind the "
        "`snapshot_archive` flag."
    ),
    dependencies=_FLAG,
    responses=_BUSY,
)
def get_archived_player_props(
    player_id: str,
    as_of: AsOfQuery,
    user: CurrentUserDep,
    db: DbDep,
    provider: ProviderDep,
    settings: SettingsDep,
    market: Annotated[str | None, Query(max_length=40)] = None,
) -> ArchivedPropsOut:
    if provider.get_player(player_id) is None:
        raise not_found("Player", player_id)
    moment = _as_of(as_of, provider)
    return _read(lambda: service.archived_props(db, provider, settings, player_id, market, moment))


@router.get(
    "/archive/events/{event_id}/status",
    response_model=ArchivedStatusOut,
    operation_id="get_archived_event_status",
    summary="One event's archived lineup and news status as of a time",
    description=(
        "The latest status record per team or player and kind captured at or before "
        "`as_of`: a status, a source and times, no article text. Empty until a lineup and "
        "news provider exists. Behind the `snapshot_archive` flag."
    ),
    dependencies=_FLAG,
)
def get_archived_event_status(
    event_id: str,
    as_of: AsOfQuery,
    user: CurrentUserDep,
    db: DbDep,
    provider: ProviderDep,
    settings: SettingsDep,
) -> ArchivedStatusOut:
    return service.archived_status(db, provider, settings, event_id, _as_of(as_of, provider))


@router.get(
    "/bets/{bet_id}/placement-prices",
    response_model=BetPlacementPricesOut,
    operation_id="get_bet_placement_prices",
    summary="The best price at your books when you placed a bet",
    description=(
        "For each leg: the best open, non-stale price overall and at your books from the "
        "archive as of the bet's `placed_at`, or `cannot_price` with the reason. Your "
        "books come from `books`, else from the books of your own recorded bets. Behind "
        "the `snapshot_archive` flag."
    ),
    dependencies=_FLAG,
    responses={
        422: {"model": ErrorResponse, "description": "Unknown or too many sportsbooks"},
        **_BUSY,
    },
)
def get_bet_placement_prices(
    bet_id: str,
    user: CurrentUserDep,
    db: DbDep,
    provider: ProviderDep,
    settings: SettingsDep,
    books: Annotated[
        str | None,
        Query(
            max_length=1000,
            description="Comma-separated sportsbook keys, at most 20, such as `northline,summit`.",
        ),
    ] = None,
) -> BetPlacementPricesOut:
    bet = db.get(Bet, bet_id)
    if bet is None or bet.user_id != user.id:
        raise not_found("Bet", bet_id)
    keys, source = resolve_books(db, provider, user.id, books)
    return BetPlacementPricesOut(
        bet_id=bet.id,
        placed_at=bet.placed_at,
        books=keys,
        books_source=source,  # type: ignore[arg-type]
        data_mode=provider.data_mode,  # type: ignore[arg-type]
        legs=_read(lambda: placement_prices(db, provider, settings, bet, keys)),
    )


@admin_router.get(
    "/archive/stats",
    response_model=ArchiveStatsOut,
    operation_id="get_archive_stats",
    summary="Snapshot archive size, row counts and latest runs",
    responses={403: {"model": ErrorResponse, "description": "Administrator role required"}},
)
def get_archive_stats(
    admin: AdminDep, db: DbDep, settings: SettingsDep, request: Request
) -> ArchiveStatsOut:
    stats = service.archive_stats(db, settings)
    audit_admin_read(db, request, admin.id, "archive_stats")
    return stats
