"""Import orchestration: retries, idempotent upsert, the bet cap, run bookkeeping."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..bets import service as bets_service
from ..bets.storage import check_money_fits, check_payout_fits, stored_odds, stored_stake
from ..db import Bet, BetLeg, SyncConnection, SyncImportRun, User, utcnow
from ..errors import ApiError
from ..quant import BET_RESULTS, LEG_RESULTS, QuantError, money
from .base import ExternalBet, FetchResult, SyncProvider, SyncProviderError
from .schemas import SyncConnectionOut, SyncRunOut

_BET_TYPES = frozenset({"straight", "parlay", "sgp", "future"})
#: Most legs an imported bet can have: the same as a bet entered by hand.
_MAX_LEGS = 20
#: Largest line ``bet_legs.line`` (``Numeric(10, 2)``) holds.
_MAX_LINE = Decimal("99999999.99")


@dataclass(frozen=True, slots=True)
class ImportResult:
    """One import run and why bets were left out of it."""

    run: SyncImportRun
    #: Left out because the account already held the most bets it can.
    over_limit: int = 0
    #: Left out because the provider sent a value a column cannot hold.
    rejected: int = 0


def run_out(run: SyncImportRun) -> SyncRunOut:
    return SyncRunOut(
        id=run.id,
        connection_id=run.connection_id,
        status=run.status,  # type: ignore[arg-type]
        attempts=run.attempts,
        fetched_count=run.fetched_count,
        imported_count=run.imported_count,
        duplicate_count=run.duplicate_count,
        retryable=run.retryable,
        error_message=run.error_message,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


def connection_out(
    db: Session, connection: SyncConnection, provider: SyncProvider | None
) -> SyncConnectionOut:
    last_run = db.scalar(
        select(SyncImportRun)
        .where(SyncImportRun.connection_id == connection.id)
        .order_by(SyncImportRun.started_at.desc(), SyncImportRun.id)
        .limit(1)
    )
    bet_count = db.scalar(
        select(func.count()).select_from(Bet).where(Bet.sync_connection_id == connection.id)
    )
    return SyncConnectionOut(
        id=connection.id,
        provider=connection.provider,
        provider_name=provider.info.name if provider else connection.provider,
        is_mock=provider.info.is_mock if provider else False,
        status="active",
        label=connection.label,
        created_at=connection.created_at,
        last_synced_at=connection.last_synced_at,
        bet_count=int(bet_count or 0),
        last_run=run_out(last_run) if last_run else None,
    )


class _Unstorable(ValueError):
    """An external bet with a value no column can hold."""


def _text(value: str | None, length: int) -> str | None:
    return value[:length] if value is not None else None


def _to_bet(user_id: str, connection: SyncConnection, external: ExternalBet) -> Bet:
    """The bet to store for ``external``, checked against the columns like a manual bet.

    Raises (``_Unstorable``, ``ApiError``, ``QuantError`` or an arithmetic error) when the
    provider sent something that cannot be stored: a price that rounds to 1.000000 or
    less or is longer than the price column, a stake that rounds to 0.00, an amount
    longer than the money column, an unknown bet type or result, no legs or more than
    twenty, an id longer than its column, or a timestamp without a time zone or outside
    the calendar in UTC. The caller leaves such a bet out.
    """
    if not external.external_bet_id or len(external.external_bet_id) > 120:
        raise _Unstorable("external bet id")
    if external.bet_type not in _BET_TYPES:
        raise _Unstorable("bet type")
    settled = external.result is not None
    if settled and external.result not in BET_RESULTS:
        raise _Unstorable("result")
    if external.placed_at.tzinfo is None:
        raise _Unstorable("placed_at")
    if settled and external.settled_at is not None and external.settled_at.tzinfo is None:
        raise _Unstorable("settled_at")
    # Converted to UTC here, as the columns hold them: a time within hours of the first
    # or last day of the calendar can fall outside it (an ``OverflowError``).
    placed_at = external.placed_at.astimezone(UTC)
    settled_at = (
        external.settled_at.astimezone(UTC) if settled and external.settled_at is not None else None
    )
    if not 1 <= len(external.legs) <= _MAX_LEGS:
        raise _Unstorable("legs")
    legs = []
    for position, leg in enumerate(external.legs):
        if leg.result is not None and (leg.result == "pending" or leg.result not in LEG_RESULTS):
            raise _Unstorable("leg result")
        if leg.line is not None and not (leg.line.is_finite() and abs(leg.line) <= _MAX_LINE):
            raise _Unstorable("line")
        legs.append(
            BetLeg(
                position=position,
                selection=leg.selection[:200],
                market=leg.market[:40],
                league=_text(leg.league, 32),
                event_label=_text(leg.event_label, 200),
                line=leg.line,
                odds_decimal=stored_odds(leg.odds_decimal),
                closing_odds_decimal=(
                    stored_odds(leg.closing_odds_decimal)
                    if leg.closing_odds_decimal is not None
                    else None
                ),
                result=leg.result,
            )
        )
    combined = Decimal(1)
    for stored_leg in legs:
        combined *= stored_leg.odds_decimal
    odds = stored_odds(combined)
    leagues = {leg.league for leg in legs if leg.league}
    stake = stored_stake(external.stake)
    payout: Decimal | None = None
    if settled and external.payout is not None:
        check_money_fits(external.payout)
        if external.payout < 0:
            raise _Unstorable("payout")
        payout = money(external.payout)
    if not settled:
        # A later settlement of this bet must fit the money column too.
        check_payout_fits(stake, odds)
    return Bet(
        user_id=user_id,
        bet_type=external.bet_type,
        status="settled" if settled else "pending",
        result=external.result,
        sport=next(iter(leagues)) if len(leagues) == 1 else ("multi" if leagues else "unknown"),
        sportsbook=external.sportsbook[:80],
        stake=stake,
        odds_decimal=odds,
        odds_source="legs",
        payout=payout,
        profit=money(payout - stake) if payout is not None else None,
        placed_at=placed_at,
        settled_at=settled_at,
        source="sync",
        sync_connection_id=connection.id,
        external_provider=connection.provider,
        external_bet_id=external.external_bet_id,
        legs=legs,
    )


def _left_out_message(over_limit: int, rejected: int, max_bets: int | None) -> str | None:
    total = over_limit + rejected
    if not total:
        return None
    reasons = []
    if over_limit:
        reasons.append(f"{over_limit} because an account holds at most {max_bets} bets")
    if rejected:
        reasons.append(f"{rejected} because a price, stake or amount cannot be recorded")
    noun = "bet was" if total == 1 else "bets were"
    return f"{total} {noun} not imported: {'; '.join(reasons)}."


def run_import(
    db: Session,
    connection: SyncConnection,
    provider: SyncProvider,
    max_attempts: int,
    now: datetime | None = None,
    max_bets: int | None = None,
) -> ImportResult:
    """Fetch and import bets, retrying retryable provider errors up to ``max_attempts``.

    Idempotent: a bet is identified by ``(user, provider, external_bet_id)`` and is
    never imported twice. The run row is added to the session; the caller commits.

    Imported bets count against the account's bet cap (``max_bets``, the same cap
    ``POST /v1/bets`` enforces): the import takes the provider's bets in order and stops
    adding when the account is full. A bet with a value no column can hold is left out
    as well. Both are counted in the result and in the run's ``error_message``, which
    says how many bets were left out and why; the run still succeeds, and the number is
    also ``fetched_count - imported_count - duplicate_count``. When bets were left out for
    room the provider's position (``provider_state``) is not moved, so a later import is
    offered them again.
    """
    now = now or utcnow()
    run = SyncImportRun(connection_id=connection.id, status="running", started_at=now)
    db.add(run)
    state = dict(connection.provider_state or {})
    result: FetchResult | None = None
    error: SyncProviderError | None = None
    attempts = 0
    while attempts < max(1, max_attempts):
        attempts += 1
        try:
            result = provider.fetch_bets(state, now)
            break
        except SyncProviderError as exc:
            error = exc
            if not exc.retryable:
                break
    run.attempts = attempts
    run.finished_at = utcnow()
    if result is None:
        connection.provider_state = dict(state)
        run.status = "failed"
        run.retryable = bool(error and error.retryable)
        run.error_message = error.message if error else "Unknown provider error"
        return ImportResult(run)

    room: int | None = None
    if max_bets is not None:
        # Imports and creates of one user wait here for each other (a row lock on
        # PostgreSQL), so the count cannot be passed by requests that arrive together.
        db.scalar(
            select(User.id).where(User.id == connection.user_id).with_for_update(key_share=True)
        )
        room = max(0, max_bets - bets_service.count_bets(db, connection.user_id))

    existing = set(
        db.scalars(
            select(Bet.external_bet_id).where(
                Bet.user_id == connection.user_id, Bet.external_provider == connection.provider
            )
        )
    )
    imported = duplicates = over_limit = rejected = 0
    for external in result.bets:
        if external.external_bet_id in existing:
            duplicates += 1
            continue
        try:
            bet = _to_bet(connection.user_id, connection, external)
        except (ApiError, QuantError, ArithmeticError, ValueError):
            rejected += 1
            continue
        if room is not None and imported >= room:
            over_limit += 1
            continue
        db.add(bet)
        existing.add(external.external_bet_id)
        imported += 1
    connection.provider_state = dict(state) if over_limit else dict(result.state)
    connection.last_synced_at = now
    run.status = "succeeded"
    run.fetched_count = len(result.bets)
    run.imported_count = imported
    run.duplicate_count = duplicates
    run.error_message = _left_out_message(over_limit, rejected, max_bets)
    return ImportResult(run, over_limit=over_limit, rejected=rejected)
