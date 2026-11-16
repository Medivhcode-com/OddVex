"""Alert rules: validation against the provider, serialisation and evaluation.

The decision logic lives in :mod:`.evaluator` (pure). This module gathers the facts a
rule needs from the provider, applies the outcome to the database and hands the
notifications to ``notifications.service.notify``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..board import Board
from ..db import AlertRule, User, utcnow
from ..deps import write_audit
from ..errors import ApiError
from ..notifications import service as notifications
from ..notifications import templates
from ..providers import Event, Team
from ..quant import valid_outcome_keys
from ..schemas import odds_to_decimal, price_out
from .evaluator import GameSnapshot, PriceSnapshot, RuleInputs, RuleSnapshot, evaluate
from .schemas import (
    AlertRuleOut,
    GameFinalAlertCreate,
    GameStartAlertCreate,
    LineMoveAlertCreate,
    PriceAtLeastAlertCreate,
)

_ODDS_QUANTUM = Decimal("0.000001")
_LINE_QUANTUM = Decimal("0.01")
#: Team-scoped rules remember handled events; older ids are dropped beyond this many.
_MAX_HANDLED_EVENTS = 200

type AlertCreateBody = (
    PriceAtLeastAlertCreate | LineMoveAlertCreate | GameStartAlertCreate | GameFinalAlertCreate
)


def _line(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(_LINE_QUANTUM, rounding=ROUND_HALF_UP)


def _invalid(code: str, message: str, **details: object) -> ApiError:
    return ApiError(422, code, message, details=details or None)


# ------------------------------------------------------------------ validation
def from_body(body: AlertCreateBody) -> AlertRule:
    """An unsaved rule holding the request's fields. Not yet checked against the provider."""
    rule = AlertRule(kind=body.kind, state="active", label="", fired_event_ids=[], arm_count=0)
    if isinstance(body, PriceAtLeastAlertCreate):
        rule.event_id, rule.market, rule.outcome_key = body.event_id, body.market, body.outcome_key
        rule.line = _line(body.line) if body.line is not None else None
        rule.threshold_decimal = odds_to_decimal(body.threshold, body.odds_format).quantize(
            _ODDS_QUANTUM, rounding=ROUND_HALF_UP
        )
    elif isinstance(body, LineMoveAlertCreate):
        rule.event_id, rule.market, rule.outcome_key = body.event_id, body.market, body.outcome_key
        rule.min_move = _line(body.min_move)
        if rule.min_move <= 0:
            raise _invalid("validation_error", "min_move must be at least 0.01 points")
    else:
        rule.event_id, rule.team_id = body.event_id, body.team_id
        if isinstance(body, GameStartAlertCreate):
            rule.minutes_before = body.minutes_before
    return rule


def _team_events(board: Board, team: Team) -> list[Event]:
    return [
        event
        for event in board.provider.list_events(league=team.league)
        if team.id in (event.home_team_id, event.away_team_id)
    ]


def _event_label(board: Board, event: Event) -> str:
    return templates.matchup(
        board.team_ref(event.home_team_id).name, board.team_ref(event.away_team_id).name
    )


def arm(board: Board, rule: AlertRule) -> None:
    """Check the rule against the provider and set what arming needs.

    Used when a rule is created and when a triggered or expired one is re-armed: the
    event must exist and still be open, the market and outcome must fit it, and a
    ``line_move`` rule takes the current consensus line as its baseline. Raises a 422
    :class:`ApiError` otherwise.
    """
    provider = board.provider
    if rule.team_id is not None:
        team = provider.get_team(rule.team_id)
        if team is None:
            raise _invalid("unknown_team", f"Team '{rule.team_id}' was not found")
        rule.label, rule.league = team.name[:200], team.league
        mark_finished_games_handled(board, rule)
        return

    assert rule.event_id is not None
    event = provider.get_event(rule.event_id)
    if event is None:
        raise _invalid("unknown_event", f"Event '{rule.event_id}' was not found")
    if event.status == "final":
        raise _invalid("event_not_open", "This event has already finished")
    if rule.kind == "game_start" and event.status != "upcoming":
        raise _invalid("event_not_open", "This event has already started")
    rule.label, rule.league = _event_label(board, event)[:200], event.league
    if rule.kind not in ("price_at_least", "line_move"):
        return

    market, outcome = rule.market or "", rule.outcome_key or ""
    if market not in event.markets:
        raise _invalid(
            "market_not_available",
            f"Market '{market}' is not offered for this event",
            available_markets=event.markets,
        )
    three_way = any(
        league.has_draw for league in provider.list_leagues() if league.key == event.league
    )
    allowed = valid_outcome_keys(market, three_way)
    if outcome not in allowed:
        raise _invalid(
            "invalid_selection",
            f"Outcome '{outcome}' is not valid for {market} on this event",
            valid_outcome_keys=list(allowed),
        )
    if rule.kind == "price_at_least":
        if market == "moneyline" and rule.line is not None:
            raise _invalid("invalid_selection", "A moneyline alert does not take a line")
        if market != "moneyline" and rule.line is None:
            raise _invalid("invalid_selection", f"A {market} alert needs a line")
        return
    baseline = board.consensus_outcome_line(event, market, outcome)
    if baseline is None:
        raise _invalid(
            "line_not_available",
            f"No open, current {market} line is available for this event right now",
        )
    rule.baseline_line = _line(baseline)


