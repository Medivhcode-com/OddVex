"""Compliance rules for notification wording (BRAND_VOICE.md, PROJECT_CONSTITUTION.md §2).

Notifications are neutral and factual: no instruction to bet, no urgency, no hype, no
probabilities. Every string a user can receive is built from
``notifications.templates.TEMPLATES``, so scanning the templates and a rendered sample of
each one covers all of them.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from string import Formatter

import pytest

from oddvex_api.notifications import templates
from oddvex_api.notifications.schemas import NOTIFICATION_KINDS
from oddvex_api.notifications.templates import TEMPLATES, NotificationDraft
from oddvex_api.quant import american_to_decimal

#: Phrases that must never appear in a notification, in any letter case.
BANNED_PHRASES = (
    "bet now",
    "hurry",
    "don't miss",
    "dont miss",
    "lock",
    "guaranteed",
    "guarantee",
    "risk-free",
    "risk free",
    "act fast",
    "last chance",
    "sure thing",
    # More from BRAND_VOICE.md "banned claims".
    "can't lose",
    "free money",
    "win it back",
    "best bet",
    "top pick",
    "no-brainer",
    "before the line moves",
    "place a bet",
    "place your bet",
    "bet on",
    "smash",
)
#: Words that would make a notification a prediction or a nudge.
BANNED_WORDS = ("probability", "chance", "likely", "odds-on", "should", "must", "now", "quick")

WHEN = datetime(2026, 3, 14, 19, 45, tzinfo=UTC)


def rendered() -> list[NotificationDraft]:
    """At least one draft from every renderer and every template variant."""
    game = {"home": "Harbor City Tides", "away": "Ironvale Anvils"}
    common = {"rule_id": "r1", "dedupe_key": "k", "event_id": "evt_1"}
    drafts = [
        templates.price_alert(
            **common,
            **game,
            market=market,
            outcome_key=outcome,
            line=line,
            price_decimal=american_to_decimal(price),
            threshold_decimal=american_to_decimal(threshold),
            sportsbook_key="northline",
            sportsbook_name="Northline",
        )
        for market, outcome, line, price, threshold in (
            ("moneyline", "home", None, 150, 145),
            ("moneyline", "away", None, -110, -115),
            ("moneyline", "draw", None, 240, 230),
            ("spread", "home", Decimal("-3.5"), -105, -110),
            ("spread", "away", Decimal("3.5"), 100, -105),
            ("total", "over", Decimal("224.5"), -108, -110),
            ("total", "under", Decimal("224.5"), 102, 100),
        )
    ]
    drafts += [
        templates.line_move(
            **common,
            **game,
            market=market,
            outcome_key=outcome,
            baseline=Decimal(baseline),
            current=Decimal(current),
        )
        for market, outcome, baseline, current in (
            ("spread", "home", "-3.5", "-4.5"),
            ("spread", "away", "3.5", "2.5"),
            ("total", "over", "224.5", "226.5"),
        )
    ]
    drafts.append(templates.game_start(**common, **game, start_time=WHEN, minutes_before=30))
    drafts.append(
        templates.game_final(
            **common, **game, home_abbr="HCT", away_abbr="IRV", home_score=101, away_score=99
        )
    )
    drafts += [
        templates.bet_settled(
            bet_id="b1",
            result=result,
            stake=Decimal("20"),
            profit=Decimal(profit),
            sportsbook="Northline",
        )
        for result, profit in (
            ("won", "16.95"),
            ("lost", "-20"),
            ("push", "0"),
            ("void", "0"),
            ("half_won", "8.47"),
            ("half_lost", "-10"),
            ("cashout", "-4"),
        )
    ]
    drafts += [
        templates.sync_finished(
            run_id="run1",
            connection_id="c1",
            label="Mock account",
            succeeded=succeeded,
            imported=10,
            duplicates=2,
            attempts=3,
        )
        for succeeded in (True, False)
    ]
    drafts.append(
        templates.stake_reminder(
            week_start=datetime(2026, 3, 9, tzinfo=UTC),
            staked=Decimal("520"),
            threshold=Decimal("500"),
        )
    )
    return drafts


def all_template_strings() -> list[tuple[str, str]]:
    return [
        (f"{kind}.{name}", text)
        for kind, group in TEMPLATES.items()
        for name, text in group.items()
    ]


def all_texts() -> list[tuple[str, str]]:
    texts = all_template_strings()
    for draft in rendered():
        texts.append((f"{draft.kind} title", draft.title))
        texts.append((f"{draft.kind} body", draft.body))
    return texts


def test_every_notification_kind_has_a_title_and_a_body_template() -> None:
    assert set(TEMPLATES) == set(NOTIFICATION_KINDS)
    for kind, group in TEMPLATES.items():
        assert {"title", "body"} <= set(group), kind
    assert {draft.kind for draft in rendered()} == set(NOTIFICATION_KINDS)


@pytest.mark.parametrize(("where", "text"), all_texts())
def test_no_banned_phrase_in_any_template_or_rendered_notification(where: str, text: str) -> None:
    lowered = text.lower()
    for phrase in BANNED_PHRASES:
        assert phrase not in lowered, f"{where}: banned phrase {phrase!r} in {text!r}"
    words = set(re.findall(r"[a-z][a-z'-]*", lowered))
    for word in BANNED_WORDS:
        assert word not in words, f"{where}: banned word {word!r} in {text!r}"
    assert "!" not in text, f"{where}: no exclamation marks"
    assert "%" not in text, f"{where}: notifications carry no probabilities or percentages"
    assert text == text.strip() and "  " not in text


def test_the_banned_phrase_scan_would_catch_bad_copy() -> None:
    # Guards the test above against silently matching nothing.
    for bad in ("Bet now!", "Don't miss out", "Lock it in", "Hurry", "A sure thing"):
        assert any(phrase in bad.lower() for phrase in BANNED_PHRASES), bad


def test_everything_a_renderer_returns_comes_from_a_template() -> None:
    """So a renderer cannot add wording that the scan of ``TEMPLATES`` does not see."""

    def pattern(template: str) -> re.Pattern[str]:
        parts = [
            re.escape(literal) + ("(.+)" if field is not None else "")
            for literal, field, _, _ in Formatter().parse(template)
        ]
        return re.compile("".join(parts), re.DOTALL)

    for draft in rendered():
        group = TEMPLATES[draft.kind]
        titles = [pattern(text) for name, text in group.items() if name.startswith("title")]
        bodies = [pattern(text) for name, text in group.items() if name.startswith("body")]
        assert any(p.fullmatch(draft.title) for p in titles), draft.title
        assert any(p.fullmatch(draft.body) for p in bodies), draft.body


def test_titles_are_sentence_case_and_short() -> None:
    for name, text in all_template_strings():
        if not name.split(".")[1].startswith("title"):
            continue
        literal = "".join(part for part, *_ in Formatter().parse(text))
        words = re.findall(r"[A-Za-z]+", literal)
        assert words[0][0].isupper(), name
        assert all(word.islower() for word in words[1:]), f"{name}: {text!r} is not sentence case"
    for draft in rendered():
        assert len(draft.title) <= 60 and not draft.title.endswith(".")
        assert draft.body.endswith(".")


def test_prices_are_american_with_an_explicit_sign() -> None:
    for draft in rendered():
        if draft.kind != "price_alert":
            continue
        assert re.fullmatch(r"Price reached [+-]\d{3,}", draft.title), draft.title
        prices = re.findall(r"(?<![\w.])[+-]\d{3,}(?![\d.])", draft.body)
        assert len(prices) == 2, draft.body  # the price and the user's threshold
        assert f"{draft.data['price_american']:+d}" == prices[0]
        assert f"{draft.data['threshold_american']:+d}" == prices[1]
        # Never decimal odds, never an implied probability.
        assert not re.search(r"\d\.\d{2,}", draft.body)
    assert templates.american(american_to_decimal(150)) == "+150"
    assert templates.american(american_to_decimal(-110)) == "-110"
    assert templates.american(Decimal("2.0")) == "+100"


def test_the_staking_reminder_is_supportive_and_points_to_help() -> None:
    draft = next(d for d in rendered() if d.kind == "stake_reminder")
    assert draft.title == "Weekly staking reminder"
    assert draft.body == (
        "You have staked $520.00 this week, at or above the $500.00 reminder you set. "
        "This is a reminder, not a limit. Free, confidential help is available at "
        "1-800-GAMBLER."
    )
    lowered = draft.body.lower()
    for shaming in (
        "too much",
        "problem",
        "addict",
        "irresponsible",
        "stop",
        "warning",
        "exceeded",
    ):
        assert shaming not in lowered
    assert draft.href == "/app/tracker"


def test_wins_and_losses_get_the_same_plain_wording() -> None:
    by_result = {d.data["result"]: d for d in rendered() if d.kind == "bet_settled"}
    assert by_result["won"].title == "Bet settled: won"
    assert by_result["won"].body == (
        "Your $20.00 bet at Northline settled as won. Profit: +$16.95."
    )
    assert by_result["lost"].title == "Bet settled: lost"
    assert by_result["lost"].body == (
        "Your $20.00 bet at Northline settled as lost. Profit: -$20.00."
    )
    assert by_result["half_won"].title == "Bet settled: half won"


def test_links_point_at_app_routes() -> None:
    for draft in rendered():
        assert re.fullmatch(
            r"/app/(games/[\w-]+(\?market=(moneyline|spread|total))?|tracker)", draft.href
        )
