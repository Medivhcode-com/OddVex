"""Bet tracker routes. Every query is scoped to the authenticated user."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import Bet
from ..deps import CurrentUserDep, DbDep, write_audit
from ..errors import AUTH_ERROR_RESPONSES, NOT_FOUND_RESPONSE, ErrorResponse, not_found
from . import service
from .schemas import (
    BetCreate,
    BetOut,
    BetSettleRequest,
    BetStatusFilter,
    BetSummaryOut,
    BetUpdate,
)

router = APIRouter(prefix="/bets", tags=["bets"], responses=AUTH_ERROR_RESPONSES)

_CONFLICT: dict[int | str, dict[str, Any]] = {
    409: {"model": ErrorResponse, "description": "The bet is already settled"}
}


def _owned_bet(db: Session, user_id: str, bet_id: str) -> Bet:
    """Fetch a bet by id *and* owner. Another user's bet is indistinguishable from a missing one."""
    bet = db.scalar(select(Bet).where(Bet.id == bet_id, Bet.user_id == user_id))
    if bet is None:
        raise not_found("Bet", bet_id)
    return bet


@router.get(
    "",
    response_model=list[BetOut],
    operation_id="list_bets",
    summary="Your bets, newest first",
)
def list_bets(
    user: CurrentUserDep,
    db: DbDep,
    status: Annotated[
        BetStatusFilter | None,
        Query(description="pending, settled, or a specific result such as won"),
    ] = None,
    sport: Annotated[str | None, Query(max_length=32)] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[BetOut]:
    query = select(Bet).where(Bet.user_id == user.id)
    if status in ("pending", "settled"):
        query = query.where(Bet.status == status)
    elif status is not None:
        query = query.where(Bet.result == status)
    if sport:
        query = query.where(Bet.sport == sport.strip().lower())
    query = query.order_by(Bet.placed_at.desc(), Bet.id).limit(limit).offset(offset)
    return [service.bet_out(bet) for bet in db.scalars(query)]


@router.post(
    "",
    response_model=BetOut,
    status_code=201,
    operation_id="create_bet",
    summary="Record a bet you placed elsewhere",
    description="OddVex never places wagers. This only records a bet for tracking.",
)
def create_bet(body: BetCreate, user: CurrentUserDep, db: DbDep, request: Request) -> BetOut:
    bet = service.create_bet(user.id, body)
    db.add(bet)
    db.flush()
    write_audit(db, request, "bet.create", user_id=user.id, entity_type="bet", entity_id=bet.id)
    db.commit()
    return service.bet_out(bet)


@router.get(
    "/summary",
    response_model=BetSummaryOut,
    operation_id="get_bet_summary",
    summary="Totals, breakdowns and cumulative profit for your bets",
)
def get_bet_summary(user: CurrentUserDep, db: DbDep) -> BetSummaryOut:
    bets = list(db.scalars(select(Bet).where(Bet.user_id == user.id)))
    return service.summarize(bets)


@router.get(
    "/{bet_id}",
    response_model=BetOut,
    operation_id="get_bet",
    summary="One bet",
    responses=NOT_FOUND_RESPONSE,
)
def get_bet(bet_id: str, user: CurrentUserDep, db: DbDep) -> BetOut:
    return service.bet_out(_owned_bet(db, user.id, bet_id))


@router.patch(
    "/{bet_id}",
    response_model=BetOut,
    operation_id="update_bet",
    summary="Edit a bet",
    responses={**NOT_FOUND_RESPONSE, **_CONFLICT},
)
def update_bet(bet_id: str, body: BetUpdate, user: CurrentUserDep, db: DbDep) -> BetOut:
    bet = _owned_bet(db, user.id, bet_id)
    service.update_bet(bet, body)
    db.commit()
    db.refresh(bet)
    return service.bet_out(bet)


@router.delete(
    "/{bet_id}",
    status_code=204,
    operation_id="delete_bet",
    summary="Delete a bet",
    responses=NOT_FOUND_RESPONSE,
)
def delete_bet(bet_id: str, user: CurrentUserDep, db: DbDep, request: Request) -> Response:
    bet = _owned_bet(db, user.id, bet_id)
    db.delete(bet)
    write_audit(db, request, "bet.delete", user_id=user.id, entity_type="bet", entity_id=bet_id)
    db.commit()
    return Response(status_code=204)


@router.post(
    "/{bet_id}/settle",
    response_model=BetOut,
    operation_id="settle_bet",
    summary="Grade a bet",
    description=(
        "Settling an already settled bet overwrites the earlier result (for corrections). "
        "The change is recorded in the audit log."
    ),
    responses=NOT_FOUND_RESPONSE,
)
def settle_bet(
    bet_id: str, body: BetSettleRequest, user: CurrentUserDep, db: DbDep, request: Request
) -> BetOut:
    bet = _owned_bet(db, user.id, bet_id)
    previous = bet.result
    service.settle(bet, body)
    write_audit(
        db,
        request,
        "bet.settle",
        user_id=user.id,
        entity_type="bet",
        entity_id=bet.id,
        details={"result": bet.result, "previous_result": previous},
    )
    db.commit()
    return service.bet_out(bet)
