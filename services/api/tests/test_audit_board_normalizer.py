"""The vendor seam rejects malformed input instead of passing it on (audit quant-data#5).

Before the fix a priced quote without a timestamp, or with one from the future, came
through and was then treated as fresh for ever. Non-finite lines, same-sign spreads,
duplicate sides, sides of another market, negative and fractional scores and non-finite
statistics came through as well.
"""

from __future__ import annotations

import copy
import logging
import signal
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any, get_args

import pytest

from oddvex_api.api.schemas import LeagueKey
from oddvex_api.providers import normalize
from oddvex_api.providers.base import MAX_CLOCK_SKEW_SECONDS
from oddvex_api.providers.normalize import (
    ProviderContractError,
    normalize_event,
    normalize_game_log,
    normalize_odds_snapshot,
    parse_timestamp,
    rejection_counts,
    reset_rejection_counts,
)

FETCHED = datetime(2026, 1, 10, 18, 6, tzinfo=UTC)
UPDATED = "2026-01-10T18:05:30Z"
PAYLOAD_MARKER = "payload-marker-7f3a"


@pytest.fixture(autouse=True)
def _fresh_counts() -> Iterator[None]:
    reset_rejection_counts()
    yield
    reset_rejection_counts()


def moneyline(**changes: Any) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "eventId": "e",
        "marketType": "h2h",
        "book": "northline",
        "state": "OPEN",
        "updatedAt": UPDATED,
        "selections": [
            {"side": "HOME", "label": "A", "priceAmerican": "-150"},
            {"side": "AWAY", "label": "B", "priceAmerican": "+130"},
        ],
    }
    raw.update(changes)
    return raw


def spread(home: Any = -3.5, away: Any = 3.5, **changes: Any) -> dict[str, Any]:
    return moneyline(
        marketType="spreads",
        selections=[
            {"side": "HOME", "label": "A", "handicap": home, "priceAmerican": "-110"},
            {"side": "AWAY", "label": "B", "handicap": away, "priceAmerican": "-110"},
        ],
        **changes,
    )


def total(over: Any = 224.5, under: Any = 224.5, **changes: Any) -> dict[str, Any]:
    return moneyline(
        marketType="totals",
        selections=[
            {"side": "OVER", "label": "Over", "handicap": over, "priceAmerican": "-108"},
            {"side": "UNDER", "label": "Under", "handicap": under, "priceAmerican": "-112"},
        ],
        **changes,
    )


def without(raw: dict[str, Any], key: str) -> dict[str, Any]:
    trimmed = copy.deepcopy(raw)
    del trimmed[key]
    return trimmed


def sides(*names: str, handicap: Any = None) -> list[dict[str, Any]]:
    rows = []
    for name in names:
        row: dict[str, Any] = {"side": name, "label": name, "priceAmerican": "-110"}
        if handicap is not None:
            row["handicap"] = handicap
        rows.append(row)
    return rows


def rejected(raw: dict[str, Any]) -> str:
    with pytest.raises(ProviderContractError) as caught:
        normalize_odds_snapshot(raw, "fixture", FETCHED)
    return caught.value.reason


@contextmanager
def within(seconds: float) -> Iterator[None]:
    """Fail when the block runs for longer than ``seconds``.

    Where the platform has an interval timer the block is interrupted at the limit, so a
    check that takes minutes or hours on one field fails the test at once instead of
    holding the whole run. Elsewhere the time is compared after the block has finished.
    """
    armed = hasattr(signal, "setitimer") and threading.current_thread() is threading.main_thread()

    def expire(signum: int, frame: Any) -> None:
        raise AssertionError(f"still running after {seconds} seconds")

    started = time.perf_counter()
    if armed:
        previous = signal.signal(signal.SIGALRM, expire)
        signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        if armed:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
    assert time.perf_counter() - started < seconds


# ---------------------------------------------------------------- timestamps
def test_valid_quotes_still_normalise() -> None:
    assert normalize_odds_snapshot(moneyline(), "fixture", FETCHED).last_updated == datetime(
        2026, 1, 10, 18, 5, 30, tzinfo=UTC
    )
    assert [o.line for o in normalize_odds_snapshot(spread(), "fixture", FETCHED).outcomes] == [
        -3.5,
        3.5,
    ]
    pick_em = normalize_odds_snapshot(spread(0, 0), "fixture", FETCHED)
    assert [o.line for o in pick_em.outcomes] == [0.0, 0.0]
    assert [o.line for o in normalize_odds_snapshot(total(), "fixture", FETCHED).outcomes] == [
        224.5,
        224.5,
    ]
    assert rejection_counts() == {}


@pytest.mark.parametrize("state", ["OPEN", "SUSPENDED", "CLOSED"])
def test_a_priced_quote_needs_a_timestamp(state: str) -> None:
    assert rejected(without(moneyline(state=state), "updatedAt")) == "missing_timestamp"
    assert rejected(moneyline(state=state, updatedAt=None)) == "missing_timestamp"
    assert rejected(moneyline(state=state, updatedAt="")) == "missing_timestamp"
    assert rejected(moneyline(state=state, updatedAt="   ")) == "missing_timestamp"


