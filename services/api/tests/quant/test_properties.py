"""Property tests: invariants that must hold for any valid input."""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oddvex_api.quant import (
    ParlayLeg,
    american_to_decimal,
    closing_line_value,
    combine_parlay,
    decimal_to_american,
    decimal_to_fractional,
    expected_value,
    fractional_to_decimal,
    hit_rate,
    implied_probability,
    no_vig,
    settle_bet,
    wilson_interval,
)

american = st.one_of(st.integers(100, 20000), st.integers(-20000, -101))
decimal_odds = st.decimals(min_value="1.01", max_value="500", places=3)
probability = st.floats(min_value=0.001, max_value=0.999)
stake = st.decimals(min_value="0.01", max_value="100000", places=2)

settings.register_profile("oddvex", max_examples=150, deadline=None)
settings.load_profile("oddvex")


@given(american)
def test_american_round_trips_through_decimal(price: int) -> None:
    assert decimal_to_american(american_to_decimal(price)) == price


@given(american)
def test_implied_probability_is_a_probability(price: int) -> None:
    assert 0 < implied_probability(american_to_decimal(price)) < 1


@given(american, american)
def test_better_american_price_has_lower_implied_probability(a: int, b: int) -> None:
    da, db = american_to_decimal(a), american_to_decimal(b)
    if da > db:
        assert implied_probability(da) < implied_probability(db)


@given(st.integers(1, 500), st.integers(1, 100))
def test_fractional_round_trip_is_reduced(numerator: int, denominator: int) -> None:
    text = decimal_to_fractional(fractional_to_decimal(f"{numerator}/{denominator}"))
    n, d = (int(part) for part in text.split("/"))
    assert Fraction(n, d) == Fraction(numerator, denominator)
    assert Fraction(n, d).numerator == n  # already in lowest terms


@given(st.lists(decimal_odds, min_size=2, max_size=8))
def test_no_vig_probabilities_sum_to_one(prices: list[Decimal]) -> None:
    result = no_vig(prices)
    assert sum(result.fair_probabilities) == pytest.approx(1.0)
    assert all(0 < p < 1 for p in result.fair_probabilities)
    assert result.overround == pytest.approx(sum(result.implied_probabilities) - 1)
    if result.overround > 0:
        assert 0 < result.hold < result.overround
        assert all(
            fair < implied
            for fair, implied in zip(
                result.fair_probabilities, result.implied_probabilities, strict=True
            )
        )


@given(probability, decimal_odds)
def test_ev_sign_matches_edge(p: float, price: Decimal) -> None:
    result = expected_value(p, price)
    assert result.ev_per_unit == pytest.approx(p * float(price) - 1, abs=1e-9)
    if abs(result.edge) > 1e-9:
        assert (result.ev_per_unit > 0) == (result.edge > 0)


@given(decimal_odds, decimal_odds)
def test_clv_sign_matches_price_comparison(taken: Decimal, closing: Decimal) -> None:
    result = closing_line_value(taken, closing)
    assert result.beat_close == (taken > closing)
    assert (result.clv_percent > 0) == (taken > closing)


@given(st.integers(0, 200), st.integers(1, 200))
def test_wilson_interval_brackets_the_point_estimate(hits: int, extra: int) -> None:
    n = hits + extra if hits else extra
    hits = min(hits, n)
    low, high = wilson_interval(hits, n)
    assert 0.0 <= low <= hits / n <= high <= 1.0


@given(st.lists(st.integers(0, 60), max_size=40), st.integers(0, 60))
def test_hit_rate_partitions_the_sample(values: list[int], line: int) -> None:
    result = hit_rate(values, line)
    assert result.hits + result.misses + result.pushes == len(values)
    assert result.sample_size == result.hits + result.misses
    assert result.pushes == sum(1 for v in values if v == line)
    under = hit_rate(values, line, "under")
    assert under.hits == result.misses


@given(st.lists(decimal_odds, min_size=1, max_size=8), stake)
def test_parlay_price_is_the_product(prices: list[Decimal], amount: Decimal) -> None:
    result = combine_parlay(
        [ParlayLeg(decimal_odds=p, event_id=f"e{i}") for i, p in enumerate(prices)], stake=amount
    )
    product = Decimal(1)
    for price in prices:
        product *= price
    assert result.combined_decimal == product
    assert result.payout is not None and result.profit is not None
    assert result.payout - result.profit == pytest.approx(amount, abs=Decimal("0.01"))


@given(stake, decimal_odds)
def test_settlement_identities(amount: Decimal, price: Decimal) -> None:
    won = settle_bet(amount, price, "won")
    lost = settle_bet(amount, price, "lost")
    push = settle_bet(amount, price, "push")
    half_won = settle_bet(amount, price, "half_won")
    half_lost = settle_bet(amount, price, "half_lost")
    assert lost.payout == 0 and lost.profit == -amount
    assert push.payout == amount and push.profit == 0
    assert won.profit == won.payout - amount
    assert lost.payout <= half_lost.payout <= push.payout <= half_won.payout <= won.payout
    for settlement in (won, lost, push, half_won, half_lost):
        assert settlement.payout == settlement.payout.quantize(Decimal("0.01"))
