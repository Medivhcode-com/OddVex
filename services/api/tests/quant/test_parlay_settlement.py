from __future__ import annotations

from decimal import Decimal

import pytest

from oddvex_api.quant import (
    INDEPENDENCE_NOTE,
    ParlayLeg,
    QuantError,
    combine_parlay,
    settle_bet,
    settle_parlay,
)

D = Decimal


def leg(
    odds: str, event: str | None = None, p: float | None = None, result: str = "pending"
) -> ParlayLeg:
    return ParlayLeg(decimal_odds=D(odds), event_id=event, win_probability=p, result=result)


# ------------------------------------------------------------------- combining
def test_combined_price_is_the_product_of_the_legs() -> None:
    result = combine_parlay([leg("2.0", "a"), leg("1.5", "b"), leg("3.0", "c")], stake=10)
    assert result.combined_decimal == D("9.00")
    assert result.active_legs == 3
    assert result.dropped_legs == 0
    assert result.payout == D("90.00")
    assert result.profit == D("80.00")


def test_two_minus_110_legs() -> None:
    price = D(210) / D(110)
    result = combine_parlay([leg(str(price), "a"), leg(str(price), "b")], stake=100)
    assert float(result.combined_decimal) == pytest.approx(3.644628, abs=1e-6)
    assert result.payout == D("364.46")


def test_pushed_and_void_legs_are_dropped() -> None:
    result = combine_parlay(
        [leg("2.0", "a"), leg("1.5", "b", result="push"), leg("3.0", "c", result="void")], stake=10
    )
    assert result.combined_decimal == D("2.0")
    assert result.active_legs == 1
    assert result.dropped_legs == 2
    assert result.payout == D("20.00")


def test_all_legs_dropped_returns_the_stake() -> None:
    result = combine_parlay(
        [leg("2.0", "a", result="push"), leg("3.0", "b", result="void")], stake=25
    )
    assert result.combined_decimal == D(1)
    assert result.active_legs == 0
    assert result.payout == D("25.00")
    assert result.profit == D("0.00")
    assert result.combined_probability is None


def test_combined_probability_for_distinct_events_assumes_independence() -> None:
    result = combine_parlay([leg("2.0", "a", 0.5), leg("2.5", "b", 0.4)])
    assert result.combined_probability == pytest.approx(0.2)
    assert result.probability_note == INDEPENDENCE_NOTE
    assert "assumes independence" in result.probability_note
    assert result.correlation_warnings == []
    assert result.payout is None


def test_dropped_legs_do_not_enter_the_combined_probability() -> None:
    result = combine_parlay(
        [leg("2.0", "a", 0.5), leg("2.5", "b", 0.4), leg("1.9", "c", 0.5, result="push")]
    )
    assert result.combined_probability == pytest.approx(0.2)


def test_same_event_legs_have_no_combined_probability() -> None:
    result = combine_parlay(
        [leg("2.0", "game1", 0.5), leg("2.5", "game1", 0.4), leg("1.8", "g2", 0.55)]
    )
    assert result.combined_probability is None
    assert len(result.correlation_warnings) == 1
    assert "game1" in result.correlation_warnings[0]
    assert "correlated" in result.correlation_warnings[0]
    # The price is still the product: it is what the book would pay, not a probability claim.
    assert result.combined_decimal == D("9.000")


def test_unknown_event_ids_block_the_combined_probability() -> None:
    result = combine_parlay([leg("2.0", None, 0.5), leg("2.5", "b", 0.4)])
    assert result.combined_probability is None
    assert any("no event_id" in warning for warning in result.correlation_warnings)


def test_missing_leg_probability_blocks_the_combined_probability() -> None:
    result = combine_parlay([leg("2.0", "a", 0.5), leg("2.5", "b")])
    assert result.combined_probability is None
    assert result.correlation_warnings == []
    assert "required" in result.probability_note


def test_single_leg_with_probability() -> None:
    result = combine_parlay([leg("2.0", None, 0.5)])
    assert result.combined_probability == pytest.approx(0.5)


def test_parlay_validation() -> None:
    with pytest.raises(QuantError) as error:
        combine_parlay([])
    assert error.value.code == "invalid_parlay"
    with pytest.raises(QuantError):
        combine_parlay([leg("1.0", "a")])
    with pytest.raises(QuantError):
        combine_parlay([leg("2.0", "a", 1.5)])
    with pytest.raises(QuantError) as error:
        combine_parlay([leg("2.0", "a", result="banana")])
    assert error.value.code == "invalid_leg_result"
    with pytest.raises(QuantError):
        combine_parlay([leg("2.0", "a")], stake=0)


