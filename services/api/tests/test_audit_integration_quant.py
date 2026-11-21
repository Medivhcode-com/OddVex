"""Every calculator route answers 422 in the error envelope for a price it cannot compute,
never 500 (quant-data#3).

Decimal arithmetic works to 28 significant digits: a price such as decimal 1e30, or the
combined price of twenty +100000 legs, used to overflow when it was rounded (to a whole
American price or to cents) and end as ``decimal.InvalidOperation`` and a 500.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from oddvex_api.quant import QuantError, decimal_to_american, money
from oddvex_api.quant.odds import MAX_DECIMAL_ODDS, bounded_price

LONG_DIGITS = "9" * 200
#: (odds_format, value) pairs no calculator can compute: too long, too short, not finite,
#: or not a number at all.
EXTREMES: list[tuple[str, Any]] = [
    ("decimal", 1e30),
    ("decimal", "1e30"),
    ("decimal", 1e308),
    ("decimal", "1e308"),
    ("decimal", "1e999999"),
    ("decimal", "1e9999999999"),
    ("decimal", LONG_DIGITS),
    ("decimal", "1" + "0" * 2000),
    ("decimal", "10000000000"),
    ("decimal", "NaN"),
    ("decimal", "sNaN"),
    ("decimal", "Infinity"),
    ("decimal", "-Infinity"),
    ("american", 1e308),
    ("american", "1e308"),
    ("american", "-1e308"),
    ("american", "1e999999"),
    ("american", "-1e999999"),
    ("american", "1e9999999999"),
    ("american", LONG_DIGITS),
    ("american", "-" + LONG_DIGITS),
    ("american", "NaN"),
    ("american", "sNaN"),
    ("fractional", "1e308/1"),
    ("fractional", "1/1e308"),
    ("fractional", "1e999999"),
    ("fractional", "1e9999999999"),
    ("fractional", LONG_DIGITS + "/1"),
    ("fractional", "1/" + LONG_DIGITS),
    ("fractional", "NaN"),
    ("fractional", "sNaN"),
]

#: A sane price in each format, for the other side of a market.
SANE = {"american": 100, "decimal": 2, "fractional": "1/1"}


def bodies(odds_format: str, value: Any) -> list[tuple[str, dict[str, Any]]]:
    """One request per calculator route (and per position) carrying ``value``."""
    sane = SANE[odds_format]
    return [
        ("/v1/quant/convert", {"odds": value, "odds_format": odds_format}),
        ("/v1/quant/no-vig", {"odds": [value, sane], "odds_format": odds_format}),
        ("/v1/quant/no-vig", {"odds": [value, value], "odds_format": odds_format}),
        (
            "/v1/quant/ev",
            {"odds": value, "odds_format": odds_format, "win_probability": 0.5, "stake": 1e6},
        ),
        ("/v1/quant/parlay", {"legs": [{"odds": value, "odds_format": odds_format}]}),
        (
            "/v1/quant/parlay",
            {"legs": [{"odds": value, "odds_format": odds_format}] * 20, "stake": 1e6},
        ),
        ("/v1/quant/clv", {"odds": value, "closing_odds": sane, "odds_format": odds_format}),
        ("/v1/quant/clv", {"odds": sane, "closing_odds": value, "odds_format": odds_format}),
        (
            "/v1/quant/clv",
            {
                "odds": sane,
                "closing_odds": sane,
                "closing_opposite_odds": value,
                "odds_format": odds_format,
            },
        ),
    ]


def assert_refused(client: TestClient, path: str, body: dict[str, Any]) -> dict[str, Any]:
    response = client.post(path, json=body)
    assert response.status_code == 422, (path, response.status_code, response.text[:300])
    error = response.json()
    assert set(error) == {"error"} and set(error["error"]) <= {"code", "message", "details"}
    assert error["error"]["code"] and error["error"]["message"]
    return error["error"]


def test_the_reported_inputs_are_422(client: TestClient) -> None:
    convert = assert_refused(client, "/v1/quant/convert", {"odds": 1e30, "odds_format": "decimal"})
    assert convert["code"] == "odds_out_of_range"
    assert str(MAX_DECIMAL_ODDS) in convert["message"]
    parlay = assert_refused(client, "/v1/quant/parlay", {"legs": [{"odds": 100000}] * 20})
    assert parlay["code"] == "odds_out_of_range"
    assert "combined price" in parlay["message"]
    with_stake = {"legs": [{"odds": 100000}] * 20, "stake": 1}
    assert assert_refused(client, "/v1/quant/parlay", with_stake)["code"] == "odds_out_of_range"


@pytest.mark.parametrize(("odds_format", "value"), EXTREMES, ids=lambda v: str(v)[:24])
def test_every_quant_route_refuses_an_extreme_price_with_422(
    client: TestClient, odds_format: str, value: Any
) -> None:
    for path, body in bodies(odds_format, value):
        assert_refused(client, path, body)


def test_a_price_too_short_to_show_is_422_where_it_is_shown(client: TestClient) -> None:
    # 1 + 1e-61: its American price has more than 28 digits. Where it is only used for a
    # probability (the other side of a closing market) it computes; nowhere is it a 500.
    short = "1." + "0" * 60 + "1"
    for path, body in bodies("decimal", short):
        if body.get("closing_opposite_odds") == short:
            response = client.post(path, json=body)
            assert response.status_code == 200, (path, response.text)
        else:
            error = assert_refused(client, path, body)
            assert error["code"] == "odds_out_of_range", (path, error)


def test_twenty_extreme_legs_are_422_on_every_parlay_shape(client: TestClient) -> None:
    longest = str(MAX_DECIMAL_ODDS)
    for legs in (
        [{"odds": longest, "odds_format": "decimal"}] * 20,
        [{"odds": 100000}] * 20,
        [{"odds": "1000000/1", "odds_format": "fractional"}] * 20,
    ):
        for stake in (None, 0.01, 1e6):
            body: dict[str, Any] = {"legs": legs}
            if stake is not None:
                body["stake"] = stake
            assert assert_refused(client, "/v1/quant/parlay", body)["code"] == "odds_out_of_range"
    # Pushed and void legs drop out: the combined price is the one counted leg.
    mixed = [{"odds": longest, "odds_format": "decimal", "result": "push"}] * 19
    mixed.append({"odds": longest, "odds_format": "decimal"})
    ok = client.post("/v1/quant/parlay", json={"legs": mixed, "stake": 1})
    assert ok.status_code == 200, ok.text
    assert ok.json()["active_legs"] == 1 and ok.json()["dropped_legs"] == 19


def test_the_longest_price_and_short_prices_still_compute(client: TestClient) -> None:
    for value in (str(MAX_DECIMAL_ODDS), "1.000001", "1.0000004"):
        convert = client.post("/v1/quant/convert", json={"odds": value, "odds_format": "decimal"})
        assert convert.status_code == 200, convert.text
        ev = client.post(
            "/v1/quant/ev",
            json={"odds": value, "odds_format": "decimal", "win_probability": 0.5, "stake": 1e6},
        )
        assert ev.status_code == 200, ev.text
        clv = client.post(
            "/v1/quant/clv",
            json={
                "odds": value,
                "closing_odds": value,
                "closing_opposite_odds": value,
                "odds_format": "decimal",
            },
        )
        assert clv.status_code == 200, clv.text
    assert (
        client.post("/v1/quant/convert", json={"odds": 1e10 - 1, "odds_format": "decimal"}).json()[
            "price"
        ]["american"]
        == 999999999800
    )
    # A long but computable parlay: two legs whose product is just in range.
    two = client.post(
        "/v1/quant/parlay",
        json={"legs": [{"odds": "99999", "odds_format": "decimal"}] * 2, "stake": 1e6},
    )
    assert two.status_code == 200, two.text
    assert two.json()["payout"] == pytest.approx(9999800001e6)
    # Everyday prices are unchanged.
    assert (
        client.post("/v1/quant/convert", json={"odds": -110}).json()["price"]["decimal"] == 1.9091
    )


def test_the_library_turns_overflow_into_quant_error() -> None:
    with pytest.raises(QuantError) as american:
        decimal_to_american(Decimal("1e30"))
    assert american.value.code == "odds_out_of_range"
    with pytest.raises(QuantError):
        decimal_to_american(Decimal("1." + "0" * 40 + "1"))
    with pytest.raises(QuantError) as cents:
        money(Decimal("1e40"))
    assert cents.value.code == "amount_out_of_range"
    assert money(Decimal("12.345")) == Decimal("12.35")
    with pytest.raises(QuantError):
        bounded_price(Decimal("1e30"))
    with pytest.raises(QuantError):
        bounded_price(Decimal("NaN"))
    assert bounded_price(MAX_DECIMAL_ODDS) == MAX_DECIMAL_ODDS
    assert bounded_price(Decimal("1.5")) == Decimal("1.5")


def test_an_arithmetic_error_left_in_a_route_is_422(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from decimal import Overflow

    from oddvex_api.api import quant_routes

    def overflow(*_: Any, **__: Any) -> Any:
        raise Overflow("simulated")

    monkeypatch.setattr(quant_routes, "no_vig", overflow)
    error = assert_refused(client, "/v1/quant/no-vig", {"odds": [-110, -110]})
    assert error["code"] == "not_computable"
