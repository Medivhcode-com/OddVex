"""Descriptive bet-history statistics (quant.tracker)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from oddvex_api.quant import QuantError, american_to_decimal
from oddvex_api.quant.tracker import (
    CLV_BOUNDS,
    CLV_BUCKETS,
    ODDS_BANDS,
    STAKE_BOUNDS,
    STAKE_BUCKETS,
    Streaks,
    bucket_index,
    mean,
    odds_band,
    streaks,
    win_rate,
)


@pytest.mark.parametrize(
    ("american", "band"),
    [
        (-1000, "-200_or_shorter"),
        (-201, "-200_or_shorter"),
        (-200, "-200_or_shorter"),
        (-199, "-199_to_-110"),
        (-150, "-199_to_-110"),
        (-110, "-199_to_-110"),
        (-109, "-109_to_+100"),
        (-101, "-109_to_+100"),
        (100, "-109_to_+100"),
        (101, "+101_to_+200"),
        (200, "+101_to_+200"),
        (201, "longer_than_+200"),
        (850, "longer_than_+200"),
    ],
)
def test_odds_band_boundaries(american: int, band: str) -> None:
    assert odds_band(american_to_decimal(american)) == band


def test_odds_band_uses_the_rounded_american_price() -> None:
    assert odds_band(Decimal("2.0")) == "-109_to_+100"  # even money is +100
    assert odds_band(Decimal("1.5")) == "-200_or_shorter"  # exactly -200
    assert odds_band(Decimal("3.0")) == "+101_to_+200"  # exactly +200
    assert odds_band(Decimal("3.004")) == "+101_to_+200"  # +200.4 rounds to +200
    assert odds_band(Decimal("3.006")) == "longer_than_+200"  # +200.6 rounds to +201
    with pytest.raises(QuantError):
        odds_band(Decimal("1.0"))
    assert [key for key, _ in ODDS_BANDS] == [
        "-200_or_shorter",
        "-199_to_-110",
        "-109_to_+100",
        "+101_to_+200",
        "longer_than_+200",
    ]


@pytest.mark.parametrize(
    ("value", "index"),
    [
        (-0.2, 0),
        (-0.05, 1),
        (-0.021, 1),
        (-0.02, 2),
        (-0.0001, 2),
        (0, 3),
        (0.0199, 3),
        (0.02, 4),
        (0.0499, 4),
        (0.05, 5),
        (3, 5),
    ],
)
def test_clv_buckets_include_the_lower_bound(value: float, index: int) -> None:
    assert bucket_index(value, CLV_BOUNDS) == index
    assert len(CLV_BUCKETS) == len(CLV_BOUNDS) + 1


@pytest.mark.parametrize(
    ("stake", "index"),
    [
        ("0.01", 0),
        ("9.99", 0),
        ("10", 1),
        ("24.99", 1),
        ("25", 2),
        ("49.99", 2),
        ("50", 3),
        ("99.99", 3),
        ("100", 4),
        ("1000000", 4),
    ],
)
def test_stake_buckets(stake: str, index: int) -> None:
    assert bucket_index(Decimal(stake), STAKE_BOUNDS) == index
    assert len(STAKE_BUCKETS) == len(STAKE_BOUNDS) + 1


def test_bucket_index_rejects_unordered_bounds() -> None:
    assert bucket_index(5, []) == 0
    with pytest.raises(QuantError):
        bucket_index(5, [10, 10])
    with pytest.raises(QuantError):
        bucket_index(5, [10, 5])
    with pytest.raises(QuantError):
        bucket_index(float("nan"), [1])


def test_win_rate() -> None:
    assert win_rate(0, 0) is None
    assert win_rate(3, 1) == 0.75
    assert win_rate(0, 4) == 0.0
    assert win_rate(2, 0) == 1.0
    with pytest.raises(QuantError):
        win_rate(-1, 2)


def test_mean() -> None:
    assert mean([]) is None
    assert mean([Decimal("10"), Decimal("20"), Decimal("45")]) == Decimal("25")
    assert mean([0.1, 0.2]) == Decimal("0.15")  # no float noise
    with pytest.raises(QuantError):
        mean(["abc"])


def test_streaks() -> None:
    assert streaks([]) == Streaks(0, 0, "none", 0)
    assert streaks([0, 0]) == Streaks(0, 0, "none", 0)
    assert streaks([10]) == Streaks(1, 0, "win", 1)
    assert streaks([-10]) == Streaks(0, 1, "loss", 1)
    # W W L W W W L L
    assert streaks([5, 5, -5, 5, 5, 5, -5, -5]) == Streaks(3, 2, "loss", 2)
    assert streaks([-1, -1, -1, -1, 2]) == Streaks(1, 4, "win", 1)


def test_a_push_neither_extends_nor_ends_a_streak() -> None:
    assert streaks([5, 0, 5, Decimal("0.00"), 5]) == Streaks(3, 0, "win", 3)
    assert streaks([-5, 0, -5, 5, 0]) == Streaks(1, 2, "win", 1)
    assert streaks([Decimal("-0.01"), Decimal("0.01")]) == Streaks(1, 1, "win", 1)