# ------------------------------------------------------------------ settlement
@pytest.mark.parametrize(
    ("result", "payout", "profit"),
    [
        ("won", "250.00", "150.00"),
        ("lost", "0.00", "-100.00"),
        ("push", "100.00", "0.00"),
        ("void", "100.00", "0.00"),
        ("half_won", "175.00", "75.00"),
        ("half_lost", "50.00", "-50.00"),
    ],
)
def test_settle_single_bet(result: str, payout: str, profit: str) -> None:
    settlement = settle_bet(100, "2.5", result)
    assert settlement.result == result
    assert settlement.payout == D(payout)
    assert settlement.profit == D(profit)


def test_settle_at_minus_110() -> None:
    settlement = settle_bet(110, D(210) / D(110), "won")
    assert settlement.payout == D("210.00")
    assert settlement.profit == D("100.00")


def test_cashout() -> None:
    settlement = settle_bet(100, "2.5", "cashout", cashout_amount="140.50")
    assert settlement.payout == D("140.50")
    assert settlement.profit == D("40.50")
    below = settle_bet(100, "2.5", "cashout", cashout_amount=60)
    assert below.profit == D("-40.00")
    zero = settle_bet(100, "2.5", "cashout", cashout_amount=0)
    assert zero.payout == D("0.00")


def test_cashout_validation() -> None:
    with pytest.raises(QuantError) as error:
        settle_bet(100, "2.5", "cashout")
    assert error.value.code == "invalid_cashout"
    with pytest.raises(QuantError):
        settle_bet(100, "2.5", "cashout", cashout_amount=-1)


def test_settlement_rounds_to_cents() -> None:
    settlement = settle_bet("33.33", D(210) / D(110), "won")
    assert settlement.payout == D("63.63")
    assert settlement.profit == D("30.30")
    half = settle_bet("33.33", "2.5", "half_lost")
    assert half.payout == D("16.67")  # 16.665 half up


def test_settle_bet_validation() -> None:
    with pytest.raises(QuantError) as error:
        settle_bet(100, "2.5", "maybe")
    assert error.value.code == "invalid_result"
    with pytest.raises(QuantError):
        settle_bet(0, "2.5", "won")
    with pytest.raises(QuantError):
        settle_bet(100, "1", "won")


def test_parlay_all_legs_won() -> None:
    settlement = settle_parlay(10, [leg("2.0", result="won"), leg("3.0", result="won")])
    assert (settlement.result, settlement.payout, settlement.profit) == (
        "won",
        D("60.00"),
        D("50.00"),
    )


def test_parlay_one_lost_leg_loses_even_with_pending_legs() -> None:
    settlement = settle_parlay(10, [leg("2.0", result="lost"), leg("3.0")])
    assert (settlement.result, settlement.payout, settlement.profit) == (
        "lost",
        D("0.00"),
        D("-10.00"),
    )


def test_parlay_push_leg_reduces_the_price() -> None:
    settlement = settle_parlay(
        10, [leg("2.0", result="won"), leg("3.0", result="push"), leg("1.5", result="void")]
    )
    assert (settlement.result, settlement.payout) == ("won", D("20.00"))
    assert settlement.effective_decimal == D("2.0")


def test_parlay_of_only_pushes_and_voids() -> None:
    pushed = settle_parlay(10, [leg("2.0", result="push"), leg("3.0", result="void")])
    assert (pushed.result, pushed.payout, pushed.profit) == ("push", D("10.00"), D("0.00"))
    voided = settle_parlay(10, [leg("2.0", result="void"), leg("3.0", result="void")])
    assert voided.result == "void"


def test_parlay_with_half_results() -> None:
    half_won = settle_parlay(10, [leg("2.0", result="won"), leg("3.0", result="half_won")])
    # 2.0 * (1 + (3.0 - 1) / 2) = 4.0
    assert (half_won.result, half_won.payout) == ("half_won", D("40.00"))
    half_lost = settle_parlay(10, [leg("1.5", result="won"), leg("3.0", result="half_lost")])
    # 1.5 * 0.5 = 0.75 -> less than the stake comes back
    assert (half_lost.result, half_lost.payout, half_lost.profit) == (
        "half_lost",
        D("7.50"),
        D("-2.50"),
    )


def test_parlay_cannot_settle_with_pending_legs() -> None:
    with pytest.raises(QuantError) as error:
        settle_parlay(10, [leg("2.0", result="won"), leg("3.0")])
    assert error.value.code == "parlay_legs_pending"


def test_parlay_settlement_validation() -> None:
    with pytest.raises(QuantError):
        settle_parlay(10, [])
    with pytest.raises(QuantError):
        settle_parlay(0, [leg("2.0", result="won")])
    with pytest.raises(QuantError):
        settle_parlay(10, [leg("2.0", result="nope")])
