"""Public, read-only sports data routes. Everything served here is synthetic."""

from __future__ import annotations

import logging
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import text

from .. import __version__
from ..board import SYNTHETIC_NOTICE
from ..deps import BoardDep, ProviderDep
from ..errors import ERROR_RESPONSES, NOT_FOUND_RESPONSE, ApiError, ErrorResponse, not_found
from ..flags.service import require_flag
from ..providers import Event, Player
from .schemas import (
    EventDetailOut,
    EventMarket,
    EventOddsOut,
    EventStatus,
    EventSummaryOut,
    HealthOut,
    LeagueKey,
    LeagueOut,
    LineHistoryOut,
    MetaOut,
    PlayerDetailOut,
    PlayerOut,
    PlayerPropsOut,
    PropBoardRowOut,
    PropSplit,
    PropWindow,
    SportsbookOut,
    ValueScreenOut,
)

logger = logging.getLogger("oddvex.health")

health_router = APIRouter(tags=["meta"])
router = APIRouter()


@health_router.get(
    "/health",
    response_model=HealthOut,
    operation_id="get_health",
    summary="Liveness check",
    description=(
        "Always answers 200 while the process is up. `database` is the result of a cheap "
        "`SELECT 1`; when it fails, `status` is `degraded`."
    ),
)
def get_health(provider: ProviderDep, request: Request) -> HealthOut:
    database: Literal["ok", "error"] = "ok"
    try:
        with request.app.state.session_factory() as session:
            session.execute(text("SELECT 1"))
    except Exception:  # the health check must answer whatever the database does
        database = "error"
        logger.warning("health_database_check_failed", exc_info=True)
    return HealthOut(
        status="ok" if database == "ok" else "degraded",
        version=__version__,
        data_mode=provider.data_mode,  # type: ignore[arg-type]
        server_time=provider.now(),
        database=database,
    )


@router.get(
    "/meta",
    response_model=MetaOut,
    operation_id="get_meta",
    tags=["meta"],
    summary="Data mode, provider and server time",
)
def get_meta(provider: ProviderDep) -> MetaOut:
    return MetaOut(
        data_mode=provider.data_mode,  # type: ignore[arg-type]
        provider=provider.name,
        version=__version__,
        server_time=provider.now(),
        notice=getattr(provider, "notice", SYNTHETIC_NOTICE),
        attribution=getattr(provider, "attribution", None),
    )


@router.get(
    "/leagues",
    response_model=list[LeagueOut],
    operation_id="list_leagues",
    tags=["meta"],
    summary="Supported leagues",
)
def list_leagues(board: BoardDep) -> list[LeagueOut]:
    return board.leagues()


@router.get(
    "/sportsbooks",
    response_model=list[SportsbookOut],
    operation_id="list_sportsbooks",
    tags=["meta"],
    summary="Sportsbooks in the comparison (fictional)",
)
def list_sportsbooks(board: BoardDep) -> list[SportsbookOut]:
    return board.sportsbooks()


# --------------------------------------------------------------------- events
def _event_or_404(provider: ProviderDep, event_id: str) -> Event:
    event = provider.get_event(event_id)
    if event is None:
        raise not_found("Event", event_id)
    return event


def _check_market(event: Event, market: str) -> None:
    if market not in event.markets:
        raise ApiError(
            422,
            "market_not_available",
            f"Market '{market}' is not offered for this event",
            details={"available_markets": event.markets},
        )


@router.get(
    "/events",
    response_model=list[EventSummaryOut],
    operation_id="list_events",
    tags=["events"],
    summary="Events, soonest first",
    description=(
        "Without `date` the window is 3 days back to 4 days ahead (UTC). `date` selects one "
        "UTC calendar day."
    ),
    responses=ERROR_RESPONSES,
)
def list_events(
    board: BoardDep,
    league: Annotated[LeagueKey | None, Query()] = None,
    status: Annotated[EventStatus | None, Query()] = None,
    on_date: Annotated[date | None, Query(alias="date", description="UTC date, YYYY-MM-DD")] = None,
) -> list[EventSummaryOut]:
    events = board.provider.list_events(league=league, status=status, on_date=on_date)
    return [board.event_summary(event) for event in events]


@router.get(
    "/events/{event_id}",
    response_model=EventDetailOut,
    operation_id="get_event",
    tags=["events"],
    summary="One event with its available markets",
    responses={**NOT_FOUND_RESPONSE, **ERROR_RESPONSES},
)
def get_event(event_id: str, board: BoardDep) -> EventDetailOut:
    return board.event_detail(_event_or_404(board.provider, event_id))


@router.get(
    "/events/{event_id}/odds",
    response_model=EventOddsOut,
    operation_id="get_event_odds",
    tags=["events"],
    summary="Odds comparison across sportsbooks for one market",
    description=(
        "`is_best` and `best` only consider books that are open and not stale. For spread and "
        "total, prices are only compared between books quoting the consensus (most common) "
        "line. `consensus` is the mean no-vig probability of those same books. Markets of "
        "finished events are reported as `unavailable`."
    ),
    responses={**NOT_FOUND_RESPONSE, **ERROR_RESPONSES},
)
def get_event_odds(
    event_id: str, board: BoardDep, market: Annotated[EventMarket, Query()] = "moneyline"
) -> EventOddsOut:
    event = _event_or_404(board.provider, event_id)
    _check_market(event, market)
    return board.event_odds(event, market)


