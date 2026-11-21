"""Bet tracker routes. Every query is scoped to the authenticated user.

Every route that writes builds its answer before it commits, so a request that ends in an
error has stored nothing. The write routes share the per-user write limit
(``ratelimit.user_rate_limit("writes")``).
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from ..db import Bet, BetLeg, User
from ..deps import CurrentUserDep, DbDep, NowDep, ProviderDep, SettingsDep, write_audit
from ..errors import (
    AUTH_ERROR_RESPONSES,
    NOT_FOUND_RESPONSE,
    RATE_LIMIT_RESPONSE,
    ErrorResponse,
    not_found,
)
from ..flags.service import require_flag
from ..notifications import service as notifications
from ..notifications import templates
from ..providers import SportsDataProvider
from ..ratelimit import UserStreamResponse, take_user_stream_slot, user_exclusive, user_rate_limit
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
#: Bets ``GET /v1/bets`` reads from the database, and sends, at a time. A bet can carry 20
#: legs and 2,000 characters of notes, about 20 KB of JSON, so a batch is about a megabyte.
LIST_BATCH = 50
#: Per-user ceilings on bet writes (per minute and per day), whatever the address.
_WRITE_LIMIT = Depends(user_rate_limit("writes"))


def _owned_bet(db: Session, user_id: str, bet_id: str) -> Bet:
    """Fetch a bet by id *and* owner. Another user's bet is indistinguishable from a missing one."""
    bet = db.scalar(select(Bet).where(Bet.id == bet_id, Bet.user_id == user_id))
    if bet is None:
        raise not_found("Bet", bet_id)
    return bet


def _batch_json(session_factory: sessionmaker[Session], user_id: str, ids: Sequence[str]) -> bytes:
    """The user's bets with these ids as JSON texts joined by commas, in the order given.

    Read in a session of its own that is closed before this returns, and nothing but the
    text is kept. An id that is not a bet of the user (deleted since) is left out.
    """
    with session_factory() as session:
        rows = {
            bet.id: bet
            for bet in session.scalars(select(Bet).where(Bet.user_id == user_id, Bet.id.in_(ids)))
        }
        return b",".join(service.bet_json(rows[bet_id]) for bet_id in ids if bet_id in rows)


def page_chunks(
    session_factory: sessionmaker[Session], user_id: str, ids: Sequence[str]
) -> Iterator[bytes]:
    """A JSON array of the user's bets with these ids, :data:`LIST_BATCH` bets per chunk.

    While a chunk is on its way to the client this holds that chunk and no database
    connection, so a page of 1,000 large bets costs one batch of memory, not the page.
    """
    opened = False
    for start in range(0, len(ids), LIST_BATCH):
        chunk = _batch_json(session_factory, user_id, ids[start : start + LIST_BATCH])
        if chunk:
            yield (b"," if opened else b"[") + chunk
            opened = True
    yield b"]" if opened else b"[]"


@router.get(
    "",
    response_model=list[BetOut],
    operation_id="list_bets",
    summary="Your bets, newest first",
    description=(
        "Filters combine with AND. `market` matches bets with at least one leg in that "
        "market. `sort` takes a field name, prefixed with `-` for descending; bets without "
        "a profit (pending) sort last either way.\n\n"
        "The page is one JSON array, as documented, but it is streamed: the bets are read "
        "and sent a batch at a time, so the response has no `Content-Length`. Read it to "
        "the end and parse it once. Which bets are on the page, and their order, is "
        "decided when the request starts. One account can have "
        "`ODDVEX_RATE_LIMIT_USER_STREAMS_AT_ONCE` (default 8) streamed responses in "
        "progress at the same moment, this list and the data export together: one more "
        "answers 429 `rate_limited` with `Retry-After`."
    ),
    responses=RATE_LIMIT_RESPONSE,
)
def list_bets(
    user: CurrentUserDep,
    db: DbDep,
    request: Request,
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
) -> Response:
    user_id = user.id
    query = select(Bet.id).where(Bet.user_id == user_id)
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
    query = query.order_by(column.is_(None), direction, Bet.placed_at.desc(), Bet.id)
    # One statement decides which bets are on the page and in what order: only their ids
    # are read here. The bets themselves are read and sent a batch at a time by
    # ``page_chunks``, each batch in a session of its own, so this request's connection
    # goes back to the pool now and is not held while the client reads.
    ids = list(db.scalars(query.limit(limit).offset(offset)))
    db.close()
    release = take_user_stream_slot(request, user_id)
    return UserStreamResponse(
        page_chunks(request.app.state.session_factory, user_id, ids),
        release,
        media_type="application/json",
    )


