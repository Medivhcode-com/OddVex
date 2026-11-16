"""Flat-stake record of graded picks."""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from oddvex_api.quant import QuantError, american_to_decimal, wilson_interval
from oddvex_api.quant.record import (
    FLAT_STAKE_METHOD,
    SMALL_SAMPLE,
    flat_stake_profit,
    pick_record,
)

D = Decimal


def test_flat_stake_profit_per_result() -> None:
    assert flat_stake_profit("won", D("1.909091")) == D("0.909091")
    assert flat_stake_profit("won", D("2.5")) == D("1.5")
    assert flat_stake_profit("lost", D("2.5")) == D("-1")
    assert flat_stake_profit("push", D("2.5")) == D("0")
    assert flat_stake_profit("won", 2) == D("1")


@pytest.mark.parametrize("result", ["void", "half_won", "cashout", "", "WON"])
def test_only_won_lost_and_push_can_be_scored(result: str) -> None:
    with pytest.raises(QuantError) as error:
        flat_stake_profit(result, D("2"))
    assert error.value.code == "invalid_result"


@pytest.mark.parametrize("price", [D("1"), D("0.5"), D("-2"), 0])
def test_a_price_has_to_be_valid_decimal_odds(price: object) -> None:
    with pytest.raises(QuantError):
        flat_stake_profit("won", price)  # type: ignore[arg-type]
    with pytest.raises(QuantError):
        pick_record([("won", price)])  # type: ignore[list-item]


def test_an_empty_record() -> None:
    record = pick_record([])
    assert (record.picks, record.wins, record.losses, record.pushes) == (0, 0, 0, 0)
    assert record.win_rate is None and record.ci_low is None and record.ci_high is None
    assert record.average_decimal_odds is None and record.flat_stake_roi is None
    assert record.units_profit == D("0")


def test_a_hand_computed_record() -> None:
    # 3 wins at 2.00, 1.80 and 2.50; 2 losses at 1.90 and 3.00; 1 push at 1.95.
    graded = [
        ("won", D("2.00")),
        ("won", D("1.80")),
        ("lost", D("1.90")),
        ("push", D("1.95")),
        ("won", D("2.50")),
        ("lost", D("3.00")),
    ]
    record = pick_record(graded)
    assert (record.picks, record.wins, record.losses, record.pushes) == (6, 3, 2, 1)
    # Pushes are left out of the win rate: 3 / (3 + 2).
    assert record.win_rate == pytest.approx(0.6)
    low, high = wilson_interval(3, 5)
    assert (record.ci_low, record.ci_high) == (low, high)
    assert record.ci_low == pytest.approx(0.2307, abs=1e-4)
    assert record.ci_high == pytest.approx(0.8824, abs=1e-4)
    assert record.confidence_level == 0.95
    # +1.00 +0.80 -1 +0 +1.50 -1 = +1.30 units on 6 units staked (the push counts as staked).
    assert record.units_profit == D("1.30")
    assert record.flat_stake_roi == pytest.approx(1.30 / 6)
    assert record.average_decimal_odds == D("13.15") / 6


def test_only_pushes_have_no_win_rate_but_a_zero_roi() -> None:
    record = pick_record([("push", D("1.9")), ("push", D("2.1"))])
    assert record.win_rate is None and record.ci_low is None and record.ci_high is None
    assert record.units_profit == D("0") and record.flat_stake_roi == 0.0
    assert record.average_decimal_odds == D("2.0")


def test_all_wins_and_all_losses() -> None:
    wins = pick_record([("won", american_to_decimal(-110))] * 10)
    assert wins.win_rate == 1.0 and wins.ci_high == 1.0
    assert wins.ci_low == pytest.approx(0.7225, abs=1e-4)  # ten in a row proves little
    assert wins.flat_stake_roi == pytest.approx(100 / 110, abs=1e-6)
    losses = pick_record([("lost", D("2.2"))] * 4)
    assert losses.win_rate == 0.0 and losses.ci_low == 0.0
    assert losses.units_profit == D("-4") and losses.flat_stake_roi == -1.0


def test_a_winning_rate_at_short_prices_can_lose_units() -> None:
    # 6 of 10 at -200 (1.50): 6 * 0.5 - 4 = -1 unit. A win rate is not a return.
    record = pick_record([("won", D("1.5"))] * 6 + [("lost", D("1.5"))] * 4)
    assert record.win_rate == pytest.approx(0.6)
    assert record.units_profit == D("-1.0") and record.flat_stake_roi == pytest.approx(-0.1)


def test_the_method_and_the_small_sample_threshold_are_stated() -> None:
    assert SMALL_SAMPLE == 30
    for words in ("1 unit", "price recorded when the pick was posted", "Wilson 95%", "push"):
        assert words in FLAT_STAKE_METHOD


results = st.sampled_from(["won", "lost", "push"])
prices = st.decimals(min_value=D("1.01"), max_value=D("50"), places=4)


@given(st.lists(st.tuples(results, prices), max_size=80))
def test_record_invariants(graded: list[tuple[str, Decimal]]) -> None:
    record = pick_record(graded)
    assert record.picks == record.wins + record.losses + record.pushes == len(graded)
    assert record.units_profit == sum((flat_stake_profit(r, p) for r, p in graded), D(0))
    # Never better than winning every pick, never worse than losing every pick.
    assert -record.picks <= record.units_profit <= sum((p - 1 for _, p in graded), D(0))
    if record.wins + record.losses:
        assert record.win_rate is not None and record.ci_low is not None
        assert record.ci_high is not None
        assert 0.0 <= record.ci_low <= record.win_rate <= record.ci_high <= 1.0
    else:
        assert record.win_rate is None and record.ci_low is None
    if graded:
        assert record.flat_stake_roi == pytest.approx(float(record.units_profit) / len(graded))
        assert record.flat_stake_roi >= -1.0
    else:
        assert record.flat_stake_roi is None


@given(st.lists(st.tuples(results, prices), min_size=1, max_size=40))
def test_the_order_of_picks_does_not_matter(graded: list[tuple[str, Decimal]]) -> None:
    assert pick_record(graded) == pick_record(list(reversed(graded)))