@router.get(
    "/events/{event_id}/line-history",
    response_model=LineHistoryOut,
    operation_id="get_event_line_history",
    tags=["events"],
    summary="About 48 hours of price and line history per sportsbook",
    responses={**NOT_FOUND_RESPONSE, **ERROR_RESPONSES},
)
def get_event_line_history(
    event_id: str, board: BoardDep, market: Annotated[EventMarket, Query()] = "moneyline"
) -> LineHistoryOut:
    event = _event_or_404(board.provider, event_id)
    _check_market(event, market)
    return board.line_history(event, market)


# -------------------------------------------------------------------- players
def _player_or_404(provider: ProviderDep, player_id: str) -> Player:
    player = provider.get_player(player_id)
    if player is None:
        raise not_found("Player", player_id)
    return player


@router.get(
    "/players",
    response_model=list[PlayerOut],
    operation_id="list_players",
    tags=["players"],
    summary="Search players by name",
    responses=ERROR_RESPONSES,
)
def list_players(
    board: BoardDep,
    q: Annotated[str | None, Query(max_length=80, description="Name contains")] = None,
    league: Annotated[LeagueKey | None, Query()] = None,
) -> list[PlayerOut]:
    players = board.provider.list_players(league=league, query=q)
    return [board.player_out(p) for p in sorted(players, key=lambda p: (p.name, p.id))]


@router.get(
    "/players/{player_id}",
    response_model=PlayerDetailOut,
    operation_id="get_player",
    tags=["players"],
    summary="One player and their next event",
    responses={**NOT_FOUND_RESPONSE, **ERROR_RESPONSES},
)
def get_player(player_id: str, board: BoardDep) -> PlayerDetailOut:
    return board.player_detail(_player_or_404(board.provider, player_id))


@router.get(
    "/players/{player_id}/props",
    response_model=PlayerPropsOut,
    operation_id="get_player_props",
    tags=["players"],
    summary="Prop research: offers by book, game log and historical hit rate",
    description=(
        "`market` defaults to the player's first prop market. The game log is filtered by "
        "`split`, then cut to the most recent `window` games, and graded against the "
        "consensus line. Hit rate is historical only; pushes are excluded from the sample."
    ),
    responses={**NOT_FOUND_RESPONSE, **ERROR_RESPONSES},
)
def get_player_props(
    player_id: str,
    board: BoardDep,
    market: Annotated[str | None, Query(max_length=40)] = None,
    window: Annotated[PropWindow, Query()] = "10",
    split: Annotated[PropSplit, Query()] = "all",
) -> PlayerPropsOut:
    player = _player_or_404(board.provider, player_id)
    chosen = market or player.prop_markets[0]
    if chosen not in player.prop_markets:
        raise ApiError(
            422,
            "market_not_available",
            f"Market '{chosen}' is not tracked for this player",
            details={"available_markets": player.prop_markets},
        )
    return board.player_props(player, chosen, window, split)


@router.get(
    "/props",
    response_model=list[PropBoardRowOut],
    operation_id="list_props",
    tags=["players"],
    summary="Prop board: consensus line, best over/under and last-10 hit rate",
    responses=ERROR_RESPONSES,
)
def list_props(
    board: BoardDep,
    league: Annotated[LeagueKey | None, Query()] = None,
    market: Annotated[str | None, Query(max_length=40)] = None,
) -> list[PropBoardRowOut]:
    return board.props_board(league, market)


# --------------------------------------------------------------- value screen
@router.get(
    "/value",
    response_model=ValueScreenOut,
    operation_id="list_value",
    tags=["value"],
    summary="Market discrepancies: best price against the consensus of the other books",
    description=(
        "Outcomes of live and upcoming events whose best open, non-stale price is longer "
        "than the no-vig consensus of the other open, non-stale sportsbooks at the same "
        "line. The sportsbook with the best price is excluded from its own consensus and "
        "at least 2 other sportsbooks are required, otherwise the outcome is skipped. "
        "Sorted by `edge`, largest first. A price above the consensus is not proof of an "
        "edge and this is not a prediction; read `caveat`. Behind the `value_screen` flag."
    ),
    dependencies=[Depends(require_flag("value_screen"))],
    responses={
        404: {"model": ErrorResponse, "description": "The feature is switched off"},
        **ERROR_RESPONSES,
    },
)
def list_value(
    board: BoardDep,
    league: Annotated[LeagueKey | None, Query()] = None,
    market: Annotated[EventMarket | None, Query()] = None,
    min_edge: Annotated[
        float, Query(ge=0, le=10, description="Smallest edge to include, as a fraction.")
    ] = 0.0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ValueScreenOut:
    return board.value_screen(league, market, min_edge, limit)