def test_an_unavailable_quote_needs_no_timestamp_but_a_given_one_must_be_valid() -> None:
    off = {"eventId": "e", "marketType": "totals", "book": "summit", "state": "OFF"}
    snapshot = normalize_odds_snapshot(off, "fixture", FETCHED)
    assert snapshot.status == "unavailable" and snapshot.last_updated is None
    assert normalize_odds_snapshot({**off, "updatedAt": UPDATED}, "fixture", FETCHED).last_updated
    assert rejected({**off, "updatedAt": "yesterday"}) == "invalid_timestamp"
    assert rejected({**off, "updatedAt": "2026-01-10T23:00:00Z"}) == "future_timestamp"


def test_a_timestamp_from_the_future_is_rejected_beyond_the_clock_skew_allowance() -> None:
    assert MAX_CLOCK_SKEW_SECONDS == 60

    def at(seconds: float) -> str:
        return (FETCHED + timedelta(seconds=seconds)).isoformat()

    assert rejected(moneyline(updatedAt=at(5 * 3600))) == "future_timestamp"
    assert rejected(moneyline(updatedAt=at(61))) == "future_timestamp"
    # Local time labelled as UTC: five hours ahead.
    assert rejected(moneyline(updatedAt="2026-01-10T23:05:30Z")) == "future_timestamp"
    for skew in (0, 30, 60):
        snapshot = normalize_odds_snapshot(moneyline(updatedAt=at(skew)), "fixture", FETCHED)
        assert snapshot.last_updated == FETCHED + timedelta(seconds=skew)


def test_malformed_timestamps() -> None:
    assert rejected(moneyline(updatedAt="2026-01-10T18:05:30")) == "invalid_timestamp"  # no zone
    assert rejected(moneyline(updatedAt=1768068330)) == "invalid_timestamp"
    assert rejected(moneyline(updatedAt="soon")) == "invalid_timestamp"


# ------------------------------------------------------------ lines and sides
@pytest.mark.parametrize("bad", ["NaN", "nan", "inf", "-Infinity", float("nan"), float("inf")])
def test_non_finite_lines_are_rejected(bad: Any) -> None:
    assert rejected(spread(bad, 3.5)) == "non_finite_number"
    assert rejected(total(bad, 224.5)) == "non_finite_number"


@pytest.mark.parametrize("bad", ["three", "", [], {}, True])
def test_lines_that_are_not_numbers_are_rejected(bad: Any) -> None:
    assert rejected(spread(bad, 3.5)) == "invalid_number"


def test_spread_and_total_selections_need_a_handicap() -> None:
    """On a payload that has its timestamp, so the handicap check itself is what rejects."""
    assert rejected(spread(None, 3.5)) == "missing_field"
    assert rejected(spread(-3.5, None)) == "missing_field"
    assert rejected(total(None, None)) == "missing_field"
    assert rejected(total(224.5, None)) == "missing_field"
    for raw in (spread(), total()):
        for index in (0, 1):
            trimmed = copy.deepcopy(raw)
            del trimmed["selections"][index]["handicap"]
            assert rejected(trimmed) == "missing_field"
    with pytest.raises(ProviderContractError, match="spread selections need a handicap"):
        normalize_odds_snapshot(spread(None, 3.5), "fixture", FETCHED)
    with pytest.raises(ProviderContractError, match="total selections need a handicap"):
        normalize_odds_snapshot(total(None, None), "fixture", FETCHED)
    # A moneyline has no handicap; one that is sent is not read.
    with_handicap = moneyline()
    with_handicap["selections"][0]["handicap"] = -3.5
    snapshot = normalize_odds_snapshot(with_handicap, "fixture", FETCHED)
    assert [o.line for o in snapshot.outcomes] == [None, None]


#: Digits of other scripts are written as escapes: \u0660-\u0669 are Arabic-Indic digits
#: and \uff10-\uff19 are full-width digits. ``int()`` and ``float()`` would read them.
@pytest.mark.parametrize(
    "bad", ["\u0661\u0662.\u0665", "\u0663", "1_0", "0x1F", "1,5", "\uff13.\uff15"]
)
def test_lines_must_be_plain_decimal_numbers(bad: str) -> None:
    assert rejected(spread(bad, 3.5)) == "invalid_number"
    assert rejected(total(bad, bad)) == "invalid_number"


def test_plain_number_forms_are_accepted_as_lines() -> None:
    for home, away in (("-3.5", "3.5"), (" -3.5 ", "+3.5"), (-3, 3), ("-3", "3."), ("-.5", ".5")):
        snapshot = normalize_odds_snapshot(spread(home, away), "fixture", FETCHED)
        assert [o.line for o in snapshot.outcomes] == [float(home), float(away)]
    snapshot = normalize_odds_snapshot(total("2.245e2", 224.5), "fixture", FETCHED)
    assert [o.line for o in snapshot.outcomes] == [224.5, 224.5]


def test_lines_out_of_any_real_range_are_rejected() -> None:
    assert rejected(spread(-1e30, 1e30)) == "out_of_range"
    assert rejected(spread("-1001", "1001")) == "out_of_range"
    assert rejected(total(1e30, 1e30)) == "out_of_range"
    assert rejected(total(1000.5, 1000.5)) == "out_of_range"
    # A total is a number of points: never negative, never zero.
    assert rejected(total(-224.5, -224.5)) == "out_of_range"
    assert rejected(total(0, 0)) == "out_of_range"
    assert normalize_odds_snapshot(total(0.5, 0.5), "fixture", FETCHED).outcomes[0].line == 0.5
    assert normalize_odds_snapshot(spread(-1000, 1000), "fixture", FETCHED).outcomes[0].line == (
        -1000.0
    )


