"""Decide what an alert rule does given the current state of the world.

Pure: no database, no provider, no clock. :func:`evaluate` takes a snapshot of the rule,
the facts it needs (gathered by ``alerts.service``) and "now", and returns whether the rule
fires, expires or does nothing, plus the notifications to deliver.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from ..notifications import templates
from ..notifications.templates import NotificationDraft

Action = Literal["fire", "expire", "none"]

_ODDS_QUANTUM = Decimal("0.000001")


@dataclass(frozen=True)
class RuleSnapshot:
    id: str
    kind: str
    event_id: str | None = None
    team_id: str | None = None
    market: str | None = None
    outcome_key: str | None = None
    line: Decimal | None = None
    threshold_decimal: Decimal | None = None
    min_move: Decimal | None = None
    baseline_line: Decimal | None = None
    minutes_before: int | None = None
    handled_event_ids: frozenset[str] = frozenset()
    arm_count: int = 0

    @property
    def one_shot(self) -> bool:
        """Event-scoped rules fire once; team-scoped rules fire once per game."""
        return self.team_id is None


@dataclass(frozen=True)
class GameSnapshot:
    id: str
    status: str
    start_time: datetime
    home: str
    away: str
    home_abbr: str = ""
    away_abbr: str = ""
    home_score: int | None = None
    away_score: int | None = None


@dataclass(frozen=True)
class PriceSnapshot:
    """Best open, non-stale price for the rule's outcome (at the rule's line)."""

    price: Decimal
    sportsbook_key: str
    sportsbook_name: str


@dataclass(frozen=True)
class RuleInputs:
    #: Event-scoped rule: the event, or nothing when the provider no longer has it.
    #: Team-scoped rule: the team's events the provider currently serves.
    games: tuple[GameSnapshot, ...] = ()
    #: Team-scoped rule only: the provider no longer has the team.
    team_missing: bool = False
    best_price: PriceSnapshot | None = None
    consensus_line: Decimal | None = None


@dataclass(frozen=True)
class Outcome:
    action: Action
    drafts: tuple[NotificationDraft, ...] = ()
    #: Team-scoped rules: events that are now handled and must not fire again.
    handled_event_ids: tuple[str, ...] = ()


NOTHING = Outcome("none")
EXPIRE = Outcome("expire")


def dedupe_key(rule: RuleSnapshot, event_id: str) -> str:
    """Stable per rule, arming and event, so a notification is never created twice."""
    return f"alert:{rule.id}:{rule.arm_count}:{event_id}"


def price_meets(best: Decimal, threshold: Decimal) -> bool:
    """``best >= threshold`` at the precision prices are stored with (6 decimal places)."""
    return best.quantize(_ODDS_QUANTUM, rounding=ROUND_HALF_UP) >= threshold.quantize(
        _ODDS_QUANTUM, rounding=ROUND_HALF_UP
    )


def line_moved(baseline: Decimal, current: Decimal, min_move: Decimal) -> bool:
    return abs(current - baseline) >= min_move


def starts_within(start_time: datetime, now: datetime, minutes_before: int) -> bool:
    """True from ``minutes_before`` minutes before the start (inclusive) until the start."""
    seconds = (start_time - now).total_seconds()
    return 0 < seconds <= minutes_before * 60


def evaluate(rule: RuleSnapshot, inputs: RuleInputs, now: datetime) -> Outcome:
    if rule.kind == "price_at_least":
        return _price_at_least(rule, inputs)
    if rule.kind == "line_move":
        return _line_move(rule, inputs)
    if rule.kind == "game_start":
        return _game_start(rule, inputs, now)
    if rule.kind == "game_final":
        return _game_final(rule, inputs)
    return NOTHING


def _open_game(inputs: RuleInputs) -> GameSnapshot | None:
    """The rule's event while it can still fire; ``None`` when it is gone or final."""
    game = inputs.games[0] if inputs.games else None
    return game if game is not None and game.status != "final" else None


