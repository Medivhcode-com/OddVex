"""Calculator endpoints: values come from quant, plus human-readable steps."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def post(client: TestClient, name: str, body: dict, status: int = 200) -> dict:
    response = client.post(f"/v1/quant/{name}", json=body)
    assert response.status_code == status, response.text
    return response.json()


@pytest.mark.parametrize(
    ("body", "american", "decimal", "fractional"),
    [
        ({"odds": 150}, 150, 2.5, "3/2"),
        ({"odds": "+150"}, 150, 2.5, "3/2"),
        ({"odds": -110}, -110, 1.9091, "10/11"),
        ({"odds": "-200", "odds_format": "american"}, -200, 1.5, "1/2"),
        ({"odds": 3.5, "odds_format": "decimal"}, 250, 3.5, "5/2"),
        ({"odds": "5/2", "odds_format": "fractional"}, 250, 3.5, "5/2"),
        ({"odds": "10/4", "odds_format": "fractional"}, 250, 3.5, "5/2"),
    ],
)
def test_convert(
    client: TestClient, body: dict, american: int, decimal: float, fractional: str
) -> None:
    result = post(client, "convert", body)
    assert result["price"]["american"] == american
    assert result["price"]["decimal"] == decimal
    assert result["price"]["fractional"] == fractional
    assert result["price"]["implied_probability"] == pytest.approx(1 / decimal, abs=1e-4)
    assert len(result["steps"]) >= 3
    assert all(isinstance(step, str) and step for step in result["steps"])


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"odds": 50}, "invalid_american_odds"),
        ({"odds": -99}, "invalid_american_odds"),
        ({"odds": 150.5}, "invalid_american_odds"),
        ({"odds": 1, "odds_format": "decimal"}, "invalid_decimal_odds"),
        ({"odds": 0.5, "odds_format": "decimal"}, "invalid_decimal_odds"),
        ({"odds": "5/0", "odds_format": "fractional"}, "invalid_fractional_odds"),
        ({"odds": "abc"}, "invalid_quant_input"),
        ({"odds": 150, "odds_format": "roman"}, "validation_error"),
        ({}, "validation_error"),
    ],
)
def test_convert_validation(client: TestClient, body: dict, code: str) -> None:
    error = post(client, "convert", body, status=422)["error"]
    assert error["code"] == code
    assert error["message"]


def test_no_vig_minus_110_both_sides(client: TestClient) -> None:
    result = post(client, "no-vig", {"odds": [-110, -110], "labels": ["Over", "Under"]})
    assert [o["no_vig_probability"] for o in result["outcomes"]] == [0.5, 0.5]
    assert [o["label"] for o in result["outcomes"]] == ["Over", "Under"]
    assert result["overround"] == pytest.approx(0.0476, abs=1e-4)
    assert result["hold"] == pytest.approx(0.0455, abs=1e-4)
    assert result["outcomes"][0]["fair_price"]["american"] == 100
    assert result["method"] == "multiplicative"
    assert any("4.76%" in step for step in result["steps"])
    assert any("50.00%" in step for step in result["steps"])


def test_no_vig_three_way(client: TestClient) -> None:
    result = post(client, "no-vig", {"odds": [2.4, 3.3, 3.1], "odds_format": "decimal"})
    assert len(result["outcomes"]) == 3
    assert sum(o["no_vig_probability"] for o in result["outcomes"]) == pytest.approx(1.0, abs=1e-5)
    assert [o["label"] for o in result["outcomes"]] == ["Outcome 1", "Outcome 2", "Outcome 3"]
    assert all(o["no_vig_probability"] < o["implied_probability"] for o in result["outcomes"])


def test_no_vig_validation(client: TestClient) -> None:
    assert (
        post(client, "no-vig", {"odds": [-110]}, status=422)["error"]["code"] == "validation_error"
    )
    assert (
        post(client, "no-vig", {"odds": [-110, 20]}, status=422)["error"]["code"]
        == "invalid_american_odds"
    )


def test_ev_plus_150_at_45_percent(client: TestClient) -> None:
    result = post(client, "ev", {"odds": "+150", "win_probability": 0.45, "stake": 100})
    assert result["ev_per_unit"] == 0.125
    assert result["ev_percent"] == 12.5
    assert result["expected_profit"] == 12.5
    assert result["breakeven_probability"] == 0.4
    assert result["edge"] == 0.05
    assert any("+12.50%" in step for step in result["steps"])
    assert "does not estimate" in result["caveat"]
    default_stake = post(client, "ev", {"odds": 150, "win_probability": 0.45})
    assert default_stake["stake"] == 1.0


@pytest.mark.parametrize("p", [0, 1, 1.2, -0.1])
def test_ev_rejects_probability_outside_open_interval(client: TestClient, p: float) -> None:
    error = post(client, "ev", {"odds": 150, "win_probability": p}, status=422)["error"]
    assert error["code"] == "invalid_probability"


def test_ev_rejects_bad_stake(client: TestClient) -> None:
    error = post(client, "ev", {"odds": 150, "win_probability": 0.5, "stake": 0}, status=422)[
        "error"
    ]
    assert error["code"] == "validation_error"


def test_parlay_distinct_events(client: TestClient) -> None:
    result = post(
        client,
        "parlay",
        {
            "stake": 10,
            "legs": [
                {
                    "odds": 2.0,
                    "odds_format": "decimal",
                    "event_id": "a",
                    "win_probability": 0.5,
                    "label": "Tides ML",
                },
                {"odds": "+150", "event_id": "b", "win_probability": 0.4},
                {"odds": -110, "event_id": "c", "result": "push"},
            ],
        },
    )
    assert result["combined_decimal"] == 5.0
    assert result["combined_price"]["american"] == 400
    assert (result["active_legs"], result["dropped_legs"]) == (2, 1)
    assert (result["payout"], result["profit"]) == (50.0, 40.0)
    assert result["combined_probability"] == pytest.approx(0.2)
    assert "assumes independence" in result["probability_note"]
    assert result["correlation_warnings"] == []
    assert [leg["counted"] for leg in result["legs"]] == [True, True, False]
    assert result["legs"][0]["label"] == "Tides ML"
    assert any("dropped" in step for step in result["steps"])
    assert any("assumes independence" in step for step in result["steps"])


def test_parlay_same_event_has_null_probability_and_a_warning(client: TestClient) -> None:
    result = post(
        client,
        "parlay",
        {
            "legs": [
                {"odds": -110, "event_id": "game1", "win_probability": 0.5},
                {"odds": -110, "event_id": "game1", "win_probability": 0.5},
            ]
        },
    )
    assert result["combined_probability"] is None
    assert len(result["correlation_warnings"]) == 1
    assert "game1" in result["correlation_warnings"][0]
    assert result["combined_decimal"] == pytest.approx(3.6446, abs=1e-4)
    assert result["payout"] is None and result["stake"] is None


def test_parlay_without_event_ids_has_null_probability(client: TestClient) -> None:
    result = post(
        client,
        "parlay",
        {"legs": [{"odds": -110, "win_probability": 0.5}, {"odds": -110, "win_probability": 0.5}]},
    )
    assert result["combined_probability"] is None
    assert result["correlation_warnings"]


def test_parlay_with_every_leg_dropped(client: TestClient) -> None:
    result = post(client, "parlay", {"stake": 20, "legs": [{"odds": -110, "result": "void"}]})
    assert result["combined_price"] is None
    assert result["combined_decimal"] == 1.0
    assert result["payout"] == 20.0 and result["profit"] == 0.0


def test_parlay_validation(client: TestClient) -> None:
    assert post(client, "parlay", {"legs": []}, status=422)["error"]["code"] == "validation_error"
    error = post(
        client,
        "parlay",
        {"legs": [{"odds": 2, "odds_format": "decimal", "win_probability": 2}]},
        status=422,
    )
    assert error["error"]["code"] == "invalid_probability"
    error = post(client, "parlay", {"legs": [{"odds": -110, "result": "lost"}]}, status=422)
    assert error["error"]["code"] == "validation_error"


def test_clv_price_based(client: TestClient) -> None:
    result = post(client, "clv", {"odds": 2.1, "closing_odds": 2.0, "odds_format": "decimal"})
    assert result["clv"] == pytest.approx(0.05)
    assert result["clv_percent"] == pytest.approx(5.0)
    assert result["beat_close"] is True
    assert result["closing_no_vig_probability"] is None
    assert result["no_vig_probability_delta"] is None
    assert any("+5.00%" in step for step in result["steps"])


def test_clv_with_two_sided_close(client: TestClient) -> None:
    result = post(
        client, "clv", {"odds": "+110", "closing_odds": -110, "closing_opposite_odds": -110}
    )
    assert result["closing_no_vig_probability"] == 0.5
    assert result["no_vig_probability_delta"] == pytest.approx(0.5 - 1 / 2.1, abs=1e-6)
    assert result["ev_at_close_percent"] == pytest.approx(5.0)
    assert result["beat_close"] is True
    worse = post(client, "clv", {"odds": -120, "closing_odds": -110})
    assert worse["beat_close"] is False and worse["clv"] < 0


def test_clv_validation(client: TestClient) -> None:
    error = post(client, "clv", {"odds": 150, "closing_odds": 10}, status=422)["error"]
    assert error["code"] == "invalid_american_odds"
    assert post(client, "clv", {"odds": 150}, status=422)["error"]["code"] == "validation_error"