#: Texts that ``float()`` reads as a finite number and that are not in plain decimal form.
#: A pattern that can split a run of digits in more than one way needs a time that grows
#: with the square of the length to refuse them: seconds at 16,000 characters, minutes at
#: 100,000, hours at 1,000,000.
LONG = 100_000
SLOW_NUMBER_TEXTS = {
    "zeros_then_underscore": "0" * LONG + "_0",
    "zeros_then_full_width_digit": "0" * LONG + "\uff10",
    "nines_underscore_exponent": "9" * LONG + "_9e-" + str(LONG),
    "full_width_digit_before_exponent": "5" + "0" * LONG + "\uff10e-" + str(LONG),
    "a_million_zeros_then_underscore": "0" * 1_000_000 + "_0",
    "a_million_zeros_then_full_width_digit": "0" * 1_000_000 + "\uff10",
}


@pytest.mark.parametrize("name", list(SLOW_NUMBER_TEXTS))
def test_a_very_long_number_text_is_refused_at_once(name: str) -> None:
    text = SLOW_NUMBER_TEXTS[name]
    with within(2.0):
        assert rejected(total(text, text)) == "invalid_number"
        assert rejected(spread(text, 3.5)) == "invalid_number"
        assert rejected(spread(-3.5, text)) == "invalid_number"
        with pytest.raises(ProviderContractError) as caught:
            normalize_game_log(game_log(text), "fixture", FETCHED)
        assert caught.value.reason == "invalid_number"


def test_a_number_text_may_be_40_characters_and_no_longer() -> None:
    """A number is never read from a longer text, whatever the text holds: the longest
    plain form of any real line or statistic is far shorter (``-1.7976931348623157e+308``
    has 24 characters)."""
    assert normalize._MAX_NUMBER_LENGTH == 40
    longest = "0" * 37 + "8.5"
    assert len(longest) == 40
    snapshot = normalize_odds_snapshot(total(longest, longest), "fixture", FETCHED)
    assert [o.line for o in snapshot.outcomes] == [8.5, 8.5]
    (entry,) = normalize_game_log(game_log("0" * 38 + "31"), "fixture", FETCHED)
    assert entry.stats == {"points": 31.0}
    # One character more, still a correct number: refused without being read.
    assert rejected(total("0" + longest, "0" + longest)) == "invalid_number"
    assert rejected(spread("-" + "0" * 37 + "3.5", "3.5")) == "invalid_number"
    assert rejected(total(" " * 38 + "8.5", 8.5)) == "invalid_number"
    for long_text in ("0" * 39 + "31", "3" + "1" * 40, "1" * 400, "0." + "0" * 400 + "1"):
        with pytest.raises(ProviderContractError) as caught:
            normalize_game_log(game_log(long_text), "fixture", FETCHED)
        assert caught.value.reason == "invalid_number"


def test_the_number_pattern_reads_a_text_once() -> None:
    """The pattern itself must not be able to split a run of digits in two ways."""
    pattern = normalize._DECIMAL
    for text in SLOW_NUMBER_TEXTS.values():
        with within(2.0):
            assert pattern.fullmatch(text) is None
    for text in ("7" * 1_000_000, "7" * 1_000_000 + ".", "." + "7" * 1_000_000 + "e5"):
        with within(2.0):
            assert pattern.fullmatch(text) is not None
    accepted = ["0", "-0", "+3.5", "3.", ".5", "-.5", "1e3", "1E-3", "007", "224.5", "2.245e2"]
    accepted += ["1.e5", ".5E+10", "0.0", "+0"]
    refused = ["", ".", "+", "-", "1_0", "1e", "1e+", "e5", "1.2.3", "3.5.", "..5", "--1", "1 0"]
    refused += ["1,5", "0x10", "inf", "nan", "Infinity", "1e5.0", "\uff13", "\u0663", "3.5\n"]
    assert [text for text in accepted if not pattern.fullmatch(text)] == []
    assert [text for text in refused if pattern.fullmatch(text)] == []


def test_a_pick_em_line_is_zero_and_never_negative_zero() -> None:
    """-0.0 equals 0.0 and would be shown as "-0.0"."""
    for home, away in ((0, -0.0), (-0.0, 0), ("-0", "0"), ("0", "-0.0"), (-0.0, -0.0), ("-0e0", 0)):
        snapshot = normalize_odds_snapshot(spread(home, away), "fixture", FETCHED)
        assert [str(o.line) for o in snapshot.outcomes] == ["0.0", "0.0"]
    (entry,) = normalize_game_log(game_log(-0.0), "fixture", FETCHED)
    assert str(entry.stats["points"]) == "0.0"


def test_spread_lines_must_mirror_each_other() -> None:
    assert rejected(spread(-3.5, -3.5)) == "lines_do_not_match"
    assert rejected(spread(3.5, 3.5)) == "lines_do_not_match"
    assert rejected(spread(-3.5, 4.5)) == "lines_do_not_match"


