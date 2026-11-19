"""Turning tool output into prose. Templates only: every number is copied from ``facts``.

The responsible-gambling replies (``safeguards.py``) are fixed wording and do not come
through an explainer.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Explainer(Protocol):
    """Phrases facts a tool produced. Implementations must not introduce new numbers.

    An explainer is never asked to phrase a responsible-gambling reply.
    """

    def explain(self, intent: str, facts: dict[str, Any]) -> str: ...


def _american(value: int) -> str:
    return f"+{value}" if value > 0 else str(value)


def _pct(value: float, places: int = 1) -> str:
    return f"{value * 100:.{places}f}%"


def _when(iso: str) -> str:
    return iso[:16].replace("T", " ") + " UTC"


class TemplateExplainer:
    def explain(self, intent: str, facts: dict[str, Any]) -> str:
        handler = getattr(self, f"_{intent}", None)
        if handler is None:
            return self._fallback(facts)
        return str(handler(facts))

    # ---------------------------------------------------------------- intents
    def _compare_odds(self, f: dict[str, Any]) -> str:
        status = f["status"]
        if status == "no_team":
            return (
                "I can compare prices for a team, but I couldn't match a team name in your "
                "message. Try the full name of a team on the odds screen."
            )
        if status == "no_event":
            return f"I couldn't find an upcoming or live game for {f['team']}."
        matchup = f"{f['away_team']} at {f['home_team']}"
        timing = "live now" if f["event_status"] == "live" else f"starts {_when(f['start_time'])}"
        if status == "no_open_prices":
            return (
                f"No sportsbook has an open, up-to-date {f['market']} price for {f['team']} "
                f"right now ({matchup}, {timing}). Markets can be suspended or stale; the game "
                "page shows each book's status."
            )
        best = f["best"]
        line = f" {best['line']:+g}" if best.get("line") is not None else ""
        text = (
            f"Best {f['market']} price for {f['team']}{line} ({matchup}, {timing}): "
            f"{_american(best['american'])} (decimal {best['decimal']:.2f}) at "
            f"{best['sportsbook']}, out of {f['books_compared']} open, up-to-date "
            f"{'book' if f['books_compared'] == 1 else 'books'}."
        )
        if f.get("no_vig_probability") is not None:
            text += (
                f" The no-vig consensus across those books is {_pct(f['no_vig_probability'])}; "
                "that is the market's margin-free price, not a prediction."
            )
        return text

    def _line_movement(self, f: dict[str, Any]) -> str:
        status = f["status"]
        if status == "no_team":
            return (
                "I can describe line movement for a team's next game, but I couldn't match a "
                "team name in your message."
            )
        if status == "no_event":
            return f"I couldn't find a game for {f['team']} to check line movement on."
        if status == "no_history":
            return f"There is no {f['market']} price history for {f['team']}'s game yet."
        direction = {
            "shortened": "shortened (the price got lower, implying a higher chance)",
            "drifted": "drifted (the price got longer, implying a lower chance)",
            "flat": "barely moved",
        }[f["direction"]]
        mover = f["largest_move"]
        return (
            f"Over about the last {f['hours']} hours the {f['market']} on {f['team']} "
            f"({f['away_team']} at {f['home_team']}) has {direction}: the average implied "
            f"probability across {f['books']} books went from {_pct(f['open_implied'])} to "
            f"{_pct(f['current_implied'])}. The largest move was at {mover['sportsbook']}, "
            f"from {_american(mover['open_american'])} to {_american(mover['current_american'])}. "
            "Movement describes what prices did; it does not say what happens next."
        )

    def _player_trend(self, f: dict[str, Any]) -> str:
        status = f["status"]
        if status == "no_player":
            return (
                "I can look up a player's recent results against a prop line, but I couldn't "
                "match a player name in your message. Try their full name."
            )
        if status == "ambiguous_player":
            return (
                f'More than one player matches "{f["query"]}": '
                + ", ".join(f["candidates"])
                + ". Which one did you mean?"
            )
        market = f["market"].replace("_", " ")
        scope = "this season" if f["window"] == "season" else f"their last {f['games']} games"
        if f["sample_size"] == 0:
            return (
                f"{f['player']} has no graded games for {market} against a line of "
                f"{f['line']:g} in {scope}."
            )
        line_note = (
            ""
            if f["line_source"] == "consensus"
            else " (no book is offering this market right now, so a reference line near the "
            "season median was used)"
        )
        pushes = (
            f" {f['pushes']} landed exactly on the line and are excluded." if f["pushes"] else ""
        )
        return (
            f"Across {scope}, {f['player']} went over {f['line']:g} {market}{line_note} in "
            f"{f['over_count']} of {f['sample_size']} graded games ({_pct(f['rate'])}; 95% "
            f"interval {_pct(f['ci_low'])} to {_pct(f['ci_high'])}).{pushes} Average over that "
            f"span: {f['average_window']:g}; season average: {f['average_season']:g}. "
            "This is a historical frequency from a small sample, not a prediction."
        )

    def _bet_summary(self, f: dict[str, Any]) -> str:
        if f["status"] == "not_authenticated":
            return "Log in to see a summary of your tracked bets. I can only read your own bets."
        if f["status"] == "no_bets":
            return (
                "You haven't tracked any bets yet. Add one in the tracker and I can summarise it."
            )
        text = (
            f"You have {f['settled_count']} settled "
            f"{'bet' if f['settled_count'] == 1 else 'bets'}: {f['wins']} won, {f['losses']} "
            f"lost, {f['pushes']} pushed or void. Staked {f['staked']:.2f}, profit "
            f"{f['profit']:+.2f}"
        )
        text += f", ROI {f['roi'] * 100:+.1f}%." if f.get("roi") is not None else "."
        if f["pending_count"]:
            text += f" {f['pending_count']} pending with {f['pending_exposure']:.2f} at stake."
        if f.get("avg_clv") is not None:
            text += (
                f" Average closing line value: {f['avg_clv'] * 100:+.2f}% over "
                f"{f['clv_sample']} {'bet' if f['clv_sample'] == 1 else 'bets'} with closing "
                "prices."
            )
        return text + " Past results do not predict future results."

    def _explain_ev(self, f: dict[str, Any]) -> str:
        lead = (
            "Using the numbers in your message"
            if f["status"] == "computed"
            else "Expected value (EV) is the average profit per unit staked if the same bet "
            "could be repeated many times. Worked example"
        )
        return (
            f"{lead}: at {_american(f['american'])} (decimal {f['decimal']:.2f}) with a win "
            f"probability of {_pct(f['win_probability'])}, EV = p x (decimal - 1) - (1 - p) = "
            f"{f['ev_per_unit']:+.4f} per unit, or {f['ev_percent']:+.2f}%. The break-even "
            f"probability at that price is {_pct(f['breakeven_probability'])}. EV is only as "
            "good as the win probability you put in; OddVex does not estimate it for you."
        )

    def _explain_no_vig(self, f: dict[str, Any]) -> str:
        lead = (
            "Using the prices in your message"
            if f["status"] == "computed"
            else "A sportsbook's prices imply probabilities that add up to more than 100%; the "
            "extra is the margin (vig). Removing it proportionally gives no-vig probabilities. "
            "Worked example"
        )
        prices = " / ".join(_american(o["american"]) for o in f["outcomes"])
        implied = " + ".join(_pct(o["implied_probability"], 2) for o in f["outcomes"])
        fair = " / ".join(_pct(o["no_vig_probability"], 2) for o in f["outcomes"])
        return (
            f"{lead}: {prices} implies {implied}, an overround of {_pct(f['overround'], 2)} "
            f"(hold {_pct(f['hold'], 2)}). Dividing each by the total gives no-vig "
            f"probabilities of {fair}. That is the market's own estimate with the margin "
            "removed, not a forecast."
        )

    def _help(self, f: dict[str, Any]) -> str:
        data_note = f.get("data_note", "all sports data here is synthetic sample data")
        return (
            'I can: find the best current price for a team ("best odds for <team>"), show a '
            'player\'s recent results against a prop line ("<player> points last 10"), describe '
            "line movement for a team's game, explain expected value and no-vig math, and "
            "summarise your tracked bets when you're logged in. I answer from OddVex data and "
            f"calculators only, and {data_note}."
        )

    def _fallback(self, f: dict[str, Any]) -> str:
        return (
            "I can't answer that. I'm a rule-based helper, not a general chatbot, and I only "
            "answer from OddVex's data and calculators. I don't make picks or predictions. "
            "Ask me for the best odds for a team, a player's recent prop results, line "
            "movement, EV or no-vig math, or your bet summary."
        )
