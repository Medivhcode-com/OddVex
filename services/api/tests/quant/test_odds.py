from __future__ import annotations

from decimal import Decimal

import pytest

from oddvex_api.quant import (
    QuantError,
    american_to_decimal,
    decimal_to_american,
    decimal_to_fractional,
    describe_price,
    fractional_to_decimal,
    implied_probability,
    parse_odds,
    probability_to_decimal,
    validate_decimal_odds,
    validate_probability,
)


@pytest.mark.parametrize(
    ("american", "decimal"),
    [
        (150, "2.5"),
        (100, "2"),
        (-100, "2"),
        (-200, "1.5"),
        (-400, "1.25"),
        (250, "3.5"),
        (10000, "101"),
        ("+150", "2.5"),
        ("-200", "1.5"),
    ],
)
def test_american_to_decimal_exact(american: int | str, decimal: str) -> None:
    assert american_to_decimal(american) == Decimal(decimal)


def test_american_minus_110() -> None:
    assert float(american_to_decimal(-110)) == pytest.approx(1.909090909, abs=1e-9)


@pytest.mark.parametrize("bad", [0, 1, 50, 99, -1, -50, -99, 99.9, -99.5, "12"])
def test_american_inside_dead_zone_is_invalid(bad: float | str) -> None:
    with pytest.raises(QuantError) as error:
        american_to_decimal(bad)
    assert error.value.code == "invalid_american_odds"


@pytest.mark.parametrize("bad", ["abc", "", None, float("nan"), float("inf"), True])
def test_american_rejects_non_numbers(bad: object) -> None:
    with pytest.raises(QuantError):
        american_to_decimal(bad)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("decimal", "american"),
    [("2.5", 150), ("2", 100), ("1.5", -200), ("1.25", -400), ("3.5", 250), ("1.909091", -110)],
)
def test_decimal_to_american(decimal: str, american: int) -> None:
    assert decimal_to_american(decimal) == american


def test_decimal_to_american_never_returns_minus_100() -> None:
    assert decimal_to_american("1.999") == 100
    assert decimal_to_american("2.001") == 100


@pytest.mark.parametrize("bad", [1, "1.0", 0.5, 0, -2, "1"])
def test_decimal_at_or_below_one_is_invalid(bad: float | str) -> None:
    with pytest.raises(QuantError) as error:
        validate_decimal_odds(bad)
    assert error.value.code == "invalid_decimal_odds"
    with pytest.raises(QuantError):
        decimal_to_american(bad)
    with pytest.raises(QuantError):
        implied_probability(bad)


@pytest.mark.parametrize(
    ("text", "decimal"),
    [
        ("5/2", "3.5"),
        ("10/11", None),
        ("1/1", "2"),
        (" 7 / 4 ", "2.75"),
        ("2", "3"),
        ("1/2", "1.5"),
    ],
)
def test_fractional_to_decimal(text: str, decimal: str | None) -> None:
    result = fractional_to_decimal(text)
    if decimal is None:
        assert float(result) == pytest.approx(1 + 10 / 11)
    else:
        assert result == Decimal(decimal)


@pytest.mark.parametrize("bad", ["0/1", "5/0", "-5/2", "a/b", "5/", "/2", "", "5/2/1", "NaN"])
def test_fractional_rejects_garbage(bad: str) -> None:
    with pytest.raises(QuantError) as error:
        fractional_to_decimal(bad)
    assert error.value.code == "invalid_fractional_odds"


def test_fractional_requires_a_string() -> None:
    with pytest.raises(QuantError):
        fractional_to_decimal(2.5)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("decimal", "fraction"),
    [
        ("3.5", "5/2"),
        ("2", "1/1"),
        ("1.5", "1/2"),
        ("2.5", "3/2"),
        ("1.909091", "10/11"),
        ("6", "5/1"),
        ("3.0", "2/1"),
        ("1.4", "2/5"),
    ],
)
def test_decimal_to_fractional_is_reduced(decimal: str, fraction: str) -> None:
    assert decimal_to_fractional(decimal) == fraction


def test_fractional_output_of_unreduced_input_is_reduced() -> None:
    assert decimal_to_fractional(fractional_to_decimal("10/4")) == "5/2"
    assert decimal_to_fractional(fractional_to_decimal("4/2")) == "2/1"


def test_very_short_price_still_has_a_positive_fraction() -> None:
    assert decimal_to_fractional("1.0001") == "1/100"


@pytest.mark.parametrize(
    ("decimal", "probability"), [("2", 0.5), ("4", 0.25), ("1.25", 0.8), ("2.5", 0.4)]
)
def test_implied_probability(decimal: str, probability: float) -> None:
    assert implied_probability(decimal) == pytest.approx(probability)


def test_implied_probability_of_minus_110() -> None:
    assert implied_probability(american_to_decimal(-110)) == pytest.approx(110 / 210)


@pytest.mark.parametrize("bad", [0, 1, -0.1, 1.2, float("nan"), "x", None])
def test_probability_must_be_strictly_inside_unit_interval(bad: object) -> None:
    with pytest.raises(QuantError) as error:
        validate_probability(bad)  # type: ignore[arg-type]
    assert error.value.code == "invalid_probability"


def test_probability_to_decimal() -> None:
    assert probability_to_decimal(0.5) == Decimal(2)
    assert probability_to_decimal(0.25) == Decimal(4)
    with pytest.raises(QuantError):
        probability_to_decimal(1.0)


def test_parse_odds_dispatches_on_format() -> None:
    assert parse_odds("american", 150) == Decimal("2.5")
    assert parse_odds("american", "150") == Decimal("2.5")
    assert parse_odds("decimal", "2.5") == Decimal("2.5")
    assert parse_odds("decimal", 2.5) == Decimal("2.5")
    assert parse_odds("fractional", "3/2") == Decimal("2.5")


def test_parse_odds_rejects_bad_input() -> None:
    with pytest.raises(QuantError) as error:
        parse_odds("american", 150.5)
    assert error.value.code == "invalid_american_odds"
    with pytest.raises(QuantError) as error:
        parse_odds("moneyline", 150)
    assert error.value.code == "invalid_odds_format"
    with pytest.raises(QuantError):
        parse_odds("decimal", 1)


def test_describe_price_has_every_format() -> None:
    price = describe_price("2.5")
    assert (price.american, price.decimal, price.fractional) == (150, Decimal("2.5"), "3/2")
    assert price.implied_probability == pytest.approx(0.4)


def test_float_inputs_do_not_leak_binary_noise() -> None:
    assert american_to_decimal(110.0) == Decimal("2.1")
    assert validate_decimal_odds(2.1) == Decimal("2.1")
