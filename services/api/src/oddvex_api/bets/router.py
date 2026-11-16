"""Bet tracker routes. Every query is scoped to the authenticated user."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import Bet, BetLeg
from ..deps import CurrentUserDep, DbDep, NowDep, ProviderDep, write_audit
from ..errors import AUTH_ERROR_RESPONSES, NOT_FOUND_RESPONSE, ErrorResponse, not_found
from ..flags.service import require_flag
from ..notifications import service as notifications
from ..notifications import templates
from ..textnorm import fold
from . import analytics, service
from .schemas import (
    AutoSettleOut,
    AutoSettleSkipOut,
    BetAnalyticsOut,
    BetCreate,
    BetOut,
    BetSettleRequest,
    BetSort,
    BetStatusFilter,
    BetSummaryOut,
    BetType,
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
    description=(
        "Filters combine with AND. `market` matches bets with at least one leg in that "
        "market. `sort` takes a field name, prefixed with `-` for descending; bets without "
        "a profit (pending) sort last either way."
    ),
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
    sort: Annotated[BetSort, Query(description="Default: -placed_at (newest first)")] = (
        "-placed_at"
    ),
    market: Annotated[str | None, Query(max_length=40)] = None,
    sportsbook: Annotated[
        str | None, Query(max_length=80, description="Exact name, case-insensitive")
    ] = None,
    bet_type: Annotated[BetType | None, Query()] = None,
) -> list[BetOut]:
    query = select(Bet).where(Bet.user_id == user.id)
    if status in ("pending", "settled"):
        query = query.where(Bet.status == status)
    elif status is not None:
        query = query.where(Bet.result == status)
    if sport:
        query = query.where(Bet.sport == sport.strip().lower())
    if market and market.strip():
        query = query.where(Bet.legs.any(BetLeg.market == market.strip().lower()))
    if sportsbook and sportsbook.strip():
        # Compared against a key folded in Python (``textnorm.fold``), not SQL ``lower()``,
        # which only folds ASCII on SQLite and on PostgreSQL with the C locale.
        query = query.where(Bet.sportsbook_key == fold(sportsbook))
    if bet_type is not None:
        query = query.where(Bet.bet_type == bet_type)
    column = {"placed_at": Bet.placed_at, "stake": Bet.stake, "profit": Bet.profit}[
        sort.lstrip("-")
    ]
    direction = column.desc() if sort.startswith("-") else column.asc()
    # ``IS NULL`` first keeps the ordering of nulls identical on SQLite and PostgreSQL.
    query = (
        query.order_by(column.is_(None), direction, Bet.placed_at.desc(), Bet.id)
        .limit(limit)
        .offset(offset)
    )
    return [service.bet_out(bet) for bet in db.scalars(query)]


@router.post(
    "",
    response_model=BetOut,
    status_code=201,
    operation_id="create_bet",
    summary="Record a bet you placed elsewhere",
    description=(
        "OddVex never places wagers. This only records a bet for tracking. If you set a "
        "weekly staking reminder and this bet takes the week's total to or past it, a "
        "`stake_reminder` notification is created; the bet is saved either way."
    ),
)
def create_bet(
    body: BetCreate,
    user: CurrentUserDep,
    db: DbDep,
    request: Request,
    provider: ProviderDep,
    now: NowDep,
) -> BetOut:
    body.legs = service.resolve_structured_legs(body.legs, provider)
    bet = service.create_bet(user.id, body)
    staked_before = notifications.staked_this_week(db, user.id, now)
    db.add(bet)
    db.flush()
    write_audit(db, request, "bet.create", user_id=user.id, entity_type="bet", entity_id=bet.id)
    notifications.check_stake_reminder(db, user.id, staked_before, now, request)
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
    "/analytics",
    response_model=BetAnalyticsOut,
    operation_id="get_bet_analytics",
    summary="Odds bands, weekdays, months, streaks, CLV and stake sizes for your settled bets",
    description=(
        "Computed only from your settled bets. Ratios are fractions. With fewer than 30 "
        "settled bets `sample_note` says the results are mostly noise. Behind the "
        "`tracker_analytics` flag."
    ),
    dependencies=[Depends(require_flag("tracker_analytics"))],
    responses={
        404: {"model": ErrorResponse, "description": "The feature is switched off"},
    },
)
def get_bet_analytics(user: CurrentUserDep, db: DbDep) -> BetAnalyticsOut:
    bets = list(db.scalars(select(Bet).where(Bet.user_id == user.id, Bet.status == "settled")))
    return analytics.analyze(bets)


@router.post(
    "/auto-settle",
    response_model=AutoSettleOut,
    operation_id="auto_settle_bets",
    summary="Settle your pending bets from final scores",
    description=(
        "Looks at each of your pending bets. A bet is settled when every leg has a "
        "structured selection (`gradeable`) and every leg's event is final: the legs are "
        "graded from the final score and the bet goes through the same settlement as a "
        "manual settle, marked `settled_by: auto`. Other bets are listed in `skipped` with "
        "a reason. Calling this again settles nothing new. Each settled bet also creates a "
        "`bet_settled` notification."
    ),
)
def auto_settle_bets(
    user: CurrentUserDep, db: DbDep, request: Request, provider: ProviderDep
) -> AutoSettleOut:
    checked, settled, skipped = service.auto_settle(db, user.id, provider)
    for bet in settled:
        write_audit(
            db,
            request,
            "bet.auto_settle",
            user_id=user.id,
            entity_type="bet",
            entity_id=bet.id,
            details={"result": bet.result, "legs": [leg.result for leg in bet.legs]},
        )
        notifications.notify(
            db,
            user.id,
            templates.bet_settled(
                bet_id=bet.id,
                result=bet.result or "",
                stake=bet.stake,
                profit=bet.profit if bet.profit is not None else Decimal(0),
                sportsbook=bet.sportsbook,
            ),
        )
    if settled:
        db.flush()
        notifications.trim(db, user.id)
    db.commit()
    return AutoSettleOut(
        checked=checked,
        settled=[service.bet_out(bet) for bet in settled],
        skipped=[AutoSettleSkipOut(bet_id=bet_id, reason=reason) for bet_id, reason in skipped],  # type: ignore[arg-type]
    )


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
def update_bet(
    bet_id: str, body: BetUpdate, user: CurrentUserDep, db: DbDep, provider: ProviderDep
) -> BetOut:
    bet = _owned_bet(db, user.id, bet_id)
    if body.legs is not None:
        body.legs = service.resolve_structured_legs(body.legs, provider)
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