def _price_at_least(rule: RuleSnapshot, inputs: RuleInputs) -> Outcome:
    game = _open_game(inputs)
    if game is None:
        return EXPIRE
    best = inputs.best_price
    if (
        best is None
        or rule.threshold_decimal is None
        or rule.market is None
        or rule.outcome_key is None
        or not price_meets(best.price, rule.threshold_decimal)
    ):
        return NOTHING
    return Outcome(
        "fire",
        (
            templates.price_alert(
                rule_id=rule.id,
                dedupe_key=dedupe_key(rule, game.id),
                event_id=game.id,
                market=rule.market,
                outcome_key=rule.outcome_key,
                line=rule.line,
                home=game.home,
                away=game.away,
                price_decimal=best.price,
                threshold_decimal=rule.threshold_decimal,
                sportsbook_key=best.sportsbook_key,
                sportsbook_name=best.sportsbook_name,
            ),
        ),
    )


def _line_move(rule: RuleSnapshot, inputs: RuleInputs) -> Outcome:
    game = _open_game(inputs)
    if game is None:
        return EXPIRE
    current = inputs.consensus_line
    if (
        current is None
        or rule.baseline_line is None
        or rule.min_move is None
        or rule.market is None
        or rule.outcome_key is None
        or not line_moved(rule.baseline_line, current, rule.min_move)
    ):
        return NOTHING
    return Outcome(
        "fire",
        (
            templates.line_move(
                rule_id=rule.id,
                dedupe_key=dedupe_key(rule, game.id),
                event_id=game.id,
                market=rule.market,
                outcome_key=rule.outcome_key,
                home=game.home,
                away=game.away,
                baseline=rule.baseline_line,
                current=current,
            ),
        ),
    )


def _start_draft(rule: RuleSnapshot, game: GameSnapshot) -> NotificationDraft:
    return templates.game_start(
        rule_id=rule.id,
        dedupe_key=dedupe_key(rule, game.id),
        event_id=game.id,
        home=game.home,
        away=game.away,
        start_time=game.start_time,
        minutes_before=rule.minutes_before or 0,
    )


def _game_start(rule: RuleSnapshot, inputs: RuleInputs, now: datetime) -> Outcome:
    if rule.minutes_before is None:
        return NOTHING
    if rule.one_shot:
        game = inputs.games[0] if inputs.games else None
        # A game that already started can no longer get a "starts at" notification.
        if game is None or game.status != "upcoming" or game.start_time <= now:
            return EXPIRE
        if not starts_within(game.start_time, now, rule.minutes_before):
            return NOTHING
        return Outcome("fire", (_start_draft(rule, game),))
    if inputs.team_missing:
        return EXPIRE
    due = [
        game
        for game in sorted(inputs.games, key=lambda g: (g.start_time, g.id))
        if game.status == "upcoming"
        and game.id not in rule.handled_event_ids
        and starts_within(game.start_time, now, rule.minutes_before)
    ]
    if not due:
        return NOTHING
    return Outcome(
        "fire", tuple(_start_draft(rule, game) for game in due), tuple(game.id for game in due)
    )


def _final_draft(rule: RuleSnapshot, game: GameSnapshot) -> NotificationDraft:
    return templates.game_final(
        rule_id=rule.id,
        dedupe_key=dedupe_key(rule, game.id),
        event_id=game.id,
        home=game.home,
        away=game.away,
        home_abbr=game.home_abbr,
        away_abbr=game.away_abbr,
        home_score=game.home_score or 0,
        away_score=game.away_score or 0,
    )


def _is_final(game: GameSnapshot) -> bool:
    return game.status == "final" and game.home_score is not None and game.away_score is not None


def _game_final(rule: RuleSnapshot, inputs: RuleInputs) -> Outcome:
    if rule.one_shot:
        game = inputs.games[0] if inputs.games else None
        if game is None:
            return EXPIRE
        return Outcome("fire", (_final_draft(rule, game),)) if _is_final(game) else NOTHING
    if inputs.team_missing:
        return EXPIRE
    done = [
        game
        for game in sorted(inputs.games, key=lambda g: (g.start_time, g.id))
        if _is_final(game) and game.id not in rule.handled_event_ids
    ]
    if not done:
        return NOTHING
    return Outcome(
        "fire", tuple(_final_draft(rule, game) for game in done), tuple(game.id for game in done)
    )
