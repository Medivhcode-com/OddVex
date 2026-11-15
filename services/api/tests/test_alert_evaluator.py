"""The pure alert evaluator: known values, edges and properties. No database, no provider."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from oddvex_api.alerts.evaluator import (
    GameSnapshot,
    PriceSnapshot,
    RuleInputs,
    RuleSnapshot,
    dedupe_key,
    evaluate,
    line_moved,
    price_meets,
    starts_within,
)
from oddvex_api.quant import american_to_decimal
from oddvex_api.schemas import odds_to_decimal

NOW = datetime(2026, 3, 14, 19, 30, tzinfo=UTC)
D = Decimal


def game(event_id: str = "evt_1", status: str = "upcoming", **overrides: object) -> GameSnapshot:
    values: dict[str, object] = {
        "id": event_id,
        "status": status,
        "start_time": NOW + timedelta(hours=3),
        "home": "Harbor City Tides",
        "away": "Ironvale Anvils",
        "home_abbr": "HCT",
        "away_abbr": "IRV",
    }
    if status == "final":
        values.update(start_time=NOW - timedelta(hours=4), home_score=101, away_score=99)
    values.update(overrides)
    return GameSnapshot(**values)  # type: ignore[arg-type]


def price(american: int, book: str = "northline") -> PriceSnapshot:
    return PriceSnapshot(
        price=american_to_decimal(american), sportsbook_key=book, sportsbook_name=book.title()
    )


def price_rule(threshold: int, **overrides: object) -> RuleSnapshot:
    values: dict[str, object] = {
        "id": "r1",
        "kind": "price_at_least",
        "event_id": "evt_1",
        "market": "moneyline",
        "outcome_key": "home",
        # Stored the way the API stores it: decimal odds rounded to 6 places.
        "threshold_decimal": odds_to_decimal(threshold, "american").quantize(D("0.000001")),
    }
    values.update(overrides)
    return RuleSnapshot(**values)  # type: ignore[arg-type]


# ------------------------------------------------------------- price_at_least
@pytest.mark.parametrize(
    ("best", "threshold", "fires"),
    [
        (150, 145, True),
        (145, 145, True),  # exactly met
        (144, 145, False),
        (-110, -110, True),  # exactly met where the decimal value does not terminate
        (-111, -110, False),
        (-105, -110, True),
        (100, -105, True),
        (-102, 100, False),
    ],
)
def test_price_alert_fires_at_or_above_the_threshold(
    best: int, threshold: int, fires: bool
) -> None:
    outcome = evaluate(
        price_rule(threshold), RuleInputs(games=(game(),), best_price=price(best)), NOW
    )
    assert outcome.action == ("fire" if fires else "none")
    assert len(outcome.drafts) == (1 if fires else 0)


def test_price_alert_notification_states_price_book_and_threshold() -> None:
    outcome = evaluate(price_rule(145), RuleInputs(games=(game(),), best_price=price(150)), NOW)
    (draft,) = outcome.drafts
    assert draft.kind == "price_alert" and draft.rule_id == "r1"
    assert draft.title == "Price reached +150"
    assert draft.body == (
        "Harbor City Tides moneyline is +150 at Northline, at or above your +145 alert."
    )
    assert draft.href == "/app/games/evt_1?market=moneyline"
    assert draft.data == {
        "alert_id": "r1",
        "event_id": "evt_1",
        "market": "moneyline",
        "outcome_key": "home",
        "line": None,
        "price_american": 150,
        "threshold_american": 145,
        "sportsbook_key": "northline",
    }
    assert draft.dedupe_key == "alert:r1:0:evt_1"


def test_price_alert_without_a_usable_price_does_nothing() -> None:
    # No open, non-stale book quotes the outcome (or not at the rule's line).
    assert evaluate(price_rule(145), RuleInputs(games=(game(),)), NOW).action == "none"


def test_price_alert_still_fires_while_the_game_is_live() -> None:
    inputs = RuleInputs(games=(game(status="live"),), best_price=price(150))
    assert evaluate(price_rule(145), inputs, NOW).action == "fire"


@pytest.mark.parametrize("games", [(), (game(status="final"),)])
def test_price_and_line_rules_expire_when_the_event_is_final_or_gone(
    games: tuple[GameSnapshot, ...],
) -> None:
    inputs = RuleInputs(games=games, best_price=price(500), consensus_line=D("-9.5"))
    assert evaluate(price_rule(145), inputs, NOW).action == "expire"
    line_rule = RuleSnapshot(
        id="r2",
        kind="line_move",
        event_id="evt_1",
        market="spread",
        outcome_key="home",
        min_move=D("1"),
        baseline_line=D("-3.5"),
    )
    outcome = evaluate(line_rule, inputs, NOW)
    assert outcome.action == "expire" and outcome.drafts == ()


def test_spread_price_alert_names_the_line() -> None:
    rule = price_rule(-105, market="spread", outcome_key="away", line=D("3.50"))
    outcome = evaluate(rule, RuleInputs(games=(game(),), best_price=price(-102)), NOW)
    (draft,) = outcome.drafts
    assert draft.body == (
        "Ironvale Anvils +3.5 spread is -102 at Northline, at or above your -105 alert."
    )
    assert draft.href == "/app/games/evt_1?market=spread" and draft.data["line"] == 3.5


def test_total_price_alert_wording() -> None:
    rule = price_rule(100, market="total", outcome_key="over", line=D("224.50"))
    outcome = evaluate(rule, RuleInputs(games=(game(),), best_price=price(104)), NOW)
    assert outcome.drafts[0].body == (
        "Over 224.5 in Ironvale Anvils at Harbor City Tides is +104 at Northline, "
        "at or above your +100 alert."
    )


# ------------------------------------------------------------------ line_move
def line_rule(baseline: str, min_move: str, market: str = "spread") -> RuleSnapshot:
    return RuleSnapshot(
        id="r2",
        kind="line_move",
        event_id="evt_1",
        market=market,
        outcome_key="home" if market == "spread" else "over",
        min_move=D(min_move),
        baseline_line=D(baseline),
    )


@pytest.mark.parametrize(
    ("baseline", "current", "min_move", "fires"),
    [
        ("-3.5", "-4.5", "1", True),  # exactly min_move, away from zero
        ("-3.5", "-2.5", "1", True),  # exactly min_move, the other direction
        ("-3.5", "-4.0", "1", False),
        ("-3.5", "-3.5", "0.5", False),
        ("-3.5", "-6.5", "1", True),
        ("-1.5", "1.5", "3", True),  # crosses zero
        ("224.5", "225.0", "0.5", True),
        ("224.5", "224.5", "0.5", False),
    ],
)
def test_line_move_fires_at_min_move_in_either_direction(
    baseline: str, current: str, min_move: str, fires: bool
) -> None:
    outcome = evaluate(
        line_rule(baseline, min_move), RuleInputs(games=(game(),), consensus_line=D(current)), NOW
    )
    assert outcome.action == ("fire" if fires else "none")


def test_line_move_notification_states_both_lines() -> None:
    outcome = evaluate(
        line_rule("-3.5", "1"), RuleInputs(games=(game(),), consensus_line=D("-4.5")), NOW
    )
    (draft,) = outcome.drafts
    assert draft.kind == "line_move" and draft.title == "Line moved to -4.5"
    assert draft.body == (
        "Ironvale Anvils at Harbor City Tides spread: the consensus line for Harbor City "
        "Tides is -4.5. It was -3.5 when you set this alert."
    )
    assert draft.data["line"] == -4.5 and draft.data["baseline_line"] == -3.5
    total_outcome = evaluate(
        line_rule("224.5", "2", market="total"),
        RuleInputs(games=(game(),), consensus_line=D("227.5")),
        NOW,
    )
    assert total_outcome.drafts[0].title == "Line moved to 227.5"
    assert "consensus line for the total is 227.5. It was 224.5" in total_outcome.drafts[0].body


def test_line_move_without_a_consensus_line_does_nothing() -> None:
    assert evaluate(line_rule("-3.5", "1"), RuleInputs(games=(game(),)), NOW).action == "none"


# ----------------------------------------------------------------- game_start
def start_rule(minutes: int, team: bool = False, handled: tuple[str, ...] = ()) -> RuleSnapshot:
    return RuleSnapshot(
        id="r3",
        kind="game_start",
        event_id=None if team else "evt_1",
        team_id="team_1" if team else None,
        minutes_before=minutes,
        handled_event_ids=frozenset(handled),
    )


@pytest.mark.parametrize(
    ("seconds_to_start", "action"),
    [
        (30 * 60 + 1, "none"),  # one second outside the window
        (30 * 60, "fire"),  # exactly minutes_before
        (30 * 60 - 1, "fire"),
        (1, "fire"),
        (0, "expire"),  # starting right now: no longer upcoming
        (-60, "expire"),
    ],
)
def test_game_start_window_edges(seconds_to_start: int, action: str) -> None:
    start = NOW + timedelta(seconds=seconds_to_start)
    inputs = RuleInputs(games=(game(start_time=start),))
    assert evaluate(start_rule(30), inputs, NOW).action == action


def test_game_start_expires_once_the_game_is_live_final_or_gone() -> None:
    for games in ((), (game(status="live"),), (game(status="final"),)):
        assert evaluate(start_rule(30), RuleInputs(games=games), NOW).action == "expire"


def test_game_start_notification_wording() -> None:
    start = datetime(2026, 3, 14, 19, 45, tzinfo=UTC)
    outcome = evaluate(start_rule(30), RuleInputs(games=(game(start_time=start),)), NOW)
    (draft,) = outcome.drafts
    assert draft.kind == "game_start" and draft.title == "Game starts at 19:45 UTC"
    assert draft.body == (
        "Ironvale Anvils at Harbor City Tides starts at 19:45 UTC on Mar 14. "
        "Your alert is set for 30 minutes before the start."
    )
    assert draft.href == "/app/games/evt_1"
    assert draft.data["start_time"] == start.isoformat()


def test_team_game_start_fires_once_per_game_and_stays_for_the_next_one() -> None:
    soon = game("evt_a", start_time=NOW + timedelta(minutes=20))
    later = game("evt_b", start_time=NOW + timedelta(hours=24, minutes=20))
    live = game("evt_c", status="live", start_time=NOW - timedelta(hours=1))
    inputs = RuleInputs(games=(later, soon, live))

    first = evaluate(start_rule(60, team=True), inputs, NOW)
    assert first.action == "fire" and first.handled_event_ids == ("evt_a",)
    assert [d.data["event_id"] for d in first.drafts] == ["evt_a"]

    # Same state again, now that evt_a is handled: nothing.
    again = evaluate(start_rule(60, team=True, handled=("evt_a",)), inputs, NOW)
    assert again.action == "none" and again.drafts == ()

    # A day later the next game comes into the window and fires on its own.
    tomorrow = NOW + timedelta(hours=24)
    next_day = evaluate(start_rule(60, team=True, handled=("evt_a",)), inputs, tomorrow)
    assert next_day.action == "fire" and next_day.handled_event_ids == ("evt_b",)
    assert next_day.drafts[0].dedupe_key != first.drafts[0].dedupe_key


# ----------------------------------------------------------------- game_final
def final_rule(team: bool = False, handled: tuple[str, ...] = ()) -> RuleSnapshot:
    return RuleSnapshot(
        id="r4",
        kind="game_final",
        event_id=None if team else "evt_1",
        team_id="team_1" if team else None,
        handled_event_ids=frozenset(handled),
    )


def test_game_final_fires_with_the_final_score() -> None:
    outcome = evaluate(final_rule(), RuleInputs(games=(game(status="final"),)), NOW)
    (draft,) = outcome.drafts
    assert outcome.action == "fire" and draft.kind == "game_final"
    assert draft.title == "Final: IRV 99, HCT 101"
    assert draft.body == "Final score: Ironvale Anvils 99, Harbor City Tides 101."
    assert draft.data == {
        "alert_id": "r4",
        "event_id": "evt_1",
        "home_score": 101,
        "away_score": 99,
    }


def test_game_final_waits_while_the_game_is_not_over_and_expires_if_it_disappears() -> None:
    assert evaluate(final_rule(), RuleInputs(games=(game(),)), NOW).action == "none"
    assert evaluate(final_rule(), RuleInputs(games=(game(status="live"),)), NOW).action == "none"
    # A final event never expires a game_final rule (it fires); a missing one does.
    assert evaluate(final_rule(), RuleInputs(games=()), NOW).action == "expire"


def test_team_game_final_fires_once_per_game() -> None:
    old = game("evt_old", status="final", start_time=NOW - timedelta(days=1))
    new = game("evt_new", status="final", home_score=3, away_score=3)
    upcoming = game("evt_next")
    inputs = RuleInputs(games=(upcoming, new, old))
    first = evaluate(final_rule(team=True, handled=("evt_old",)), inputs, NOW)
    assert first.action == "fire" and first.handled_event_ids == ("evt_new",)
    assert first.drafts[0].title == "Final: IRV 3, HCT 3"
    again = evaluate(final_rule(team=True, handled=("evt_old", "evt_new")), inputs, NOW)
    assert again.action == "none"
    # Two unhandled finals are reported oldest first.
    both = evaluate(final_rule(team=True), inputs, NOW)
    assert both.handled_event_ids == ("evt_old", "evt_new") and len(both.drafts) == 2


def test_team_rules_expire_only_when_the_team_is_gone() -> None:
    assert evaluate(final_rule(team=True), RuleInputs(), NOW).action == "none"
    assert evaluate(start_rule(30, team=True), RuleInputs(), NOW).action == "none"
    gone = RuleInputs(team_missing=True)
    assert evaluate(final_rule(team=True), gone, NOW).action == "expire"
    assert evaluate(start_rule(30, team=True), gone, NOW).action == "expire"


def test_dedupe_key_depends_on_rule_arming_and_event() -> None:
    rule = RuleSnapshot(id="r", kind="game_final", event_id="e")
    rearmed = RuleSnapshot(id="r", kind="game_final", event_id="e", arm_count=1)
    assert dedupe_key(rule, "e") == "alert:r:0:e"
    assert len({dedupe_key(rule, "e"), dedupe_key(rearmed, "e"), dedupe_key(rule, "f")}) == 3


def test_unknown_kind_does_nothing() -> None:
    assert evaluate(RuleSnapshot(id="r", kind="mystery"), RuleInputs(), NOW).action == "none"


# ----------------------------------------------------------------- properties
american_prices = st.integers(min_value=100, max_value=5000).flatmap(
    lambda magnitude: st.sampled_from([magnitude, -magnitude])
)
half_points = st.integers(min_value=-120, max_value=600).map(lambda n: D(n) / 2)


@given(best=american_prices, threshold=american_prices)
def test_price_alert_fires_exactly_when_the_price_pays_at_least_the_threshold(
    best: int, threshold: int
) -> None:
    # American odds are ordered like their payout: -110 pays less than +100, which pays
    # less than +150. -100 and +100 are the same price.
    def payout(american: int) -> float:
        return american / 100 if american > 0 else 100 / -american

    outcome = evaluate(
        price_rule(threshold), RuleInputs(games=(game(),), best_price=price(best)), NOW
    )
    assert (outcome.action == "fire") == (payout(best) >= payout(threshold))
    assert price_meets(american_to_decimal(best), american_to_decimal(best))


@given(baseline=half_points, current=half_points, steps=st.integers(min_value=1, max_value=40))
def test_line_move_is_symmetric_and_fires_exactly_at_the_distance(
    baseline: D, current: D, steps: int
) -> None:
    min_move = D(steps) / 2
    expected = abs(current - baseline) >= min_move
    assert line_moved(baseline, current, min_move) == expected
    assert line_moved(current, baseline, min_move) == expected
    assert line_moved(baseline, baseline + min_move, min_move)
    assert line_moved(baseline, baseline - min_move, min_move)
    assert not line_moved(baseline, baseline, min_move)


@given(
    seconds=st.integers(min_value=-86_400, max_value=3 * 86_400),
    minutes=st.integers(min_value=5, max_value=1440),
)
def test_game_start_window_is_the_minutes_before_the_start(seconds: int, minutes: int) -> None:
    start = NOW + timedelta(seconds=seconds)
    assert starts_within(start, NOW, minutes) == (0 < seconds <= minutes * 60)
    outcome = evaluate(start_rule(minutes), RuleInputs(games=(game(start_time=start),)), NOW)
    expected = "expire" if seconds <= 0 else "fire" if seconds <= minutes * 60 else "none"
    assert outcome.action == expected


@given(
    handled=st.sets(st.sampled_from(["a", "b", "c", "d"])),
    finals=st.sets(st.sampled_from(["a", "b", "c", "d"])),
)
def test_team_final_rule_never_fires_twice_for_a_game(handled: set[str], finals: set[str]) -> None:
    games = tuple(
        game(event_id, status="final" if event_id in finals else "upcoming")
        for event_id in ("a", "b", "c", "d")
    )
    rule = final_rule(team=True, handled=tuple(handled))
    first = evaluate(rule, RuleInputs(games=games), NOW)
    assert set(first.handled_event_ids) == finals - handled
    assert len(first.drafts) == len(first.handled_event_ids)
    assert len({d.dedupe_key for d in first.drafts}) == len(first.drafts)
    after = final_rule(team=True, handled=(*handled, *first.handled_event_ids))
    assert evaluate(after, RuleInputs(games=games), NOW).action == "none"
