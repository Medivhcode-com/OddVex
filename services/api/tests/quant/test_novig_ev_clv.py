from __future__ import annotations

from decimal import Decimal

import pytest

from oddvex_api.quant import (
    QuantError,
    american_to_decimal,
    closing_line_value,
    expected_value,
    money,
    no_vig,
    payout,
    profit,
    roi,
    validate_stake,
)

M110 = american_to_decimal(-110)


# ---------------------------------------------------------------------- no-vig
def test_minus_110_both_sides_is_fifty_fifty() -> None:
    result = no_vig([M110, M110])
    assert result.fair_probabilities == pytest.approx((0.5, 0.5))
    assert result.overround == pytest.approx(0.047619, abs=1e-6)
    assert result.hold == pytest.approx(0.045455, abs=1e-6)
    assert result.method == "multiplicative"


def test_two_way_unbalanced_market() -> None:
    result = no_vig([american_to_decimal(-150), american_to_decimal(130)])
    implied_fav, implied_dog = 150 / 250, 100 / 230
    total = implied_fav + implied_dog
    assert result.implied_probabilities == pytest.approx((implied_fav, implied_dog))
    assert result.fair_probabilities == pytest.approx((implied_fav / total, implied_dog / total))
    assert sum(result.fair_probabilities) == pytest.approx(1.0)
    assert result.overround == pytest.approx(total - 1)


def test_three_way_market() -> None:
    result = no_vig(["2.4", "3.3", "3.1"])
    assert len(result.fair_probabilities) == 3
    assert sum(result.fair_probabilities) == pytest.approx(1.0)
    assert result.overround == pytest.approx(1 / 2.4 + 1 / 3.3 + 1 / 3.1 - 1)
    # Proportional method preserves the ordering of the outcomes.
    assert (
        result.fair_probabilities[0] > result.fair_probabilities[2] > result.fair_probabilities[1]
    )


def test_n_way_market_of_five() -> None:
    result = no_vig([4, 4, 4, 4, 4])
    assert result.fair_probabilities == pytest.approx((0.2,) * 5)
    assert result.overround == pytest.approx(0.25)
    assert result.hold == pytest.approx(0.2)


def test_fair_market_has_no_overround() -> None:
    result = no_vig([2, 2])
    assert result.overround == pytest.approx(0.0)
    assert result.hold == pytest.approx(0.0)


def test_no_vig_needs_two_outcomes_and_valid_prices() -> None:
    with pytest.raises(QuantError) as error:
        no_vig([2])
    assert error.value.code == "invalid_market"
    with pytest.raises(QuantError):
        no_vig([])
    with pytest.raises(QuantError):
        no_vig([2, 1])


# -------------------------------------------------------------- payout / profit
def test_payout_and_profit() -> None:
    assert payout(100, "2.5") == Decimal("250.00")
    assert profit(100, "2.5") == Decimal("150.00")
    assert payout("110", M110) == Decimal("210.00")
    assert profit("110", M110) == Decimal("100.00")


def test_money_rounds_half_up_to_cents() -> None:
    assert money(Decimal("1.005")) == Decimal("1.01")
    assert money(Decimal("1.004")) == Decimal("1.00")
    assert money(Decimal("-1.005")) == Decimal("-1.01")
    assert payout("0.10", "1.05") == Decimal("0.11")  # 0.105 rounds up, not to even


@pytest.mark.parametrize("bad", [0, -5, "abc", float("inf")])
def test_stake_must_be_positive(bad: object) -> None:
    with pytest.raises(QuantError):
        validate_stake(bad)  # type: ignore[arg-type]
    with pytest.raises(QuantError):
        payout(bad, 2)  # type: ignore[arg-type]


def test_roi() -> None:
    assert roi(25, 100) == pytest.approx(0.25)
    assert roi(-10, 200) == pytest.approx(-0.05)
    assert roi(Decimal("0"), Decimal("50")) == 0.0
    assert roi(10, 0) is None
    with pytest.raises(QuantError):
        roi(10, -1)


# -------------------------------------------------------------------------- EV
def test_plus_150_at_45_percent_is_plus_12_5_percent() -> None:
    result = expected_value(0.45, american_to_decimal(150))
    assert result.ev_per_unit == pytest.approx(0.125)
    assert result.ev_percent == pytest.approx(12.5)
    assert result.breakeven_probability == pytest.approx(0.4)
    assert result.edge == pytest.approx(0.05)
    assert result.expected_profit == Decimal("0.13")  # 0.125 on a 1-unit stake, half up


def test_ev_scales_with_stake() -> None:
    result = expected_value(0.45, "2.5", stake=200)
    assert result.expected_profit == Decimal("25.00")
    assert result.ev_percent == pytest.approx(12.5)


def test_ev_is_zero_at_the_breakeven_probability() -> None:
    result = expected_value(0.5, 2)
    assert result.ev_per_unit == pytest.approx(0.0)
    assert result.edge == pytest.approx(0.0)


def test_negative_ev() -> None:
    result = expected_value(0.5, M110)
    assert result.ev_percent == pytest.approx(-4.5454545, abs=1e-6)
    assert result.expected_profit == Decimal("-0.05")


@pytest.mark.parametrize("p", [0, 1, -0.2, 1.5])
def test_ev_rejects_probability_outside_open_interval(p: float) -> None:
    with pytest.raises(QuantError) as error:
        expected_value(p, 2)
    assert error.value.code == "invalid_probability"


def test_ev_rejects_bad_price_and_stake() -> None:
    with pytest.raises(QuantError):
        expected_value(0.5, 1)
    with pytest.raises(QuantError):
        expected_value(0.5, 2, stake=0)


# ------------------------------------------------------------------------- CLV
def test_price_based_clv() -> None:
    result = closing_line_value("2.10", "2.00")
    assert result.clv_percent == pytest.approx(5.0)
    assert result.beat_close is True
    assert result.closing_no_vig_probability is None
    assert result.no_vig_probability_delta is None
    assert result.ev_at_close_percent is None


def test_negative_and_zero_clv() -> None:
    worse = closing_line_value("1.90", "2.00")
    assert worse.clv_percent == pytest.approx(-5.0)
    assert worse.beat_close is False
    same = closing_line_value(2, 2)
    assert same.clv_percent == pytest.approx(0.0)
    assert same.beat_close is False


def test_no_vig_clv_with_two_sided_close() -> None:
    # Took +110; closed -110 / -110, so the fair closing probability is 50%.
    result = closing_line_value(american_to_decimal(110), M110, M110)
    assert result.closing_no_vig_probability == pytest.approx(0.5)
    assert result.no_vig_probability_delta == pytest.approx(0.5 - 1 / 2.1)
    assert result.ev_at_close_percent == pytest.approx(5.0)
    assert result.clv_percent == pytest.approx((2.1 / (210 / 110) - 1) * 100)


def test_no_vig_clv_uses_the_selection_side() -> None:
    result = closing_line_value("2.5", american_to_decimal(130), american_to_decimal(-150))
    implied_sel, implied_opp = 100 / 230, 150 / 250
    fair = implied_sel / (implied_sel + implied_opp)
    assert result.closing_no_vig_probability == pytest.approx(fair)
    assert result.no_vig_probability_delta == pytest.approx(fair - 0.4)


def test_clv_rejects_invalid_prices() -> None:
    with pytest.raises(QuantError):
        closing_line_value(1, 2)
    with pytest.raises(QuantError):
        closing_line_value(2, 1)
    with pytest.raises(QuantError):
        closing_line_value(2, 2, 0.5)
