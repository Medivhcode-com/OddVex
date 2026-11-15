"""Bet tracker domain logic. All arithmetic is delegated to :mod:`oddvex_api.quant`."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from ..db import Bet, BetLeg, utcnow
from ..errors import ApiError
from ..quant import (
    ParlayLeg,
    QuantError,
    closing_line_value,
    money,
    payout,
    profit,
    roi,
    settle_bet,
    settle_parlay,
)
from ..schemas import odds_to_decimal, price_out
from .schemas import (
    BetCreate,
    BetLegIn,
    BetLegOut,
    BetOut,
    BetSettleRequest,
    BetSummaryOut,
    BetTotalsOut,
    BetUpdate,
    BreakdownRowOut,
    TimelinePointOut,
    _check_leg_count,
)

_ODDS_QUANTUM = Decimal("0.000001")
SUMMARY_NOTE = (
    "Totals and breakdowns cover settled bets only; void bets are excluded from staked. "
    "Past results do not predict future results."
)


def _q(value: Decimal) -> Decimal:
    return value.quantize(_ODDS_QUANTUM, rounding=ROUND_HALF_UP)


def to_money(value: float | Decimal) -> Decimal:
    return money(value if isinstance(value, Decimal) else Decimal(str(value)))


def build_leg(data: BetLegIn, position: int) -> BetLeg:
    closing = (
        _q(odds_to_decimal(data.closing_odds, data.odds_format))
        if data.closing_odds is not None
        else None
    )
    closing_opposite = (
        _q(odds_to_decimal(data.closing_opposite_odds, data.odds_format))
        if data.closing_opposite_odds is not None
        else None
    )
    return BetLeg(
        position=position,
        selection=data.selection.strip(),
        market=data.market.strip().lower(),
        league=data.league.strip().lower() if data.league else None,
        event_id=data.event_id,
        event_label=data.event_label,
        line=Decimal(str(data.line)) if data.line is not None else None,
        odds_decimal=_q(odds_to_decimal(data.odds, data.odds_format)),
        closing_odds_decimal=closing,
        closing_opposite_odds_decimal=closing_opposite,
    )


def sport_of(legs: Sequence[BetLeg]) -> str:
    leagues = {leg.league for leg in legs if leg.league}
    if not leagues:
        return "unknown"
    if len(leagues) > 1 or any(not leg.league for leg in legs):
        return "multi"
    return next(iter(leagues))


def product_of_legs(legs: Iterable[BetLeg]) -> Decimal:
    combined = Decimal(1)
    for leg in legs:
        combined *= leg.odds_decimal
    return _q(combined)


def _apply_price(bet: Bet, override_odds: float | str | None, odds_format: str) -> None:
    if override_odds is not None:
        bet.odds_decimal = _q(odds_to_decimal(override_odds, odds_format))
        bet.odds_source = "override"
    else:
        bet.odds_decimal = product_of_legs(bet.legs)
        bet.odds_source = "legs"
    bet.sport = sport_of(bet.legs)


def create_bet(user_id: str, data: BetCreate) -> Bet:
    bet = Bet(
        user_id=user_id,
        bet_type=data.bet_type,
        status="pending",
        sportsbook=data.sportsbook.strip(),
        stake=to_money(data.stake),
        notes=data.notes,
        placed_at=data.placed_at or utcnow(),
        source="manual",
    )
    bet.legs = [build_leg(leg, i) for i, leg in enumerate(data.legs)]
    _apply_price(bet, data.odds, data.odds_format)
    return bet


def update_bet(bet: Bet, data: BetUpdate) -> None:
    fields = data.model_fields_set
    structural = {"bet_type", "legs", "stake", "odds"} & fields
    if structural and bet.status != "pending":
        raise ApiError(
            409,
            "bet_already_settled",
            "Stake, legs, odds and bet type can only be changed while the bet is pending",
            details={"fields": sorted(structural)},
        )
    if "bet_type" in fields and data.bet_type is not None:
        bet.bet_type = data.bet_type
    if "legs" in fields and data.legs is not None:
        bet.legs = [build_leg(leg, i) for i, leg in enumerate(data.legs)]
    if structural:
        try:
            _check_leg_count(bet.bet_type, len(bet.legs))
        except ValueError as exc:
            raise ApiError(422, "validation_error", str(exc)) from exc
    if "stake" in fields and data.stake is not None:
        bet.stake = to_money(data.stake)
    if "odds" in fields or "legs" in fields:
        keep_override = bet.odds_source == "override" and "odds" not in fields
        if not keep_override:
            _apply_price(bet, data.odds if "odds" in fields else None, data.odds_format)
        bet.sport = sport_of(bet.legs)
    if "sportsbook" in fields and data.sportsbook is not None:
        bet.sportsbook = data.sportsbook.strip()
    if "placed_at" in fields and data.placed_at is not None:
        bet.placed_at = data.placed_at
    if "notes" in fields:
        bet.notes = data.notes
    if data.closing_odds:
        by_id = {leg.id: leg for leg in bet.legs}
        for item in data.closing_odds:
            leg = by_id.get(item.leg_id)
            if leg is None:
                raise ApiError(422, "unknown_leg", f"Leg '{item.leg_id}' is not part of this bet")
            leg.closing_odds_decimal = _q(odds_to_decimal(item.closing_odds, item.odds_format))
            leg.closing_opposite_odds_decimal = (
                _q(odds_to_decimal(item.closing_opposite_odds, item.odds_format))
                if item.closing_opposite_odds is not None
                else None
            )
    bet.updated_at = utcnow()


def settle(bet: Bet, data: BetSettleRequest) -> None:
    """Grade a bet. Re-settling an already settled bet overwrites the earlier result."""
    by_id = {leg.id: leg for leg in bet.legs}
    for item in data.leg_results or []:
        if item.leg_id not in by_id:
            raise ApiError(422, "unknown_leg", f"Leg '{item.leg_id}' is not part of this bet")
    staged = {leg.id: leg.result for leg in bet.legs}
    for item in data.leg_results or []:
        staged[item.leg_id] = item.result

    result = data.result
    multi = len(bet.legs) > 1
    if data.leg_results and result != "cashout":
        leg_states = [staged[leg.id] or "pending" for leg in bet.legs]
        if not multi:
            derived = leg_states[0]
            if result is not None and result != derived:
                raise ApiError(
                    422, "result_mismatch", f"Leg result '{derived}' conflicts with '{result}'"
                )
            settlement = settle_bet(bet.stake, bet.odds_decimal, derived)
        elif bet.odds_source == "legs":
            settlement = settle_parlay(
                bet.stake,
                [
                    ParlayLeg(decimal_odds=leg.odds_decimal, result=state)
                    for leg, state in zip(bet.legs, leg_states, strict=True)
                ],
            )
            if result is not None and result != settlement.result:
                raise ApiError(
                    422,
                    "result_mismatch",
                    f"Leg results settle the bet as '{settlement.result}', not '{result}'",
                )
        else:
            # The bet carries its own price, so only all-won / any-lost can be derived.
            if "lost" in leg_states:
                derived = "lost"
            elif all(state == "won" for state in leg_states):
                derived = "won"
            elif result is not None:
                derived = result
            else:
                raise ApiError(
                    422,
                    "result_required",
                    "This bet has its own price, so a bet-level result is required unless "
                    "every leg won or a leg lost",
                )
            if result is not None and result != derived:
                raise ApiError(
                    422, "result_mismatch", f"Leg results imply '{derived}', not '{result}'"
                )
            settlement = settle_bet(bet.stake, bet.odds_decimal, derived)
    else:
        if result is None:  # pragma: no cover - guarded by the request model
            raise ApiError(422, "result_required", "A result is required")
        settlement = settle_bet(bet.stake, bet.odds_decimal, result, data.cashout_amount)
        if result != "cashout":
            if not multi:
                staged[bet.legs[0].id] = result
            elif result == "won":
                staged = {leg.id: staged[leg.id] or "won" for leg in bet.legs}

    for leg in bet.legs:
        leg.result = staged[leg.id]
    bet.status = "settled"
    bet.result = settlement.result
    bet.payout = settlement.payout
    bet.profit = settlement.profit
    bet.settled_at = data.settled_at or utcnow()
    bet.updated_at = utcnow()


# ------------------------------------------------------------- serialisation
def _leg_clv(leg: BetLeg) -> float | None:
    if leg.closing_odds_decimal is None:
        return None
    try:
        return round(
            closing_line_value(leg.odds_decimal, leg.closing_odds_decimal).clv_percent / 100, 6
        )
    except QuantError:
        return None


def bet_clv(bet: Bet) -> float | None:
    """Price-based CLV of the whole bet; needs a closing price on every leg."""
    if not bet.legs or any(leg.closing_odds_decimal is None for leg in bet.legs):
        return None
    taken = Decimal(1)
    closing = Decimal(1)
    for leg in bet.legs:
        taken *= leg.odds_decimal
        closing *= leg.closing_odds_decimal or Decimal(1)
    try:
        return round(closing_line_value(taken, closing).clv_percent / 100, 6)
    except QuantError:
        return None


def bet_out(bet: Bet) -> BetOut:
    return BetOut(
        id=bet.id,
        bet_type=bet.bet_type,  # type: ignore[arg-type]
        status=bet.status,  # type: ignore[arg-type]
        result=bet.result,  # type: ignore[arg-type]
        sport=bet.sport,
        sportsbook=bet.sportsbook,
        stake=float(bet.stake),
        combined_price=price_out(bet.odds_decimal),
        combined_decimal_odds=round(float(bet.odds_decimal), 4),
        odds_source=bet.odds_source,  # type: ignore[arg-type]
        potential_payout=float(payout(bet.stake, bet.odds_decimal)),
        potential_profit=float(profit(bet.stake, bet.odds_decimal)),
        payout=float(bet.payout) if bet.payout is not None else None,
        profit=float(bet.profit) if bet.profit is not None else None,
        clv=bet_clv(bet),
        notes=bet.notes,
        placed_at=bet.placed_at,
        settled_at=bet.settled_at,
        source=bet.source,  # type: ignore[arg-type]
        sync_connection_id=bet.sync_connection_id,
        external_bet_id=bet.external_bet_id,
        legs=[
            BetLegOut(
                id=leg.id,
                position=leg.position,
                selection=leg.selection,
                market=leg.market,
                league=leg.league,
                event_id=leg.event_id,
                event_label=leg.event_label,
                line=float(leg.line) if leg.line is not None else None,
                price=price_out(leg.odds_decimal),
                closing_price=(
                    price_out(leg.closing_odds_decimal)
                    if leg.closing_odds_decimal is not None
                    else None
                ),
                clv=_leg_clv(leg),
                result=leg.result,  # type: ignore[arg-type]
            )
            for leg in bet.legs
        ],
        created_at=bet.created_at,
        updated_at=bet.updated_at,
    )


# -------------------------------------------------------------------- summary
def _market_key(bet: Bet) -> str:
    if len(bet.legs) == 1:
        return bet.legs[0].market
    return "multiple" if bet.legs else "unknown"


def _breakdown(groups: dict[str, list[Bet]]) -> list[BreakdownRowOut]:
    rows = []
    for key, bets in groups.items():
        staked = sum((b.stake for b in bets if b.result != "void"), Decimal(0))
        total_profit = sum((b.profit or Decimal(0) for b in bets), Decimal(0))
        rows.append(
            BreakdownRowOut(
                key=key,
                bets=len(bets),
                staked=float(staked),
                profit=float(total_profit),
                roi=_round(roi(total_profit, staked)),
            )
        )
    rows.sort(key=lambda r: (-r.bets, r.key))
    return rows


def _round(value: float | None, places: int = 6) -> float | None:
    return round(value, places) if value is not None else None


def summarize(bets: Sequence[Bet]) -> BetSummaryOut:
    settled = [b for b in bets if b.status == "settled"]
    pending = [b for b in bets if b.status == "pending"]
    staked = sum((b.stake for b in settled if b.result != "void"), Decimal(0))
    total_profit = sum((b.profit or Decimal(0) for b in settled), Decimal(0))
    clvs = [value for value in (bet_clv(b) for b in bets) if value is not None]

    by_sport: dict[str, list[Bet]] = defaultdict(list)
    by_market: dict[str, list[Bet]] = defaultdict(list)
    by_book: dict[str, list[Bet]] = defaultdict(list)
    by_type: dict[str, list[Bet]] = defaultdict(list)
    daily: dict[datetime, Decimal] = defaultdict(Decimal)
    for bet in settled:
        by_sport[bet.sport].append(bet)
        by_market[_market_key(bet)].append(bet)
        by_book[bet.sportsbook].append(bet)
        by_type[bet.bet_type].append(bet)
        when = bet.settled_at or bet.placed_at
        daily[when.date()] += bet.profit or Decimal(0)  # type: ignore[index]

    running = Decimal(0)
    timeline = []
    for day in sorted(daily):
        running += daily[day]
        timeline.append(TimelinePointOut(date=day, cumulative_profit=float(running)))  # type: ignore[arg-type]

    return BetSummaryOut(
        totals=BetTotalsOut(
            staked=float(staked),
            profit=float(total_profit),
            roi=_round(roi(total_profit, staked)),
            wins=sum(1 for b in settled if (b.profit or 0) > 0),
            losses=sum(1 for b in settled if (b.profit or 0) < 0),
            pushes=sum(1 for b in settled if (b.profit or 0) == 0),
            pending_count=len(pending),
            pending_exposure=float(sum((b.stake for b in pending), Decimal(0))),
            avg_clv=_round(sum(clvs) / len(clvs)) if clvs else None,
            clv_sample=len(clvs),
            settled_count=len(settled),
        ),
        by_sport=_breakdown(by_sport),
        by_market=_breakdown(by_market),
        by_sportsbook=_breakdown(by_book),
        by_bet_type=_breakdown(by_type),
        timeline=timeline,
        note=SUMMARY_NOTE,
    )