@router.post(
    "",
    response_model=BetOut,
    status_code=201,
    operation_id="create_bet",
    summary="Record a bet you placed elsewhere",
    description=(
        "OddVex never places wagers. This only records a bet for tracking. If you set a "
        "weekly staking reminder and this bet takes the week's total to or past it, a "
        "`stake_reminder` notification is created; the bet is saved either way.\n\n"
        "The bet is checked completely before anything is saved. Prices are stored as "
        "decimal odds with six decimal places and stakes in cents: a price that would be "
        "stored as 1.000000 or less (`invalid_decimal_odds`), a price or combined parlay "
        "price above 9999999999.999999 (`odds_out_of_range`), a stake that would be "
        "stored as 0.00 (`invalid_stake`) and a stake and price whose payout is above "
        "999999999999.99 (`payout_out_of_range`) are each a 422, and a 422 never saves "
        "anything.\n\n"
        "**Retrying safely.** Send `client_request_id` (8 to 64 characters from "
        "`A-Z a-z 0-9 _ -`, for example a UUID made once per filled-in form) and send the "
        "same value again when you retry a create whose answer you did not receive. The "
        "first request stores the bet and answers 201. Every later request from the same "
        "account with the same id answers **200** with the bet that was stored the first "
        "time: no second bet, no second audit entry and no second staking reminder. The "
        "stored bet is returned even if the repeated body differs, so use a new id for a "
        "new or edited bet. This also holds when the retry arrives while the first "
        "request is still running. A repeat is still a request: a body that does not "
        "pass this schema is a 422 and a request over the write limit is a 429, with or "
        "without a known id. An id is only compared within one account, and is "
        "free again once that bet is deleted.\n\n"
        "An account holds at most `ODDVEX_MAX_BETS_PER_USER` bets (default 5,000), "
        "imported bets included: at the cap this answers 409 `bet_limit_reached` with "
        "`details.max_bets`. Bet writes are limited per user (120 a minute and 2,000 a "
        "day by default): over the limit this answers 429 `rate_limited` with "
        "`Retry-After`."
    ),
    responses={
        200: {
            "model": BetOut,
            "description": (
                "A repeat of an earlier create with the same `client_request_id`: the "
                "bet stored the first time. Nothing new was saved"
            ),
        },
        409: {"model": ErrorResponse, "description": "The account holds the most bets it can"},
        **RATE_LIMIT_RESPONSE,
    },
    dependencies=[_WRITE_LIMIT],
)
def create_bet(
    body: BetCreate,
    user: CurrentUserDep,
    db: DbDep,
    request: Request,
    response: Response,
    provider: ProviderDep,
    now: NowDep,
    settings: SettingsDep,
) -> BetOut:
    user_id = user.id
    request_id = body.client_request_id

    def stored_earlier() -> BetOut | None:
        """The answer to a repeat: the bet this user already stored under the id."""
        if request_id is None:
            return None
        existing = service.find_by_client_request_id(db, user_id, request_id)
        if existing is None:
            return None
        response.status_code = 200
        return service.bet_out(existing)

    # Looked up before anything else, so a repeat is answered whatever its body says
    # and however full the account is.
    if (repeat := stored_earlier()) is not None:
        return repeat
    body.legs = service.resolve_structured_legs(body.legs, provider)
    bet = service.create_bet(user_id, body)
    # Creates of one user wait here for each other (a row lock on PostgreSQL), so the
    # count below cannot be passed by requests that arrive together.
    db.scalar(select(User.id).where(User.id == user_id).with_for_update(key_share=True))
    if service.count_bets(db, user_id) >= settings.max_bets_per_user:
        # The account is full. It may be full because of the first request with this
        # id, which was still running at the look-up above and has committed since
        # (this request waited for it at the lock): then this is a repeat, not a new bet.
        if (repeat := stored_earlier()) is not None:
            db.rollback()  # ends the transaction that holds the lock; nothing was written
            return repeat
        raise service.bet_limit_reached(settings.max_bets_per_user)
    staked_before = notifications.staked_this_week(db, user_id, now)
    db.add(bet)
    try:
        db.flush()
    except IntegrityError:
        # The same client_request_id was stored by a request that ran at the same time:
        # the unique index refused this one. Answer with the bet that won.
        db.rollback()
        if (repeat := stored_earlier()) is None:
            raise
        return repeat
    out = service.bet_out(bet)
    write_audit(db, request, "bet.create", user_id=user_id, entity_type="bet", entity_id=bet.id)
    notifications.check_stake_reminder(db, user_id, staked_before, now, request)
    db.commit()
    return out