def mark_finished_games_handled(board: Board, rule: AlertRule) -> None:
    """Team ``game_final`` rules: games that are already over are not news.

    Called when the rule is created or resumed, so it only reports games that end while
    it is active.
    """
    if rule.kind != "game_final" or rule.team_id is None:
        return
    team = board.provider.get_team(rule.team_id)
    if team is None:
        return
    finished = [e.id for e in _team_events(board, team) if e.status == "final"]
    _add_handled(rule, finished)


def _add_handled(rule: AlertRule, event_ids: list[str]) -> None:
    known = list(rule.fired_event_ids or [])
    merged = known + [event_id for event_id in event_ids if event_id not in known]
    # A new list object, so the JSON column is seen as changed.
    rule.fired_event_ids = merged[-_MAX_HANDLED_EVENTS:]


def _identity(rule: AlertRule) -> tuple[object, ...]:
    return (
        rule.kind,
        rule.event_id,
        rule.team_id,
        rule.market,
        rule.outcome_key,
        rule.line,
        rule.threshold_decimal,
        rule.min_move,
        rule.minutes_before,
    )


def find_active_duplicate(db: Session, user_id: str, rule: AlertRule) -> AlertRule | None:
    """An active rule of this user with exactly the same definition, other than ``rule``."""
    candidates = db.scalars(
        select(AlertRule)
        .where(
            AlertRule.user_id == user_id, AlertRule.state == "active", AlertRule.kind == rule.kind
        )
        .order_by(AlertRule.created_at, AlertRule.id)
    )
    wanted = _identity(rule)
    return next((c for c in candidates if c.id != rule.id and _identity(c) == wanted), None)


def count_rules(db: Session, user_id: str, state: str | None = None) -> int:
    query = select(func.count()).select_from(AlertRule).where(AlertRule.user_id == user_id)
    if state is not None:
        query = query.where(AlertRule.state == state)
    return int(db.scalar(query) or 0)


# --------------------------------------------------------------- serialisation
def _points(value: Decimal) -> str:
    return f"{float(value):g} {'point' if value == 1 else 'points'}"


def _summary(rule: AlertRule, home: str, away: str) -> str:
    market, outcome = rule.market or "", rule.outcome_key or ""
    if rule.kind == "price_at_least" and rule.threshold_decimal is not None:
        selection = templates.selection_label(market, outcome, rule.line, home, away)
        return f"{selection} at {templates.american(rule.threshold_decimal)} or higher"
    if rule.kind == "line_move" and rule.min_move is not None and rule.baseline_line is not None:
        side = templates.side_label(market, outcome, home, away)
        baseline = templates.line_text(market, rule.baseline_line)
        return (
            f"{rule.label} {market} line for {side} moves {_points(rule.min_move)} or more "
            f"from {baseline}"
        )
    if rule.kind == "game_start":
        if rule.team_id is not None:
            return f"Each {rule.label} game, {rule.minutes_before} minutes before the start"
        return f"{rule.label}, {rule.minutes_before} minutes before the start"
    if rule.team_id is not None:
        return f"Final score of each {rule.label} game"
    return f"Final score of {rule.label}"


def rule_out(board: Board, rule: AlertRule) -> AlertRuleOut:
    provider = board.provider
    event = provider.get_event(rule.event_id) if rule.event_id else None
    team = provider.get_team(rule.team_id) if rule.team_id else None
    home, away = "Home team", "Away team"
    if event is not None:
        home = board.team_ref(event.home_team_id).name
        away = board.team_ref(event.away_team_id).name
    return AlertRuleOut(
        id=rule.id,
        kind=rule.kind,  # type: ignore[arg-type]
        state=rule.state,  # type: ignore[arg-type]
        summary=_summary(rule, home, away),
        event_id=rule.event_id,
        team_id=rule.team_id,
        market=rule.market,  # type: ignore[arg-type]
        outcome_key=rule.outcome_key,  # type: ignore[arg-type]
        line=float(rule.line) if rule.line is not None else None,
        threshold=price_out(rule.threshold_decimal) if rule.threshold_decimal is not None else None,
        min_move=float(rule.min_move) if rule.min_move is not None else None,
        baseline_line=float(rule.baseline_line) if rule.baseline_line is not None else None,
        minutes_before=rule.minutes_before,
        label=rule.label,
        league=rule.league,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
        triggered_at=rule.triggered_at,
        available=event is not None or team is not None,
        event=board.event_summary(event) if event is not None else None,
        team=board.team_ref(team.id) if team is not None else None,
    )


# ------------------------------------------------------------------ evaluation
@dataclass(frozen=True)
class EvaluationResult:
    evaluated: int = 0
    fired: int = 0
    expired: int = 0


