"""Intent routing and data tools for the assistant. Deterministic; no model calls.

Every message goes through the responsible-gambling checks in :mod:`.safeguards` before
any intent is matched. When one applies, no data tool runs and the reply is fixed wording.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..bets.service import summarize
from ..board import Board
from ..db import Bet, User
from ..helpline import HELPLINE_CONTACT
from ..providers import Player, Team
from ..quant import QuantError, american_to_decimal, expected_value, no_vig
from ..schemas import price_out
from . import safeguards
from .explainer import Explainer, TemplateExplainer
from .schemas import (
    AssistantResponse,
    AssistantSourceOut,
    AssistantSuggestionOut,
    AssistantSupportOut,
)

logger = logging.getLogger("oddvex.assistant")

_HELP_LINE = f"For adults 21+. If gambling is causing problems, {HELPLINE_CONTACT} (US)."

DISCLAIMER = (
    "OddVex gives information and math, not betting advice or predictions. All sports data "
    f"shown is synthetic sample data. {_HELP_LINE}"
)

REPLAY_DISCLAIMER = (
    "OddVex gives information and math, not betting advice or predictions. The games shown "
    f"are a replay of past results; sportsbook prices and prop lines are simulated. {_HELP_LINE}"
)

_BET_SUMMARY_RE = re.compile(
    r"\b(my (bets?|roi|record|profit|results?|clv|tracker|performance|bankroll|history)"
    r"|how am i doing|bet summary)\b"
)
_EV_RE = re.compile(r"(\bexpected value\b|(?<![a-z])\+?ev\b)")
_NO_VIG_RE = re.compile(r"(no[- ]?vig|\bvig\b|\bjuice\b|overround|\bhold\b|fair (odds|price|prob))")
_MOVEMENT_RE = re.compile(r"(line mov|line history|\bmov(e|ed|ing|ement)\b|\bsteam\b|\bdrift)")
_TREND_RE = re.compile(r"(hit rate|\btrend|\bprops?\b|last \d+|game log)")
_ODDS_RE = re.compile(r"(best (price|odds|line|number)|\bodds\b|\bcompare\b|moneyline|\bprice\b)")
_HELP_RE = re.compile(
    r"(\bhelp\b|what can you|how do i|where (is|do|can)|navigat|get started|^(hi|hello|hey)\b)"
)
_AMERICAN_RE = re.compile(r"(?<![\w.])([+-]\d{3,5})(?![\d.%])")
_PERCENT_RE = re.compile(r"(\d{1,2}(?:\.\d+)?)\s?%")
_WINDOW_RE = re.compile(r"last (\d{1,2})")

_MARKET_WORDS: tuple[tuple[str, str], ...] = (
    ("passing yards", "passing_yards"),
    ("pass yards", "passing_yards"),
    ("rushing yards", "rushing_yards"),
    ("rush yards", "rushing_yards"),
    ("receptions", "receptions"),
    ("catches", "receptions"),
    ("rebounds", "rebounds"),
    ("boards", "rebounds"),
    ("assists", "assists"),
    ("threes", "threes"),
    ("three-pointers", "threes"),
    ("3-pointers", "threes"),
    ("strikeouts", "strikeouts"),
    ("shots", "shots"),
    ("hits", "hits"),
    ("points", "points"),
)


@dataclass
class ToolResult:
    """What a tool found. ``facts`` is the only input the explainer gets.

    ``fixed_answer`` is set by the responsible-gambling replies: it is the whole answer and
    the explainer is not asked. ``support_case`` says which support reply it is.
    """

    intent: str
    facts: dict[str, Any]
    sources: list[AssistantSourceOut] = field(default_factory=list)
    suggestions: list[AssistantSuggestionOut] = field(default_factory=list)
    has_data: bool = True
    fixed_answer: str | None = None
    support_case: safeguards.SupportCase | None = None


def _suggest(label: str, href: str) -> AssistantSuggestionOut:
    return AssistantSuggestionOut(label=label, href=href)


def _word_in(needle: str, haystack: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", haystack) is not None


class Assistant:
    def __init__(
        self,
        board: Board,
        db: Session | None = None,
        user: User | None = None,
        explainer: Explainer | None = None,
    ) -> None:
        self.board = board
        self.db = db
        self.user = user
        self.explainer: Explainer = explainer or TemplateExplainer()

    # ------------------------------------------------------------------ entry
    def answer(self, message: str) -> AssistantResponse:
        result = self.route(message)
        if result.support_case is not None:
            # A count for operations. Never the message, and nothing that identifies anyone.
            logger.info(
                "assistant_support_reply",
                extra={"case": result.support_case, "signed_in": self.user is not None},
            )
        return AssistantResponse(
            intent=result.intent,  # type: ignore[arg-type]
            answer=result.fixed_answer
            if result.fixed_answer is not None
            else self.explainer.explain(result.intent, result.facts),
            data=result.facts if result.has_data else None,
            sources=result.sources,
            suggestions=result.suggestions,
            disclaimer=DISCLAIMER
            if self.board.provider.data_mode == "synthetic"
            else REPLAY_DISCLAIMER,
            support=AssistantSupportOut(case=result.support_case)
            if result.support_case is not None
            else None,
        )

    def route(self, message: str) -> ToolResult:
        """Responsible-gambling checks first, then the keyword / regex intent router.

        In the router the first match wins, most specific first. The checks run before it
        so that a team name, a player name or "my record" in the same message cannot pull
        in betting data.
        """
        signals = safeguards.detect(message)
        if signals.case is not None:
            return self.support(signals)
        if signals.certainty:
            return self.no_certainty()
        text = " ".join(message.lower().split())
        if _BET_SUMMARY_RE.search(text):
            return self.bet_summary()
        if _EV_RE.search(text):
            return self.explain_ev(message)
        if _NO_VIG_RE.search(text):
            return self.explain_no_vig(message)
        players = self._find_players(text)
        if players:
            return self.player_trend(players, text)
        team = self._find_team(message, text)
        if _MOVEMENT_RE.search(text):
            return self.line_movement(team, text)
        if team is not None:
            return self.compare_odds(team, text)
        if _TREND_RE.search(text):
            return self.player_trend([], text)
        if _ODDS_RE.search(text):
            return self.compare_odds(None, text)
        if _HELP_RE.search(text):
            return self.help()
        return self.fallback()

    # --------------------------------------------------------------- entities
    def _find_team(self, original: str, text: str) -> Team | None:
        teams = self.board.provider.list_teams()
        for attribute in ("name", "nickname", "city"):
            candidates = sorted(teams, key=lambda t: -len(getattr(t, attribute)))
            for team in candidates:
                if _word_in(getattr(team, attribute).lower(), text):
                    return team
        tokens = set(re.findall(r"\b[A-Z]{3}\b", original))
        for team in teams:
            if team.abbreviation in tokens:
                return team
        return None

    def _find_players(self, text: str) -> list[Player]:
        players = self.board.provider.list_players()
        full = [p for p in players if _word_in(p.name.lower(), text)]
        if full:
            return full
        return [p for p in players if _word_in(p.name.lower().split()[-1], text)]

    def _source(self, label: str, data_mode: str | None = None) -> AssistantSourceOut:
        """A source line, prefixed with the provider's data mode unless a mode is given."""
        if data_mode is None:
            data_mode = self.board.provider.data_mode
            label = f"{data_mode.capitalize()} {label}"
        return AssistantSourceOut(label=label, as_of=self.board.now, data_mode=data_mode)

    # ----------------------------------------------- responsible-gambling replies
    def support(self, signals: safeguards.Signals) -> ToolResult:
        """Crisis, under 21 or distress: help only. No data tool runs and no bet is read."""
        case = signals.case
        if case is None:
            raise ValueError("no support case")
        suggestions = [_suggest(safeguards.RESOURCES_LABEL, safeguards.RESOURCES_HREF)]
        if case == "distress":
            suggestions += [
                _suggest(safeguards.REMINDER_LABEL, safeguards.REMINDER_HREF),
                _suggest(safeguards.TRACKER_LABEL, safeguards.TRACKER_HREF),
            ]
        return ToolResult(
            "support",
            {
                "case": case,
                "distress": signals.distress,
                "chasing_losses": signals.chasing_losses,
            },
            suggestions=suggestions,
            has_data=False,
            fixed_answer=safeguards.reply(signals),
            support_case=case,
        )

    def no_certainty(self) -> ToolResult:
        """A request for a certain winner: no result is certain; market data is on offer."""
        return ToolResult(
            "fallback",
            {"reason": "certainty"},
            suggestions=[
                _suggest("Odds board", "/app/odds"),
                _suggest("Calculators", "/app/tools"),
            ],
            has_data=False,
            fixed_answer=safeguards.NO_CERTAINTY_REPLY,
        )

    # ------------------------------------------------------------------ tools
    def compare_odds(self, team: Team | None, text: str) -> ToolResult:
        if team is None:
            return ToolResult(
                "compare_odds",
                {"status": "no_team"},
                suggestions=[_suggest("Browse the odds board", "/app/odds")],
                has_data=False,
            )
        event = self.board.provider.next_event_for_team(team.id)
        if event is None:
            return ToolResult(
                "compare_odds",
                {"status": "no_event", "team": team.name},
                suggestions=[_suggest("Browse the odds board", "/app/odds")],
            )
        market = "spread" if "spread" in text and "spread" in event.markets else "moneyline"
        side = "home" if event.home_team_id == team.id else "away"
        odds = self.board.event_odds(event, market)
        best = next((b for b in odds.best if b.outcome_key == side), None)
        consensus = next((c for c in odds.consensus.outcomes if c.key == side), None)
        facts: dict[str, Any] = {
            "status": "ok" if best else "no_open_prices",
            "team": team.name,
            "side": side,
            "market": market,
            "event_id": event.id,
            "home_team": odds.event.home_team.name,
            "away_team": odds.event.away_team.name,
            "start_time": event.start_time.isoformat(),
            "event_status": event.status,
            "books_compared": odds.consensus.books_used,
            "no_vig_probability": consensus.no_vig_probability if consensus else None,
            "best": None,
            "prices": [
                {
                    "sportsbook": book.sportsbook.name,
                    "status": book.status,
                    "is_stale": book.is_stale,
                    "american": outcome.price.american,
                    "line": outcome.line,
                }
                for book in odds.books
                for outcome in book.outcomes
                if outcome.key == side
            ],
        }
        if best:
            facts["best"] = {
                "sportsbook": self.board.book_ref(best.sportsbook_key).name,
                "american": best.price.american,
                "decimal": best.price.decimal,
                "implied_probability": best.price.implied_probability,
                "line": best.line,
            }
        return ToolResult(
            "compare_odds",
            facts,
            sources=[self._source(f"odds feed: {market}, {event.id}")],
            suggestions=[
                _suggest("Open this game", f"/app/games/{event.id}"),
                _suggest("Browse the odds board", "/app/odds"),
            ],
        )

    def line_movement(self, team: Team | None, text: str) -> ToolResult:
        if team is None:
            return ToolResult(
                "line_movement",
                {"status": "no_team"},
                suggestions=[_suggest("Browse the odds board", "/app/odds")],
                has_data=False,
            )
        event = self.board.provider.next_event_for_team(team.id)
        if event is None:
            return ToolResult("line_movement", {"status": "no_event", "team": team.name})
        side = "home" if event.home_team_id == team.id else "away"
        history = self.board.line_history(event, "moneyline")
        series = [s for s in history.series if s.outcome_key == side and len(s.points) >= 2]
        suggestions = [_suggest("Open this game", f"/app/games/{event.id}")]
        base = {
            "team": team.name,
            "market": "moneyline",
            "event_id": event.id,
            "home_team": history.event.home_team.name,
            "away_team": history.event.away_team.name,
        }
        if not series:
            return ToolResult(
                "line_movement", {"status": "no_history", **base}, suggestions=suggestions
            )
        moves: list[dict[str, Any]] = [
            {
                "sportsbook": s.sportsbook.name,
                "open_american": s.points[0].price.american,
                "current_american": s.points[-1].price.american,
                "open_implied": s.points[0].price.implied_probability,
                "current_implied": s.points[-1].price.implied_probability,
                "open_at": s.points[0].timestamp.isoformat(),
                "current_at": s.points[-1].timestamp.isoformat(),
            }
            for s in series
        ]
        open_implied = sum(m["open_implied"] for m in moves) / len(moves)
        current_implied = sum(m["current_implied"] for m in moves) / len(moves)
        change = current_implied - open_implied
        largest = max(moves, key=lambda m: abs(m["current_implied"] - m["open_implied"]))
        span = series[0].points[-1].timestamp - series[0].points[0].timestamp
        facts = {
            "status": "ok",
            **base,
            "side": side,
            "books": len(moves),
            "hours": round(span.total_seconds() / 3600),
            "open_implied": round(open_implied, 6),
            "current_implied": round(current_implied, 6),
            "direction": "flat"
            if abs(change) < 0.005
            else "shortened"
            if change > 0
            else "drifted",
            "largest_move": largest,
            "moves": moves,
        }
        return ToolResult(
            "line_movement",
            facts,
            sources=[self._source(f"line history: moneyline, {event.id}")],
            suggestions=suggestions,
        )

    def player_trend(self, players: list[Player], text: str) -> ToolResult:
        if not players:
            return ToolResult(
                "player_trend",
                {"status": "no_player"},
                suggestions=[_suggest("Browse player props", "/app/props")],
                has_data=False,
            )
        if len(players) > 1:
            return ToolResult(
                "player_trend",
                {
                    "status": "ambiguous_player",
                    "query": players[0].name.split()[-1],
                    "candidates": [p.name for p in players[:6]],
                },
                suggestions=[_suggest(p.name, f"/app/props/{p.id}") for p in players[:6]],
            )
        player = players[0]
        market = next(
            (key for word, key in _MARKET_WORDS if word in text and key in player.prop_markets),
            player.prop_markets[0],
        )
        window = "10"
        match = _WINDOW_RE.search(text)
        if "season" in text:
            window = "season"
        elif match:
            window = min(("5", "10", "20"), key=lambda w: abs(int(w) - int(match.group(1))))
        props = self.board.player_props(player, market, window, "all")
        rate = props.hit_rate
        facts = {
            "status": "ok",
            "player": player.name,
            "player_id": player.id,
            "market": market,
            "window": window,
            "games": len(props.game_log),
            "line": rate.line,
            "line_source": rate.line_source,
            "over_count": rate.over_count,
            "sample_size": rate.sample_size,
            "pushes": rate.pushes,
            "rate": rate.rate,
            "ci_low": rate.ci_low,
            "ci_high": rate.ci_high,
            "average_window": props.averages.window,
            "average_season": props.averages.season,
            "next_opponent": props.opponent.name if props.opponent else None,
            "caveat": props.caveat,
        }
        return ToolResult(
            "player_trend",
            facts,
            sources=[self._source(f"game log and prop lines: {player.id}, {market}")],
            suggestions=[
                _suggest(f"Open {player.name}'s props", f"/app/props/{player.id}"),
                _suggest("Browse player props", "/app/props"),
            ],
        )

    def bet_summary(self) -> ToolResult:
        if self.user is None or self.db is None:
            return ToolResult(
                "bet_summary",
                {"status": "not_authenticated"},
                suggestions=[_suggest("Log in", "/login"), _suggest("Bet tracker", "/app/tracker")],
                has_data=False,
            )
        bets = list(self.db.scalars(select(Bet).where(Bet.user_id == self.user.id)))
        suggestions = [_suggest("Open your tracker", "/app/tracker")]
        if not bets:
            return ToolResult(
                "bet_summary", {"status": "no_bets"}, suggestions=suggestions, has_data=False
            )
        totals = summarize(bets).totals
        return ToolResult(
            "bet_summary",
            {"status": "ok", **totals.model_dump()},
            sources=[
                AssistantSourceOut(
                    label="Your tracked bets",
                    as_of=datetime.now(self.board.now.tzinfo),
                    data_mode="user",
                )
            ],
            suggestions=suggestions,
        )

    def explain_ev(self, message: str) -> ToolResult:
        american, probability, status = 150, 0.45, "example"
        prices = _AMERICAN_RE.findall(message)
        percents = _PERCENT_RE.findall(message)
        if prices and percents:
            try:
                candidate = int(prices[0])
                candidate_p = float(percents[0]) / 100
                expected_value(candidate_p, american_to_decimal(candidate))
                american, probability, status = candidate, candidate_p, "computed"
            except QuantError:
                pass
        decimal = american_to_decimal(american)
        result = expected_value(probability, decimal)
        return ToolResult(
            "explain_ev",
            {
                "status": status,
                "american": american,
                "decimal": round(float(decimal), 4),
                "win_probability": probability,
                "ev_per_unit": round(result.ev_per_unit, 6),
                "ev_percent": round(result.ev_percent, 4),
                "breakeven_probability": round(result.breakeven_probability, 6),
            },
            sources=[self._source("OddVex quant library: expected value", "calculation")],
            suggestions=[_suggest("Open the calculators", "/app/tools")],
        )

    def explain_no_vig(self, message: str) -> ToolResult:
        americans, status = [-110, -110], "example"
        prices = _AMERICAN_RE.findall(message)
        if 2 <= len(prices) <= 3:
            try:
                candidates = [int(p) for p in prices]
                no_vig([american_to_decimal(c) for c in candidates])
                americans, status = candidates, "computed"
            except QuantError:
                pass
        decimals = [american_to_decimal(a) for a in americans]
        result = no_vig(decimals)
        return ToolResult(
            "explain_no_vig",
            {
                "status": status,
                "outcomes": [
                    {
                        "american": american,
                        "decimal": price_out(decimal).decimal,
                        "implied_probability": round(implied, 6),
                        "no_vig_probability": round(fair, 6),
                    }
                    for american, decimal, implied, fair in zip(
                        americans,
                        decimals,
                        result.implied_probabilities,
                        result.fair_probabilities,
                        strict=True,
                    )
                ],
                "overround": round(result.overround, 6),
                "hold": round(result.hold, 6),
            },
            sources=[self._source("OddVex quant library: no-vig (proportional)", "calculation")],
            suggestions=[_suggest("Open the calculators", "/app/tools")],
        )

    def help(self) -> ToolResult:
        return ToolResult(
            "help",
            {
                "data_note": "all sports data here is synthetic sample data"
                if self.board.provider.data_mode == "synthetic"
                else "the games here are a replay of past results with simulated prices"
            },
            suggestions=[
                _suggest("Odds board", "/app/odds"),
                _suggest("Player props", "/app/props"),
                _suggest("Calculators", "/app/tools"),
                _suggest("Bet tracker", "/app/tracker"),
            ],
            has_data=False,
        )

    def fallback(self) -> ToolResult:
        return ToolResult(
            "fallback",
            {},
            suggestions=[
                _suggest("Odds board", "/app/odds"),
                _suggest("Calculators", "/app/tools"),
            ],
            has_data=False,
        )
