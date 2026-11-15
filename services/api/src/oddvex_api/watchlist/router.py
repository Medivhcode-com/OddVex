"""Watchlist routes. Every query is scoped to the authenticated user."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..api.schemas import EventSummaryOut
from ..db import WatchlistItem
from ..deps import BoardDep, CurrentUserDep, DbDep, write_audit
from ..errors import AUTH_ERROR_RESPONSES, NOT_FOUND_RESPONSE, ApiError, ErrorResponse, not_found
from . import service
from .schemas import (
    MAX_WATCHLIST_ITEMS,
    WatchlistItemCreate,
    WatchlistItemOut,
    WatchlistKind,
    WatchlistOut,
)

router = APIRouter(prefix="/watchlist", tags=["watchlist"], responses=AUTH_ERROR_RESPONSES)

_KIND_NAMES = {"team": "Team", "player": "Player", "event": "Event"}


def _items(db: Session, user_id: str, kind: str | None = None) -> list[WatchlistItem]:
    query = select(WatchlistItem).where(WatchlistItem.user_id == user_id)
    if kind is not None:
        query = query.where(WatchlistItem.kind == kind)
    return list(db.scalars(query.order_by(WatchlistItem.created_at.desc(), WatchlistItem.id)))


def _existing(db: Session, user_id: str, kind: str, ref_id: str) -> WatchlistItem | None:
    return db.scalar(
        select(WatchlistItem).where(
            WatchlistItem.user_id == user_id,
            WatchlistItem.kind == kind,
            WatchlistItem.ref_id == ref_id,
        )
    )


@router.get(
    "",
    response_model=WatchlistOut,
    operation_id="list_watchlist",
    summary="Your watched teams, players and events, newest first",
    description=(
        "Each item embeds the current team, player or event from the data provider. When "
        "the provider no longer has it, `available` is false and the embed is null."
    ),
)
def list_watchlist(
    user: CurrentUserDep,
    db: DbDep,
    board: BoardDep,
    kind: Annotated[WatchlistKind | None, Query()] = None,
) -> WatchlistOut:
    return WatchlistOut(items=[service.item_out(board, item) for item in _items(db, user.id, kind)])


@router.post(
    "",
    response_model=WatchlistItemOut,
    status_code=201,
    operation_id="add_watchlist_item",
    summary="Watch a team, player or event",
    description=(
        "Idempotent: adding something you already watch returns the existing item with 200 "
        f"instead of 201. A watchlist holds at most {MAX_WATCHLIST_ITEMS} items."
    ),
    responses={
        200: {"model": WatchlistItemOut, "description": "Already on the watchlist"},
        **NOT_FOUND_RESPONSE,
        409: {"model": ErrorResponse, "description": "The watchlist is full"},
    },
)
def add_watchlist_item(
    body: WatchlistItemCreate,
    user: CurrentUserDep,
    db: DbDep,
    board: BoardDep,
    request: Request,
    response: Response,
) -> WatchlistItemOut:
    described = service.describe(board, body.kind, body.ref_id)
    if described is None:
        raise not_found(_KIND_NAMES[body.kind], body.ref_id)
    existing = _existing(db, user.id, body.kind, body.ref_id)
    if existing is not None:
        response.status_code = 200
        return service.item_out(board, existing)
    count = db.scalar(
        select(func.count()).select_from(WatchlistItem).where(WatchlistItem.user_id == user.id)
    )
    if int(count or 0) >= MAX_WATCHLIST_ITEMS:
        raise ApiError(
            409,
            "watchlist_full",
            f"A watchlist holds at most {MAX_WATCHLIST_ITEMS} items. Remove one to add another.",
            details={"max_items": MAX_WATCHLIST_ITEMS},
        )
    label, league = described
    item = WatchlistItem(
        user_id=user.id, kind=body.kind, ref_id=body.ref_id, label=label[:200], league=league
    )
    db.add(item)
    try:
        db.flush()
    except IntegrityError:
        # A concurrent request added the same item first; return that one.
        db.rollback()
        existing = _existing(db, user.id, body.kind, body.ref_id)
        if existing is None:
            raise
        response.status_code = 200
        return service.item_out(board, existing)
    write_audit(
        db,
        request,
        "watchlist.add",
        user_id=user.id,
        entity_type="watchlist_item",
        entity_id=item.id,
        details={"kind": item.kind, "ref_id": item.ref_id},
    )
    db.commit()
    return service.item_out(board, item)


@router.get(
    "/events",
    response_model=list[EventSummaryOut],
    operation_id="list_watchlist_events",
    summary="Live and upcoming events for everything you watch",
    description=(
        "Events involving a watched team or a watched player's team, plus events watched "
        "directly. De-duplicated; live events first, then by start time."
    ),
)
def list_watchlist_events(
    user: CurrentUserDep, db: DbDep, board: BoardDep
) -> list[EventSummaryOut]:
    return service.watched_events(board, _items(db, user.id))


@router.delete(
    "/{item_id}",
    status_code=204,
    operation_id="remove_watchlist_item",
    summary="Stop watching",
    responses=NOT_FOUND_RESPONSE,
)
def remove_watchlist_item(
    item_id: str, user: CurrentUserDep, db: DbDep, request: Request
) -> Response:
    item = db.scalar(
        select(WatchlistItem).where(WatchlistItem.id == item_id, WatchlistItem.user_id == user.id)
    )
    if item is None:
        raise not_found("Watchlist item", item_id)
    details = {"kind": item.kind, "ref_id": item.ref_id}
    db.delete(item)
    write_audit(
        db,
        request,
        "watchlist.remove",
        user_id=user.id,
        entity_type="watchlist_item",
        entity_id=item_id,
        details=details,
    )
    db.commit()
    return Response(status_code=204)