def snapshot(rule: AlertRule) -> RuleSnapshot:
    return RuleSnapshot(
        id=rule.id,
        kind=rule.kind,
        event_id=rule.event_id,
        team_id=rule.team_id,
        market=rule.market,
        outcome_key=rule.outcome_key,
        line=rule.line,
        threshold_decimal=rule.threshold_decimal,
        min_move=rule.min_move,
        baseline_line=rule.baseline_line,
        minutes_before=rule.minutes_before,
        handled_event_ids=frozenset(rule.fired_event_ids or []),
        arm_count=rule.arm_count,
    )


def _game(board: Board, event: Event) -> GameSnapshot:
    home, away = board.team_ref(event.home_team_id), board.team_ref(event.away_team_id)
    return GameSnapshot(
        id=event.id,
        status=event.status,
        start_time=event.start_time,
        home=home.name,
        away=away.name,
        home_abbr=home.abbreviation,
        away_abbr=away.abbreviation,
        home_score=event.score.home if event.score else None,
        away_score=event.score.away if event.score else None,
    )


def gather_inputs(
    board: Board, rule: AlertRule, league_events: dict[str, list[Event]] | None = None
) -> RuleInputs:
    """Read from the provider what :func:`evaluator.evaluate` needs for ``rule``.

    Prices come from :meth:`Board.best_price`, the same best-price logic the odds
    endpoint uses (open, non-stale books only).
    """
    provider = board.provider
    if rule.team_id is not None:
        team = provider.get_team(rule.team_id)
        if team is None:
            return RuleInputs(team_missing=True)
        cache = league_events if league_events is not None else {}
        if team.league not in cache:
            cache[team.league] = provider.list_events(league=team.league)
        return RuleInputs(
            games=tuple(
                _game(board, event)
                for event in cache[team.league]
                if team.id in (event.home_team_id, event.away_team_id)
            )
        )
    event = provider.get_event(rule.event_id) if rule.event_id else None
    if event is None:
        return RuleInputs()
    games = (_game(board, event),)
    if event.status == "final" or not rule.market or not rule.outcome_key:
        return RuleInputs(games=games)
    if rule.kind == "price_at_least":
        best = board.best_price(
            event,
            rule.market,
            rule.outcome_key,
            float(rule.line) if rule.line is not None else None,
        )
        return RuleInputs(
            games=games,
            best_price=PriceSnapshot(
                price=best.price,
                sportsbook_key=best.sportsbook.key,
                sportsbook_name=best.sportsbook.name,
            )
            if best is not None
            else None,
        )
    if rule.kind == "line_move":
        current = board.consensus_outcome_line(event, rule.market, rule.outcome_key)
        return RuleInputs(
            games=games, consensus_line=_line(current) if current is not None else None
        )
    return RuleInputs(games=games)


def evaluate_user_alerts(
    db: Session,
    user: User,
    now: datetime,
    board: Board,
    request: Request | None = None,
) -> EvaluationResult:
    """Evaluate ``user``'s active rules against the provider state behind ``board``.

    Writes notifications (unless the user disabled the kind), updates rule state and
    audits what happened. Idempotent: a second run right after the first changes
    nothing, because one-shot rules are no longer active and team rules remember the
    games they handled. Safe against a concurrent run: the unique constraint on
    ``(user_id, dedupe_key)`` lets only one of them create a given notification.

    Flushes but does not commit; the caller owns the transaction.
    """
    rules = list(
        db.scalars(
            select(AlertRule)
            .where(AlertRule.user_id == user.id, AlertRule.state == "active")
            .order_by(AlertRule.created_at, AlertRule.id)
        )
    )
    league_events: dict[str, list[Event]] = {}
    fired = expired = delivered = 0
    for rule in rules:
        outcome = evaluate(snapshot(rule), gather_inputs(board, rule, league_events), now)
        if outcome.action == "none":
            continue
        if outcome.action == "expire":
            rule.state = "expired"
            rule.updated_at = utcnow()
            expired += 1
            write_audit(
                db,
                request,
                "alert.expired",
                user_id=user.id,
                entity_type="alert_rule",
                entity_id=rule.id,
                details={"kind": rule.kind},
            )
            continue
        results = [notifications.notify(db, user.id, draft) for draft in outcome.drafts]
        new = sum(1 for result in results if result != "duplicate")
        fired += new
        delivered += results.count("delivered")
        if rule.team_id is None:
            rule.state = "triggered"
            rule.triggered_at = now
        else:
            _add_handled(rule, list(outcome.handled_event_ids))
        rule.updated_at = utcnow()
        if new:
            write_audit(
                db,
                request,
                "alert.fired",
                user_id=user.id,
                entity_type="alert_rule",
                entity_id=rule.id,
                details={
                    "kind": rule.kind,
                    "fired": new,
                    "notified": results.count("delivered"),
                },
            )
    db.flush()
    if delivered:
        notifications.trim(db, user.id)
    return EvaluationResult(evaluated=len(rules), fired=fired, expired=expired)