def test_total_lines_must_be_equal() -> None:
    assert rejected(total(224.5, 225.5)) == "lines_do_not_match"
    assert rejected(total(224.5, 224)) == "lines_do_not_match"
    assert rejected(total("224.5", "8.5")) == "lines_do_not_match"
    # A negative total is rejected for its own reason before the two lines are compared.
    assert rejected(total(224.5, -224.5)) == "out_of_range"


def test_duplicate_sides_are_rejected() -> None:
    assert rejected(moneyline(selections=sides("HOME", "HOME"))) == "duplicate_side"
    assert rejected(moneyline(selections=sides("HOME", "AWAY", "AWAY"))) == "duplicate_side"
    twice_over = moneyline(marketType="totals", selections=sides("OVER", "OVER", handicap=220.5))
    assert rejected(twice_over) == "duplicate_side"


def test_sides_must_belong_to_the_market() -> None:
    over_in_spread = moneyline(
        marketType="spreads", selections=sides("HOME", "OVER", handicap=-3.5)
    )
    assert rejected(over_in_spread) == "side_not_in_market"
    assert rejected(moneyline(selections=sides("OVER", "UNDER"))) == "side_not_in_market"
    draw_in_spread = moneyline(
        marketType="spreads", selections=sides("HOME", "DRAW", "AWAY", handicap=0)
    )
    assert rejected(draw_in_spread) == "side_not_in_market"
    home_in_total = moneyline(marketType="totals", selections=sides("HOME", "AWAY", handicap=220.5))
    assert rejected(home_in_total) == "side_not_in_market"


def test_a_market_must_have_all_its_sides() -> None:
    assert rejected(moneyline(selections=sides("HOME", "DRAW"))) == "missing_side"
    assert rejected(moneyline(selections=sides("HOME"))) == "missing_side"
    assert rejected(moneyline(selections=[])) == "missing_side"


def test_outcomes_come_back_in_one_order_whatever_the_vendor_sent() -> None:
    """The board reads the first outcome's line as the market line."""
    raw = moneyline(
        marketType="spreads",
        selections=[
            {"side": "AWAY", "label": "B", "handicap": 3.5, "priceAmerican": "-105"},
            {"side": "HOME", "label": "A", "handicap": -3.5, "priceAmerican": "-115"},
        ],
    )
    snapshot = normalize_odds_snapshot(raw, "fixture", FETCHED)
    assert [(o.key, o.line, o.price_american) for o in snapshot.outcomes] == [
        ("home", -3.5, -115),
        ("away", 3.5, -105),
    ]
    three_way = moneyline(selections=sides("AWAY", "DRAW", "HOME"))
    keys = [o.key for o in normalize_odds_snapshot(three_way, "fixture", FETCHED).outcomes]
    assert keys == ["home", "draw", "away"]
    under_first = moneyline(marketType="totals", selections=sides("UNDER", "OVER", handicap=8.5))
    keys = [o.key for o in normalize_odds_snapshot(under_first, "fixture", FETCHED).outcomes]
    assert keys == ["over", "under"]


@pytest.mark.parametrize("bad", ["-50", "0", "abc", "1e3", "150.5", 150.5, True, None, "1+10"])
def test_malformed_prices_are_rejected(bad: Any) -> None:
    raw = moneyline()
    raw["selections"][0]["priceAmerican"] = bad
    assert rejected(raw) in ("invalid_price", "missing_field")


@pytest.mark.parametrize(
    "bad",
    [
        "9" * 30,
        int("9" * 30),
        -(10**30),
        "+1000001",
        -1000001,
        "\u0661\u0665\u0660",
        "-\uff11\uff15\uff10",
        "1_50",
    ],
)
def test_prices_of_absurd_size_or_in_other_digits_are_rejected(bad: Any) -> None:
    raw = moneyline()
    raw["selections"][0]["priceAmerican"] = bad
    assert rejected(raw) == "invalid_price"


def test_long_but_real_prices_are_accepted() -> None:
    raw = moneyline()
    raw["selections"][0]["priceAmerican"] = "-1000000"
    raw["selections"][1]["priceAmerican"] = 1000000
    snapshot = normalize_odds_snapshot(raw, "fixture", FETCHED)
    assert [o.price_american for o in snapshot.outcomes] == [-1000000, 1000000]


def identifier_reasons(bad: Any) -> set[str]:
    """The reasons every identifier and label field is rejected for when it holds ``bad``."""
    reasons = {
        rejected(moneyline(book=bad)),
        rejected(moneyline(eventId=bad)),
        event_rejected(event(eventId=bad)),
        event_rejected(event(leagueKey=bad)),
        event_rejected(event(home={"teamId": bad})),
        event_rejected(event(away={"teamId": bad})),
    }
    labelled = moneyline()
    labelled["selections"][0]["label"] = bad
    reasons.add(rejected(labelled))
    raw = game_log()
    raw["playerId"] = bad
    with pytest.raises(ProviderContractError) as caught:
        normalize_game_log(raw, "fixture", FETCHED)
    reasons.add(caught.value.reason)
    for field in ("eventId", "opp"):
        raw = game_log()
        raw["games"][0][field] = bad
        with pytest.raises(ProviderContractError) as caught:
            normalize_game_log(raw, "fixture", FETCHED)
        reasons.add(caught.value.reason)
    return reasons