@router.get(
    "/summary",
    response_model=BetSummaryOut,
    operation_id="get_bet_summary",
    summary="Totals, breakdowns and cumulative profit for your bets",
)
def get_bet_summary(user: CurrentUserDep, db: DbDep) -> BetSummaryOut:
    # Plain columns, not mapped bets with their legs and notes: see BetFacts.
    return service.summarize(service.load_bet_facts(db, user.id))


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
    return analytics.analyze(service.load_bet_facts(db, user.id, settled_only=True))


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
        "`bet_settled` notification. One call settles at most 200 bets, oldest first; "
        "when it stops there with pending bets left unexamined, `has_more` is true and "
        "calling again continues; it is false otherwise, and always sent. "
        "Counts towards the per-user write limit, and one account runs one auto-settle at "
        "a time: a call that arrives while another of the same account is still running "
        "is not started (both are 429 `rate_limited` with `Retry-After`)."
    ),
    responses=RATE_LIMIT_RESPONSE,
    dependencies=[_WRITE_LIMIT],
)
def auto_settle_bets(
    user: CurrentUserDep, db: DbDep, request: Request, provider: ProviderDep
) -> Response:
    with user_exclusive(request, "auto_settle", user.id):
        return _auto_settle(user.id, db, request, provider)


def _auto_settle(
    user_id: str, db: Session, request: Request, provider: SportsDataProvider
) -> Response:
    checked, settled, skipped, has_more = service.auto_settle(db, user_id, provider)
    for bet in settled:
        write_audit(
            db,
            request,
            "bet.auto_settle",
            user_id=user_id,
            entity_type="bet",
            entity_id=bet.id,
            details={"result": bet.result, "legs": [leg.result for leg in bet.legs]},
        )
        notifications.notify(
            db,
            user_id,
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
        notifications.trim(db, user_id)
    out = AutoSettleOut(
        checked=checked,
        settled=[service.bet_out(bet) for bet in settled],
        skipped=[AutoSettleSkipOut(bet_id=bet_id, reason=reason) for bet_id, reason in skipped],  # type: ignore[arg-type]
        has_more=has_more,
    )
    # Serialised before the commit, so an error here saves nothing.
    body = out.model_dump_json()
    db.commit()
    return Response(body, media_type="application/json")


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
    description=(
        "Stake, legs, odds and bet type can only change while the bet is pending. The "
        "changed bet is checked as a whole before anything is saved, with the same rules "
        "as a create (`invalid_decimal_odds`, `odds_out_of_range`, `invalid_stake`, "
        "`payout_out_of_range`, all 422): a refused update changes nothing. Editing never "
        "adds a bet, so it works at the bet cap. Counts towards the per-user write limit "
        "(429 `rate_limited` with `Retry-After`)."
    ),
    responses={**NOT_FOUND_RESPONSE, **_CONFLICT, **RATE_LIMIT_RESPONSE},
    dependencies=[_WRITE_LIMIT],
)
def update_bet(
    bet_id: str, body: BetUpdate, user: CurrentUserDep, db: DbDep, provider: ProviderDep
) -> BetOut:
    bet = _owned_bet(db, user.id, bet_id)
    if body.legs is not None:
        body.legs = service.resolve_structured_legs(body.legs, provider)
    service.update_bet(bet, body)
    db.flush()
    db.refresh(bet)
    out = service.bet_out(bet)
    db.commit()
    return out


@router.delete(
    "/{bet_id}",
    status_code=204,
    operation_id="delete_bet",
    summary="Delete a bet",
    responses={**NOT_FOUND_RESPONSE, **RATE_LIMIT_RESPONSE},
    dependencies=[_WRITE_LIMIT],
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
        "The change is recorded in the audit log. A result whose payout is above "
        "999999999999.99 is refused with 422 `payout_out_of_range` and the bet is left "
        "as it was. Counts towards the per-user write limit (429 `rate_limited` with "
        "`Retry-After`)."
    ),
    responses={**NOT_FOUND_RESPONSE, **RATE_LIMIT_RESPONSE},
    dependencies=[_WRITE_LIMIT],
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
    db.flush()
    out = service.bet_out(bet)
    db.commit()
    return out
