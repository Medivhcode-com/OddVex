"""Import orchestration: retries, idempotent upsert, run bookkeeping."""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import Bet, BetLeg, SyncConnection, SyncImportRun, utcnow
from ..quant import money
from .base import ExternalBet, FetchResult, SyncProvider, SyncProviderError
from .schemas import SyncConnectionOut, SyncRunOut

_ODDS_QUANTUM = Decimal("0.000001")


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


def _to_bet(user_id: str, connection: SyncConnection, external: ExternalBet) -> Bet:
    legs = [
        BetLeg(
            position=position,
            selection=leg.selection[:200],
            market=leg.market[:40],
            league=leg.league,
            event_label=leg.event_label,
            line=leg.line,
            odds_decimal=leg.odds_decimal.quantize(_ODDS_QUANTUM, rounding=ROUND_HALF_UP),
            closing_odds_decimal=(
                leg.closing_odds_decimal.quantize(_ODDS_QUANTUM, rounding=ROUND_HALF_UP)
                if leg.closing_odds_decimal is not None
                else None
            ),
            result=leg.result,
        )
        for position, leg in enumerate(external.legs)
    ]
    combined = Decimal(1)
    for leg in legs:
        combined *= leg.odds_decimal
    leagues = {leg.league for leg in legs if leg.league}
    stake = money(external.stake)
    settled = external.result is not None
    payout = money(external.payout) if settled and external.payout is not None else None
    return Bet(
        user_id=user_id,
        bet_type=external.bet_type,
        status="settled" if settled else "pending",
        result=external.result,
        sport=next(iter(leagues)) if len(leagues) == 1 else ("multi" if leagues else "unknown"),
        sportsbook=external.sportsbook[:80],
        stake=stake,
        odds_decimal=combined.quantize(_ODDS_QUANTUM, rounding=ROUND_HALF_UP),
        odds_source="legs",
        payout=payout,
        profit=money(payout - stake) if payout is not None else None,
        placed_at=external.placed_at,
        settled_at=external.settled_at if settled else None,
        source="sync",
        sync_connection_id=connection.id,
        external_provider=connection.provider,
        external_bet_id=external.external_bet_id,
        legs=legs,
    )


def run_import(
    db: Session,
    connection: SyncConnection,
    provider: SyncProvider,
    max_attempts: int,
    now: datetime | None = None,
) -> SyncImportRun:
    """Fetch and import bets, retrying retryable provider errors up to ``max_attempts``.

    Idempotent: a bet is identified by ``(user, provider, external_bet_id)`` and is
    never imported twice. The run row is added to the session; the caller commits.
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
        return run

    existing = set(
        db.scalars(
            select(Bet.external_bet_id).where(
                Bet.user_id == connection.user_id, Bet.external_provider == connection.provider
            )
        )
    )
    imported = duplicates = 0
    for external in result.bets:
        if external.external_bet_id in existing:
            duplicates += 1
            continue
        db.add(_to_bet(connection.user_id, connection, external))
        existing.add(external.external_bet_id)
        imported += 1
    connection.provider_state = dict(result.state)
    connection.last_synced_at = now
    run.status = "succeeded"
    run.fetched_count = len(result.bets)
    run.imported_count = imported
    run.duplicate_count = duplicates
    return run
