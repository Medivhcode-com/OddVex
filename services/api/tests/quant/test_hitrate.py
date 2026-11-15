from __future__ import annotations

import pytest

from oddvex_api.quant import QuantError, hit_rate, wilson_interval


def test_seven_of_ten_wilson_interval() -> None:
    low, high = wilson_interval(7, 10)
    assert low == pytest.approx(0.397, abs=0.001)
    assert high == pytest.approx(0.892, abs=0.001)


def test_wilson_known_values() -> None:
    low, high = wilson_interval(5, 10)
    assert (low, high) == (pytest.approx(0.2366, abs=1e-3), pytest.approx(0.7634, abs=1e-3))
    low, high = wilson_interval(50, 100)
    assert (low, high) == (pytest.approx(0.4038, abs=1e-3), pytest.approx(0.5962, abs=1e-3))


def test_wilson_extremes_stay_inside_unit_interval() -> None:
    low, high = wilson_interval(0, 10)
    assert low == 0.0
    assert 0.25 < high < 0.31
    low, high = wilson_interval(10, 10)
    assert high == 1.0
    assert 0.69 < low < 0.75


@pytest.mark.parametrize("n", [1, 7, 83, 1000])
def test_wilson_bounds_are_exact_at_zero_and_all_hits(n: int) -> None:
    assert wilson_interval(0, n)[0] == 0.0  # no float residue such as 3e-18
    assert wilson_interval(n, n)[1] == 1.0
    assert 0.0 < wilson_interval(0, n)[1] < 1.0
    assert 0.0 < wilson_interval(n, n)[0] < 1.0


def test_wilson_narrows_with_sample_size() -> None:
    small = wilson_interval(7, 10)
    large = wilson_interval(700, 1000)
    assert (large[1] - large[0]) < (small[1] - small[0])


@pytest.mark.parametrize(("hits", "n"), [(1, 0), (-1, 5), (6, 5), (0, -3)])
def test_wilson_rejects_impossible_counts(hits: int, n: int) -> None:
    with pytest.raises(QuantError) as error:
        wilson_interval(hits, n)
    assert error.value.code == "invalid_sample"


def test_wilson_rejects_non_positive_z() -> None:
    with pytest.raises(QuantError):
        wilson_interval(1, 2, z=0)


def test_hit_rate_counts_overs() -> None:
    values = [25, 30, 18, 22, 27, 31, 19, 24, 26, 28]
    result = hit_rate(values, 22.5)
    assert (result.hits, result.misses, result.pushes, result.sample_size) == (7, 3, 0, 10)
    assert result.rate == pytest.approx(0.7)
    assert result.ci_low == pytest.approx(0.397, abs=0.001)
    assert result.ci_high == pytest.approx(0.892, abs=0.001)
    assert result.confidence_level == 0.95


def test_pushes_are_excluded_from_the_sample() -> None:
    values = [25, 22, 22, 30, 18, 22, 27]
    result = hit_rate(values, 22)
    assert result.pushes == 3
    assert result.sample_size == 4
    assert result.hits == 3
    assert result.rate == pytest.approx(0.75)
    assert (result.ci_low, result.ci_high) == wilson_interval(3, 4)


def test_under_direction() -> None:
    values = [25, 22, 22, 30, 18, 22, 27]
    result = hit_rate(values, 22, direction="under")
    assert (result.hits, result.misses, result.pushes) == (1, 3, 3)
    assert result.rate == pytest.approx(0.25)


def test_empty_and_all_push_samples_have_no_rate() -> None:
    empty = hit_rate([], 10.5)
    assert (empty.sample_size, empty.rate, empty.ci_low, empty.ci_high) == (0, None, None, None)
    pushes = hit_rate([5, 5, 5], 5)
    assert pushes.pushes == 3
    assert pushes.sample_size == 0
    assert pushes.rate is None


def test_hit_rate_validates_input() -> None:
    with pytest.raises(QuantError):
        hit_rate([1, 2], 1.5, direction="sideways")  # type: ignore[arg-type]
    with pytest.raises(QuantError):
        hit_rate([1, 2], float("nan"))