@pytest.mark.parametrize("bad", [{"id": 1}, ["northline"], 1.5, True, "", "   ", "x" * 201])
def test_identifiers_must_be_short_text_or_whole_numbers(bad: Any) -> None:
    """Before, an object sent as an identifier was turned into its text and passed on."""
    assert identifier_reasons(bad) <= {"invalid_identifier", "missing_field"}


#: Characters that cannot be shown or stored as they are. A lone surrogate (JSON
#: ``"\ud800"`` loads as one) cannot even be written into a response: before, a payload
#: with one as an identifier was accepted and every answer listing it would have failed.
UNPRINTABLE = {
    "nul": "\x00",
    "newline": "\n",
    "tab": "\t",
    "escape": "\x1b",
    "delete": "\x7f",
    "c1_control": "\x85",
    "lone_surrogate": "\ud800",
    "zero_width_space": "\u200b",
    "right_to_left_override": "\u202e",
    "line_separator": "\u2028",
    "byte_order_mark": "\ufeff",
    "private_use": "\ue000",
    "not_a_character": "\uffff",
}


@pytest.mark.parametrize("name", list(UNPRINTABLE))
def test_identifiers_and_labels_hold_no_control_or_invisible_characters(name: str) -> None:
    assert identifier_reasons(f"north{UNPRINTABLE[name]}line") == {"invalid_identifier"}


def test_names_in_any_script_are_accepted() -> None:
    for label in (
        "Montr\u00e9al",
        "S\u00e3o Paulo",
        "\u6771\u4eac",
        "O'Neil-Smith Jr.",
        "A&B (W) #2",
    ):
        raw = moneyline()
        raw["selections"][0]["label"] = label
        assert normalize_odds_snapshot(raw, "fixture", FETCHED).outcomes[0].name == label
    assert normalize_event(event(eventId="evt:nhl/2026-01-10_1"), "fixture", FETCHED).id == (
        "evt:nhl/2026-01-10_1"
    )


def test_a_whole_number_too_long_to_be_an_identifier_is_rejected_by_name() -> None:
    """Not left to the interpreter's limit on writing out very long whole numbers."""
    for bad in (10**200, -(10**200), 10**5000, 10**100_000):
        with within(2.0):
            assert identifier_reasons(bad) == {"invalid_identifier"}
    snapshot = normalize_odds_snapshot(moneyline(eventId=10**18 + 7), "fixture", FETCHED)
    assert snapshot.event_id == "1000000000000000007"


@pytest.mark.parametrize("bad", [{"id": 1}, ["northline"], 1.5, True])
def test_an_identifier_that_is_not_text_is_never_turned_into_text(bad: Any) -> None:
    assert rejected(moneyline(book=bad)) == "invalid_identifier"
    assert rejected(moneyline(eventId=bad)) == "invalid_identifier"


def test_numeric_identifiers_are_read_as_text() -> None:
    snapshot = normalize_odds_snapshot(
        moneyline(eventId=4711, book="NorthLine"), "fixture", FETCHED
    )
    assert (snapshot.event_id, snapshot.sportsbook_id) == ("4711", "northline")
    assert snapshot.provider_id == "4711:moneyline:northline"


@pytest.mark.parametrize("selections", ["HOME,AWAY", [1, 2], [None, None], {"HOME": -110}, 7])
def test_selections_of_the_wrong_shape_are_rejected_not_crashed_on(selections: Any) -> None:
    assert rejected(moneyline(selections=selections)) == "malformed_payload"


@pytest.mark.parametrize("raw", [None, [], "text", 3])
def test_a_payload_that_is_not_an_object_is_rejected(raw: Any) -> None:
    for normalise in (normalize_event, normalize_odds_snapshot, normalize_game_log):
        with pytest.raises(ProviderContractError) as caught:
            normalise(raw, "fixture", FETCHED)
        assert caught.value.reason == "malformed_payload"


# ------------------------------------------------------------------- events
def event(**changes: Any) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "eventId": "evt_nhl_20260110_1",
        "leagueKey": "nhl",
        "startsAt": "2026-01-10T09:00:00Z",
        "state": "IN_PROGRESS",
        "home": {"teamId": "a"},
        "away": {"teamId": "b"},
        "score": {"home": 2, "away": 1},
        "clock": "P2 11:42",
    }
    raw.update(changes)
    return raw


def event_rejected(raw: dict[str, Any]) -> str:
    with pytest.raises(ProviderContractError) as caught:
        normalize_event(raw, "fixture", FETCHED)
    return caught.value.reason


@pytest.mark.parametrize(
    "bad", [-3, 101.9, "101.9", "NaN", float("nan"), float("inf"), "-1", "", "x", True, [3]]
)
def test_scores_must_be_whole_and_not_negative(bad: Any) -> None:
    assert event_rejected(event(score={"home": bad, "away": 1})) == "invalid_score"
    assert event_rejected(event(score={"home": 1, "away": bad})) == "invalid_score"


@pytest.mark.parametrize("bad", [10**30, "9" * 30, 1e30, 1001, "1001", "\u0663", "\uff13", "1_0"])
def test_scores_of_absurd_size_or_in_other_digits_are_rejected(bad: Any) -> None:
    assert event_rejected(event(score={"home": bad, "away": 1})) == "invalid_score"
    assert event_rejected(event(score={"home": 1, "away": bad})) == "invalid_score"


