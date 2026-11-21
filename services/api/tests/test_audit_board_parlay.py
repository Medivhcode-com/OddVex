"""The parlay response says why a combined probability is or is not there (audit web-product#5).

Clients used to print ``probability_note`` verbatim, including "a win probability is
required for every leg", which no form can act on. ``probability_status`` is a fixed set
of values a client can map to its own sentence, and the worked steps no longer end with
a combined-probability line when no combined probability was computed.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from oddvex_api.quant import ParlayLeg, combine_parlay
from oddvex_api.quant.parlay import PROBABILITY_STATUSES

STATUSES = {
    "computed",
    "needs_leg_probabilities",
    "same_event_legs",
    "unverified_legs",
    "no_active_legs",
}


def leg(
    event_id: str | None = None, probability: float | None = None, result: str = "pending"
) -> ParlayLeg:
    return ParlayLeg(Decimal("1.9091"), event_id, probability, result)


def body(event_id: str | None = None, probability: float | None = None, **extra: Any) -> dict:
    payload: dict[str, Any] = {"odds": -110, **extra}
    if event_id is not None:
        payload["event_id"] = event_id
    if probability is not None:
        payload["win_probability"] = probability
    return payload


def parlay(client: TestClient, legs: list[dict], **extra: Any) -> dict:
    response = client.post("/v1/quant/parlay", json={"legs": legs, **extra})
    assert response.status_code == 200, response.text
    return response.json()


def test_the_set_of_statuses_is_fixed() -> None:
    assert set(PROBABILITY_STATUSES) == STATUSES
    assert len(PROBABILITY_STATUSES) == 5


# ------------------------------------------------------------------ the maths
@pytest.mark.parametrize(
    ("legs", "status", "computed"),
    [
        ([leg("a", 0.5), leg("b", 0.4)], "computed", True),
        ([leg(None, 0.5)], "computed", True),  # one leg: nothing to be correlated with
        ([leg("a"), leg("b")], "needs_leg_probabilities", False),
        ([leg("a", 0.5), leg("b")], "needs_leg_probabilities", False),
        ([leg(None)], "needs_leg_probabilities", False),
        ([leg("a", 0.5), leg("a", 0.5)], "same_event_legs", False),
        ([leg("a"), leg("a"), leg("b")], "same_event_legs", False),
        ([leg(None, 0.5), leg("b", 0.5)], "unverified_legs", False),
        ([leg(None), leg(None)], "unverified_legs", False),
        ([leg("a", result="void"), leg("b", result="push")], "no_active_legs", False),
        # A dropped leg does not count: the one active leg stands alone.
        ([leg("a", 0.5), leg("a", 0.5, "push")], "computed", True),
    ],
)
def test_status_of_each_case(legs: list[ParlayLeg], status: str, computed: bool) -> None:
    result = combine_parlay(legs)
    assert result.probability_status == status
    assert (result.combined_probability is not None) is computed
    assert (status == "computed") is computed


def test_precedence_when_several_reasons_apply() -> None:
    # Same event, an unknown event and a missing probability at once.
    mixed = combine_parlay([leg("a", 0.5), leg("a"), leg(None)])
    assert mixed.probability_status == "same_event_legs"
    assert len(mixed.correlation_warnings) == 2
    # An unknown event and a missing probability.
    assert combine_parlay([leg(None), leg("b", 0.5)]).probability_status == "unverified_legs"
    # Nothing active wins over everything.
    dropped = combine_parlay([leg("a", result="void"), leg("a", result="void")])
    assert dropped.probability_status == "no_active_legs"


def test_the_note_and_warnings_are_unchanged() -> None:
    assert combine_parlay([leg("a"), leg("b")]).probability_note == (
        "not computed: a win probability is required for every leg"
    )
    same = combine_parlay([leg("a", 0.5), leg("a", 0.5)])
    assert same.probability_note == "not computed: legs may be correlated"
    assert "correlated" in same.correlation_warnings[0]
    unknown = combine_parlay([leg(None, 0.5), leg("b", 0.5)])
    assert unknown.probability_note == "not computed: legs may be correlated"
    assert "no event_id" in unknown.correlation_warnings[0]
    assert combine_parlay([leg("a", result="void")]).probability_note == "no active legs remain"
    assert "assumes independence" in combine_parlay([leg("a", 0.5)]).probability_note


# -------------------------------------------------------------------- the API
def test_two_board_legs_from_different_games(client: TestClient) -> None:
    """What the web and mobile parlay tools send: prices and event ids, no probabilities."""
    result = parlay(client, [body("evt_1"), body("evt_2")], stake=10)
    assert result["probability_status"] == "needs_leg_probabilities"
    assert result["combined_probability"] is None
    assert result["correlation_warnings"] == []
    assert result["probability_note"] == "not computed: a win probability is required for every leg"
    # The working shows the price and the payout and stops there.
    assert not any("probability" in step.lower() for step in result["steps"])
    assert result["steps"][-1].startswith("Payout = 10.00 x ")
    assert result["payout"] == pytest.approx(36.45, abs=0.01)


def test_computed_case_keeps_its_working(client: TestClient) -> None:
    result = parlay(client, [body("evt_1", 0.5), body("evt_2", 0.4)])
    assert result["probability_status"] == "computed"
    assert result["combined_probability"] == pytest.approx(0.2)
    assert result["steps"][-1] == (
        "Combined probability = 0.5000 x 0.4000 = 20.00% (assumes independence)"
    )


@pytest.mark.parametrize(
    ("legs", "status"),
    [
        ([body("evt_1", 0.5), body("evt_1", 0.5)], "same_event_legs"),
        ([body(None, 0.5), body("evt_2", 0.5)], "unverified_legs"),
        ([body(None), body(None)], "unverified_legs"),
        ([body("evt_1", result="void")], "no_active_legs"),
        ([body("evt_1", 0.5), body("evt_1"), body(None)], "same_event_legs"),
    ],
)
def test_no_combined_probability_line_without_a_combined_probability(
    client: TestClient, legs: list[dict], status: str
) -> None:
    result = parlay(client, legs)
    assert result["probability_status"] == status
    assert result["combined_probability"] is None
    assert not any(step.startswith("Combined probability") for step in result["steps"])
    assert result["steps"][-1].startswith("Combined decimal = ")
    assert result["probability_note"]  # still there for older clients


def test_the_schema_describes_the_field(client: TestClient) -> None:
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    response = schemas["ParlayResponse"]
    assert "probability_status" in response["required"]
    field = response["properties"]["probability_status"]
    assert set(field["enum"]) == STATUSES
    assert field["type"] == "string"
    for status in STATUSES:
        assert f"`{status}`" in field["description"], status
    assert "precedence" in field["description"].lower()
    # One active leg without an event id is `computed`; the description must say so.
    assert "single active leg" in field["description"]
    assert "probability_status" in response["properties"]["probability_note"]["description"]
    steps = response["properties"]["steps"]["description"]
    assert "combined probability" in steps.lower()
