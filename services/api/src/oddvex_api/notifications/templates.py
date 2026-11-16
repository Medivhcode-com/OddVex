"""Every notification's wording, in one place.

Copy rules (a compliance requirement, enforced by ``tests/test_notification_copy.py``):
neutral and factual, sentence case, no instruction to bet, no urgency, no hype, no
exclamation marks. Prices are American with an explicit sign. No probabilities: a
notification never carries a number the quant engine did not produce.

This module is pure: it formats values it is given and does no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from ..quant import describe_price

#: ``kind -> {name: template}``. Every user-visible string is built from these.
TEMPLATES: dict[str, dict[str, str]] = {
    "price_alert": {
        "title": "Price reached {price}",
        "body": "{selection} is {price} at {sportsbook}, at or above your {threshold} alert.",
    },
    "line_move": {
        "title": "Line moved to {current}",
        "body": (
            "{matchup} {market}: the consensus line for {side} is {current}. "
            "It was {baseline} when you set this alert."
        ),
    },
    "game_start": {
        "title": "Game starts at {start}",
        "body": (
            "{matchup} starts at {start} on {day}. "
            "Your alert is set for {minutes} minutes before the start."
        ),
    },
    "game_final": {
        "title": "Final: {away_abbr} {away_score}, {home_abbr} {home_score}",
        "body": "Final score: {away} {away_score}, {home} {home_score}.",
    },
    "bet_settled": {
        "title": "Bet settled: {result}",
        "body": "Your {stake} bet at {sportsbook} settled as {result}. Profit: {profit}.",
    },
    "sync_finished": {
        "title": "Import finished",
        "body": "{label} import finished: {imported} new, {duplicates} already imported.",
        "title_failed": "Import did not finish",
        "body_failed": (
            "{label} import did not finish after {attempts} attempt(s). No bets were added."
        ),
    },
    "stake_reminder": {
        "title": "Weekly staking reminder",
        "body": (
            "You have staked {staked} this week, at or above the {threshold} reminder you "
            "set. This is a reminder, not a limit. Free, confidential help is available at "
            "1-800-GAMBLER."
        ),
    },
    # Community. Facts only: who did what, and how a pick was graded. No comment text, no
    # praise, no nudge to post or to bet.
    "new_follower": {
        "title": "New follower",
        "body": "@{handle} follows your community profile.",
    },
    "pick_comment": {
        "title": "New comment on your pick",
        "body": "@{handle} commented on your pick: {selection}.",
    },
    "pick_graded": {
        "title": "Pick graded: {result}",
        "body": (
            "Your pick, {selection}, was graded as {result}. "
            "Final score: {event_label}, {away_score} to {home_score}."
        ),
    },
}

_RESULT_WORDS = {
    "won": "won",
    "lost": "lost",
    "push": "push",
    "void": "void",
    "half_won": "half won",
    "half_lost": "half lost",
    "cashout": "cashout",
}


@dataclass(frozen=True)
class NotificationDraft:
    """A notification that has not been delivered yet."""

    kind: str
    title: str
    body: str
    href: str
    dedupe_key: str
    data: dict[str, Any] = field(default_factory=dict)
    rule_id: str | None = None


# ------------------------------------------------------------------ formatting
def american(decimal_odds: Decimal | float) -> str:
    """American odds with an explicit sign: ``+150``, ``-110``."""
    return f"{describe_price(decimal_odds).american:+d}"


def signed_line(line: Decimal | float) -> str:
    """A spread line with its sign: ``-3.5``, ``+3.5``."""
    return f"{float(line):+g}"


def plain_line(line: Decimal | float) -> str:
    return f"{float(line):g}"


def money(amount: Decimal | float) -> str:
    return f"${abs(float(amount)):,.2f}"


def signed_money(amount: Decimal | float) -> str:
    return f"{'-' if float(amount) < 0 else '+'}{money(amount)}"


def clock(moment: datetime) -> str:
    return f"{moment:%H:%M} UTC"


def matchup(home: str, away: str) -> str:
    return f"{away} at {home}"


def line_text(market: str, line: Decimal | float) -> str:
    return signed_line(line) if market == "spread" else plain_line(line)


def selection_label(
    market: str, outcome_key: str, line: Decimal | float | None, home: str, away: str
) -> str:
    """What a rule is about, e.g. ``Harbor City Tides moneyline`` or ``Over 224.5 in A at B``."""
    game = matchup(home, away)
    if market == "total":
        side = "Over" if outcome_key == "over" else "Under"
        return f"{side} {plain_line(line or 0)} in {game}"
    if outcome_key == "draw":
        return f"Draw moneyline in {game}"
    team = home if outcome_key == "home" else away
    if market == "spread":
        return f"{team} {signed_line(line or 0)} spread"
    return f"{team} moneyline"


def side_label(market: str, outcome_key: str, home: str, away: str) -> str:
    if market == "total":
        return "the total"
    return home if outcome_key == "home" else away


def game_href(event_id: str, market: str | None = None) -> str:
    return f"/app/games/{event_id}" + (f"?market={market}" if market else "")


TRACKER_HREF = "/app/tracker"


# ------------------------------------------------------------------- renderers
def price_alert(
    *,
    rule_id: str,
    dedupe_key: str,
    event_id: str,
    market: str,
    outcome_key: str,
    line: Decimal | float | None,
    home: str,
    away: str,
    price_decimal: Decimal,
    threshold_decimal: Decimal,
    sportsbook_key: str,
    sportsbook_name: str,
) -> NotificationDraft:
    values = {
        "price": american(price_decimal),
        "threshold": american(threshold_decimal),
        "sportsbook": sportsbook_name,
        "selection": selection_label(market, outcome_key, line, home, away),
    }
    template = TEMPLATES["price_alert"]
    return NotificationDraft(
        kind="price_alert",
        title=template["title"].format(**values),
        body=template["body"].format(**values),
        href=game_href(event_id, market),
        dedupe_key=dedupe_key,
        rule_id=rule_id,
        data={
            "alert_id": rule_id,
            "event_id": event_id,
            "market": market,
            "outcome_key": outcome_key,
            "line": float(line) if line is not None else None,
            "price_american": describe_price(price_decimal).american,
            "threshold_american": describe_price(threshold_decimal).american,
            "sportsbook_key": sportsbook_key,
        },
    )


def line_move(
    *,
    rule_id: str,
    dedupe_key: str,
    event_id: str,
    market: str,
    outcome_key: str,
    home: str,
    away: str,
    baseline: Decimal,
    current: Decimal,
) -> NotificationDraft:
    values = {
        "matchup": matchup(home, away),
        "market": market,
        "side": side_label(market, outcome_key, home, away),
        "current": line_text(market, current),
        "baseline": line_text(market, baseline),
    }
    template = TEMPLATES["line_move"]
    return NotificationDraft(
        kind="line_move",
        title=template["title"].format(**values),
        body=template["body"].format(**values),
        href=game_href(event_id, market),
        dedupe_key=dedupe_key,
        rule_id=rule_id,
        data={
            "alert_id": rule_id,
            "event_id": event_id,
            "market": market,
            "outcome_key": outcome_key,
            "line": float(current),
            "baseline_line": float(baseline),
        },
    )


def game_start(
    *,
    rule_id: str,
    dedupe_key: str,
    event_id: str,
    home: str,
    away: str,
    start_time: datetime,
    minutes_before: int,
) -> NotificationDraft:
    values = {
        "matchup": matchup(home, away),
        "start": clock(start_time),
        "day": f"{start_time:%b} {start_time.day}",
        "minutes": minutes_before,
    }
    template = TEMPLATES["game_start"]
    return NotificationDraft(
        kind="game_start",
        title=template["title"].format(**values),
        body=template["body"].format(**values),
        href=game_href(event_id),
        dedupe_key=dedupe_key,
        rule_id=rule_id,
        data={
            "alert_id": rule_id,
            "event_id": event_id,
            "start_time": start_time.isoformat(),
            "minutes_before": minutes_before,
        },
    )


def game_final(
    *,
    rule_id: str,
    dedupe_key: str,
    event_id: str,
    home: str,
    away: str,
    home_abbr: str,
    away_abbr: str,
    home_score: int,
    away_score: int,
) -> NotificationDraft:
    values = {
        "home": home,
        "away": away,
        "home_abbr": home_abbr,
        "away_abbr": away_abbr,
        "home_score": home_score,
        "away_score": away_score,
    }
    template = TEMPLATES["game_final"]
    return NotificationDraft(
        kind="game_final",
        title=template["title"].format(**values),
        body=template["body"].format(**values),
        href=game_href(event_id),
        dedupe_key=dedupe_key,
        rule_id=rule_id,
        data={
            "alert_id": rule_id,
            "event_id": event_id,
            "home_score": home_score,
            "away_score": away_score,
        },
    )


def bet_settled(
    *, bet_id: str, result: str, stake: Decimal, profit: Decimal, sportsbook: str
) -> NotificationDraft:
    values = {
        "result": _RESULT_WORDS.get(result, result.replace("_", " ")),
        "stake": money(stake),
        "sportsbook": sportsbook,
        "profit": signed_money(profit),
    }
    template = TEMPLATES["bet_settled"]
    return NotificationDraft(
        kind="bet_settled",
        title=template["title"].format(**values),
        body=template["body"].format(**values),
        href=TRACKER_HREF,
        dedupe_key=f"bet_settled:{bet_id}",
        data={"bet_id": bet_id, "result": result, "profit": float(profit)},
    )


def sync_finished(
    *,
    run_id: str,
    connection_id: str,
    label: str,
    succeeded: bool,
    imported: int,
    duplicates: int,
    attempts: int,
) -> NotificationDraft:
    values = {"label": label, "imported": imported, "duplicates": duplicates, "attempts": attempts}
    template = TEMPLATES["sync_finished"]
    suffix = "" if succeeded else "_failed"
    return NotificationDraft(
        kind="sync_finished",
        title=template[f"title{suffix}"].format(**values),
        body=template[f"body{suffix}"].format(**values),
        href=TRACKER_HREF,
        dedupe_key=f"sync_finished:{run_id}",
        data={
            "run_id": run_id,
            "connection_id": connection_id,
            "status": "succeeded" if succeeded else "failed",
            "imported": imported,
            "duplicates": duplicates,
        },
    )


def stake_reminder(
    *, week_start: datetime, staked: Decimal, threshold: Decimal
) -> NotificationDraft:
    values = {"staked": money(staked), "threshold": money(threshold)}
    template = TEMPLATES["stake_reminder"]
    return NotificationDraft(
        kind="stake_reminder",
        title=template["title"].format(**values),
        body=template["body"].format(**values),
        href=TRACKER_HREF,
        dedupe_key=f"stake_reminder:{week_start:%Y-%m-%d}",
        data={
            "week_start": week_start.isoformat(),
            "staked_this_week": float(staked),
            "weekly_stake_threshold": float(threshold),
        },
    )


# ------------------------------------------------------------------ community
def pick_href(pick_id: str) -> str:
    return f"/app/community/picks/{pick_id}"


def profile_href(handle: str) -> str:
    return f"/app/community/profiles/{handle}"


def new_follower(*, follower_id: str, handle: str) -> NotificationDraft:
    template = TEMPLATES["new_follower"]
    return NotificationDraft(
        kind="new_follower",
        title=template["title"],
        body=template["body"].format(handle=handle),
        href=profile_href(handle),
        # One per follower, ever: following again after unfollowing does not notify twice.
        dedupe_key=f"new_follower:{follower_id}",
        data={"handle": handle},
    )


def pick_comment(
    *, comment_id: str, pick_id: str, handle: str, selection: str
) -> NotificationDraft:
    template = TEMPLATES["pick_comment"]
    return NotificationDraft(
        kind="pick_comment",
        title=template["title"],
        body=template["body"].format(handle=handle, selection=selection),
        href=pick_href(pick_id),
        dedupe_key=f"pick_comment:{comment_id}",
        data={"pick_id": pick_id, "comment_id": comment_id, "handle": handle},
    )


def pick_graded(
    *,
    pick_id: str,
    selection: str,
    event_label: str,
    result: str,
    home_score: int,
    away_score: int,
) -> NotificationDraft:
    values = {
        "selection": selection,
        "event_label": event_label,
        "result": _RESULT_WORDS.get(result, result),
        "home_score": home_score,
        "away_score": away_score,
    }
    template = TEMPLATES["pick_graded"]
    return NotificationDraft(
        kind="pick_graded",
        title=template["title"].format(**values),
        body=template["body"].format(**values),
        href=pick_href(pick_id),
        dedupe_key=f"pick_graded:{pick_id}",
        data={
            "pick_id": pick_id,
            "result": result,
            "home_score": home_score,
            "away_score": away_score,
        },
    )