@pytest.mark.parametrize(
    "error",
    [AttributeError, KeyError, IndexError, TypeError, ValueError, OverflowError, ZeroDivisionError],
)
def test_an_error_no_named_check_foresaw_is_still_a_counted_contract_error(
    monkeypatch: pytest.MonkeyPatch, error: type[Exception]
) -> None:
    """Every field has a named check, so the safety net is reached by breaking one step on
    purpose. The failure must come out as a counted contract error without its own text."""

    def broken(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise error(PAYLOAD_MARKER)

    monkeypatch.setattr(normalize, "_provenance", broken)
    assert event_rejected(event()) == "malformed_payload"
    assert rejected(moneyline()) == "malformed_payload"
    with pytest.raises(ProviderContractError) as caught:
        normalize_game_log(game_log(), "fixture", FETCHED)
    assert caught.value.reason == "malformed_payload"
    assert str(caught.value) == "game_log payload is not shaped as expected"
    assert caught.value.__cause__ is None and caught.value.__suppress_context__
    assert rejection_counts() == {
        ("fixture", "event", "malformed_payload"): 1,
        ("fixture", "odds_snapshot", "malformed_payload"): 1,
        ("fixture", "game_log", "malformed_payload"): 1,
    }


def test_the_league_must_be_one_the_api_serves() -> None:
    """The response models take a fixed set of leagues: an event of any other league
    could be stored and would then fail every answer that lists it."""
    assert frozenset(get_args(LeagueKey)) == normalize._LEAGUES
    for bad in ("cricket", "nba2", "n", "all", 5):
        assert event_rejected(event(leagueKey=bad)) == "unknown_value"
    with pytest.raises(ProviderContractError, match="unknown league"):
        normalize_event(event(leagueKey="cricket"), "fixture", FETCHED)
    for key in get_args(LeagueKey):
        assert normalize_event(event(leagueKey=key.upper()), "fixture", FETCHED).league == key
        assert normalize_event(event(leagueKey=f" {key} "), "fixture", FETCHED).league == key


def test_an_event_needs_two_different_teams() -> None:
    assert event_rejected(event(home={"teamId": "a"}, away={"teamId": "a"})) == "same_team"
    assert event_rejected(event(home={"teamId": "a "}, away={"teamId": " a"})) == "same_team"
    assert event_rejected(event(home={"teamId": 7}, away={"teamId": "7"})) == "same_team"
    different = normalize_event(
        event(home={"teamId": "a"}, away={"teamId": "A"}), "fixture", FETCHED
    )
    assert (different.home_team_id, different.away_team_id) == ("a", "A")


def test_the_clock_of_a_live_event_is_a_short_text_or_absent() -> None:
    """Before, a text of any length was stored as the clock."""
    assert normalize_event(event(), "fixture", FETCHED).period_text == "P2 11:42"
    assert normalize_event(event(clock=" Q4 0:31 "), "fixture", FETCHED).period_text == "Q4 0:31"
    assert normalize_event(event(clock="x" * 200), "fixture", FETCHED).period_text == "x" * 200
    for absent in (
        without(event(), "clock"),
        event(clock=None),
        event(clock=""),
        event(clock="  "),
    ):
        assert normalize_event(absent, "fixture", FETCHED).period_text is None
    for bad in (5, 1.5, True, ["P2"], {"period": 2}, "x" * 201, "x" * 100_000, " " * 201):
        assert event_rejected(event(clock=bad)) == "invalid_text"
    for name, character in UNPRINTABLE.items():
        assert event_rejected(event(clock=f"P2{character}11:42")) == "invalid_text", name
    with pytest.raises(ProviderContractError, match="'clock' must be a short text"):
        normalize_event(event(clock=5), "fixture", FETCHED)
    # Only a live event has a clock; on any other event the field is not read.
    final = normalize_event(event(state="FINAL", clock=5), "fixture", FETCHED)
    assert final.period_text == "Final"
    upcoming = normalize_event(event(state="SCHEDULED", clock=["x"]), "fixture", FETCHED)
    assert upcoming.period_text is None


#: One megabyte in one field, in the forms each check could be slow on.
HUGE_TEXTS = {
    "digits": "7" * 1_000_000,
    "digits_then_underscore": "0" * 1_000_000 + "_0",
    "letters": "x" * 1_000_000,
    "spaces_then_a_letter": " " * 1_000_000 + "x",
    "signs": "+-" * 500_000,
    "a_timestamp_with_a_long_fraction": "2026-01-10T18:05:30." + "0" * 1_000_000 + "Z",
    "dots": "." * 1_000_000,
}


@pytest.mark.parametrize("name", list(HUGE_TEXTS))
def test_no_field_takes_long_to_refuse(name: str) -> None:
    """Every text field of every record refuses a megabyte of anything in well under a
    second; the limit is generous so that a busy machine does not fail the test."""
    text = HUGE_TEXTS[name]
    snapshots = [moneyline(**{key: text}) for key in ("eventId", "marketType", "book", "state")]
    snapshots += [moneyline(updatedAt=text), spread(text, 3.5), total(text, text)]
    snapshots.append(moneyline(selections=sides(text, "AWAY")))
    for key in ("label", "priceAmerican"):
        raw = moneyline()
        raw["selections"][1][key] = text
        snapshots.append(raw)
    events = [event(**{key: text}) for key in ("eventId", "leagueKey", "startsAt", "state")]
    events += [event(clock=text), event(scoreUpdatedAt=text), event(home={"teamId": text})]
    events += [event(away={"teamId": text}), event(score={"home": text, "away": 1})]
    logs = [game_log(text), game_log(date=text)]
    for key in ("eventId", "opp", "venue"):
        raw = game_log()
        raw["games"][0][key] = text
        logs.append(raw)
    raw = game_log()
    raw["playerId"] = text
    logs.append(raw)
    with within(5.0):
        for snapshot in snapshots:
            rejected(snapshot)
        for raw_event in events:
            event_rejected(raw_event)
        for raw_log in logs:
            with pytest.raises(ProviderContractError):
                normalize_game_log(raw_log, "fixture", FETCHED)
    assert sum(rejection_counts().values()) == len(snapshots) + len(events) + len(logs)


def test_whole_scores_in_any_plain_form_are_accepted() -> None:
    for home, away in ((2, 1), ("2", "1"), (2.0, 1.0), (0, 0), (101, 99), (1000, 0)):
        normalised = normalize_event(event(score={"home": home, "away": away}), "fixture", FETCHED)
        assert normalised.score is not None
        assert (normalised.score.home, normalised.score.away) == (int(home), int(away))
        assert isinstance(normalised.score.home, int)


def test_the_score_change_time_is_optional_and_checked() -> None:
    assert normalize_event(event(), "fixture", FETCHED).score_updated_at is None
    stamped = normalize_event(event(scoreUpdatedAt="2026-01-10T10:02:00Z"), "fixture", FETCHED)
    assert stamped.score_updated_at == datetime(2026, 1, 10, 10, 2, tzinfo=UTC)
    assert event_rejected(event(scoreUpdatedAt="2026-01-10T23:00:00Z")) == "future_timestamp"
    assert event_rejected(event(scoreUpdatedAt="10:02")) == "invalid_timestamp"
    # Only a live event has one.
    final = normalize_event(
        event(state="FINAL", scoreUpdatedAt="2026-01-10T10:02:00Z"), "fixture", FETCHED
    )
    assert final.score_updated_at is None


# ---------------------------------------------------------------- game logs
def game_log(stat: Any = 31, date: str = "2026-01-08T00:00:00Z") -> dict[str, Any]:
    return {
        "playerId": "p",
        "games": [
            {"eventId": "e", "date": date, "opp": "t", "venue": "H", "statLine": {"PTS": stat}}
        ],
    }


@pytest.mark.parametrize(
    ("bad", "reason"),
    [
        ("NaN", "non_finite_number"),
        (float("nan"), "non_finite_number"),
        ("Infinity", "non_finite_number"),
        (float("-inf"), "non_finite_number"),
        ("many", "invalid_number"),
        (None, "invalid_number"),
        (True, "invalid_number"),
    ],
)
def test_statistics_must_be_finite_numbers(bad: Any, reason: str) -> None:
    with pytest.raises(ProviderContractError) as caught:
        normalize_game_log(game_log(bad), "fixture", FETCHED)
    assert caught.value.reason == reason


@pytest.mark.parametrize("bad", [1e30, "1e30", -1e30, 100001, "\u0663\u0661", "3_1"])
def test_statistics_of_absurd_size_or_in_other_digits_are_rejected(bad: Any) -> None:
    with pytest.raises(ProviderContractError) as caught:
        normalize_game_log(game_log(bad), "fixture", FETCHED)
    assert caught.value.reason in ("out_of_range", "invalid_number")


def test_two_keys_for_the_same_statistic_are_rejected() -> None:
    """``PTS`` and ``P`` both mean points. Before, the last one silently won."""
    raw = game_log()
    raw["games"][0]["statLine"] = {"PTS": 31, "P": 2}
    with pytest.raises(ProviderContractError) as caught:
        normalize_game_log(raw, "fixture", FETCHED)
    assert caught.value.reason == "duplicate_statistic"
    raw["games"][0]["statLine"] = {"PTS": 31, "REB": 6, "AST": 7}
    (entry,) = normalize_game_log(raw, "fixture", FETCHED)
    assert entry.stats == {"points": 31.0, "rebounds": 6.0, "assists": 7.0}


def test_plain_statistics_are_accepted() -> None:
    for value in (31, 31.0, "31", 0, -4, 0.5):  # rushing yards can be negative
        (entry,) = normalize_game_log(game_log(value), "fixture", FETCHED)
        assert entry.stats == {"points": float(value)}
    # The limit of a statistic is 100,000, not the 1,000 of a line.
    for value in (1500, "1500", 4321.5, 100000, -100000, "1e5"):
        (entry,) = normalize_game_log(game_log(value), "fixture", FETCHED)
        assert entry.stats == {"points": float(value)}
    for value in (100000.5, -100001, "1.00001e5"):
        with pytest.raises(ProviderContractError) as caught:
            normalize_game_log(game_log(value), "fixture", FETCHED)
        assert caught.value.reason == "out_of_range"


def test_a_game_log_entry_from_the_future_is_rejected() -> None:
    with pytest.raises(ProviderContractError) as caught:
        normalize_game_log(game_log(date="2026-02-01T00:00:00Z"), "fixture", FETCHED)
    assert caught.value.reason == "future_timestamp"


@pytest.mark.parametrize("stat_line", [None, [], "PTS=3", 4])
def test_a_stat_line_of_the_wrong_shape_is_rejected(stat_line: Any) -> None:
    raw = game_log()
    raw["games"][0]["statLine"] = stat_line
    with pytest.raises(ProviderContractError) as caught:
        normalize_game_log(raw, "fixture", FETCHED)
    assert caught.value.reason in ("malformed_payload", "missing_field")


# ----------------------------------------------------- counting and logging
class _Collector(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def log() -> Iterator[_Collector]:
    logger = logging.getLogger("oddvex.providers")
    collector = _Collector()
    level = logger.level
    logger.addHandler(collector)
    logger.setLevel(logging.INFO)
    yield collector
    logger.removeHandler(collector)
    logger.setLevel(level)


def test_rejections_are_counted_by_provider_record_and_reason(log: _Collector) -> None:
    for _ in range(3):
        rejected(without(moneyline(), "updatedAt"))
    rejected(spread("NaN", 3.5))
    event_rejected(event(score={"home": -3, "away": 1}))
    with pytest.raises(ProviderContractError):
        normalize_game_log(game_log("NaN"), "other-vendor", FETCHED)
    normalize_odds_snapshot(moneyline(), "fixture", FETCHED)  # accepted: not counted
    assert rejection_counts() == {
        ("fixture", "odds_snapshot", "missing_timestamp"): 3,
        ("fixture", "odds_snapshot", "non_finite_number"): 1,
        ("fixture", "event", "invalid_score"): 1,
        ("other-vendor", "game_log", "non_finite_number"): 1,
    }
    assert len(log.records) == 6
    first = log.records[0]
    assert first.getMessage() == "provider_payload_rejected"
    assert first.levelno == logging.WARNING
    assert (first.provider, first.record, first.reason) == (  # type: ignore[attr-defined]
        "fixture",
        "odds_snapshot",
        "missing_timestamp",
    )
    assert [r.rejected_total for r in log.records[:3]] == [1, 2, 3]  # type: ignore[attr-defined]
    reset_rejection_counts()
    assert rejection_counts() == {}


def test_neither_the_log_nor_the_error_carries_the_payload(log: _Collector) -> None:
    cases: list[dict[str, Any]] = [
        moneyline(updatedAt=PAYLOAD_MARKER),
        moneyline(state=PAYLOAD_MARKER),
        moneyline(marketType=PAYLOAD_MARKER),
        moneyline(selections=sides(PAYLOAD_MARKER, "AWAY")),
        spread(PAYLOAD_MARKER, 3.5),
        moneyline(selections=PAYLOAD_MARKER),
    ]
    raw = moneyline()
    raw["selections"][0]["priceAmerican"] = PAYLOAD_MARKER
    cases.append(raw)
    for case in cases:
        with pytest.raises(ProviderContractError) as caught:
            normalize_odds_snapshot(case, "fixture", FETCHED)
        assert PAYLOAD_MARKER not in str(caught.value)
        assert PAYLOAD_MARKER not in caught.value.reason
    with pytest.raises(ProviderContractError) as caught:
        normalize_event(event(score={"home": PAYLOAD_MARKER, "away": 1}), "fixture", FETCHED)
    assert PAYLOAD_MARKER not in str(caught.value)
    with pytest.raises(ProviderContractError) as caught:
        normalize_game_log(game_log(PAYLOAD_MARKER), "fixture", FETCHED)
    assert PAYLOAD_MARKER not in str(caught.value)
    with pytest.raises(ProviderContractError) as caught:
        parse_timestamp(PAYLOAD_MARKER)
    assert PAYLOAD_MARKER not in str(caught.value)

    assert len(log.records) == len(cases) + 2
    for record in log.records:
        rendered = f"{record.getMessage()} {record.__dict__}"
        assert PAYLOAD_MARKER not in rendered
        assert record.exc_info is None  # no traceback, which would show the values
        assert set(record.__dict__) >= {"provider", "record", "reason", "rejected_total"}
    assert all(PAYLOAD_MARKER not in str(key) for key in rejection_counts())


@pytest.mark.parametrize("price", ["-77", 77, "+99", 0, "1234567", -1234567, "-1000001"])
def test_a_whole_number_that_is_not_a_price_is_not_quoted_in_the_error(
    log: _Collector, price: Any
) -> None:
    raw = moneyline()
    raw["selections"][0]["priceAmerican"] = price
    with pytest.raises(ProviderContractError) as caught:
        normalize_odds_snapshot(raw, "fixture", FETCHED)
    assert caught.value.reason == "invalid_price"
    assert str(caught.value) == "priceAmerican is not a valid American price"
    (record,) = log.records
    assert (record.getMessage(), record.reason) == (  # type: ignore[attr-defined]
        "provider_payload_rejected",
        "invalid_price",
    )
    assert record.exc_info is None and record.args in (None, ())


def test_the_error_message_still_names_the_field() -> None:
    with pytest.raises(ProviderContractError, match="updatedAt"):
        normalize_odds_snapshot(without(moneyline(), "updatedAt"), "fixture", FETCHED)
    with pytest.raises(ProviderContractError, match="handicap"):
        normalize_odds_snapshot(spread("NaN", 3.5), "fixture", FETCHED)
    with pytest.raises(ProviderContractError, match="score"):
        normalize_event(event(score={"home": -3, "away": 1}), "fixture", FETCHED)
