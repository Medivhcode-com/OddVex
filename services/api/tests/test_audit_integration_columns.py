"""Price and money values outside the bet tracker are checked against their columns before
anything is written (api-data#4), as ``bets/storage.py`` does for bets.

* An alert threshold is stored as ``Numeric(16, 6)``: one that would be stored as
  1.000000 or less, or is longer than the column, is a 422 and no rule is saved.
* A community pick snapshots the provider's best price into the same kind of column:
  a price the column cannot hold is a 422 and no pick is saved.
* The weekly staking-reminder threshold is stored in cents: one that would be stored as
  0.00 is a 422, like a stake.

PostgreSQL refuses a value longer than its column with an error of its own (a 500 before
these checks); SQLite stores it. Run with ``ODDVEX_TEST_DATABASE_URL`` pointing at a
throwaway PostgreSQL database to check the boundary there too.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from oddvex_api.db import AlertRule, CommunityPick, StakeReminder

from .community_support import COMMUNITY_APP, enable, fresh, member, upcoming
from .conftest import AppFactory, auth_headers
from .fakes import ControlledProvider, moneyline
from .test_platform import assert_envelope

Headers = dict[str, str]

MAX_STORED = "9999999999.999999"


@pytest.fixture
def world() -> ControlledProvider:
    return ControlledProvider()


@pytest.fixture
def app(make_app: AppFactory, world: ControlledProvider) -> FastAPI:
    return make_app(provider=world, alert_eval_min_seconds=0, **COMMUNITY_APP)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def count(client: TestClient, model: type) -> int:
    with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
        return int(db.scalar(select(func.count()).select_from(model)) or 0)


def assert_stored(client: TestClient, value: Any, expected: Decimal) -> None:
    """PostgreSQL returns the column's exact value; SQLite keeps a number as a float."""
    if client.app.state.engine.dialect.name == "postgresql":  # type: ignore[attr-defined]
        assert value == expected
    else:
        assert float(value) == pytest.approx(float(expected), abs=1e-5)


# ------------------------------------------------------------------- alerts
def price_alert(world: ControlledProvider, threshold: Any, odds_format: str) -> dict[str, Any]:
    return {
        "kind": "price_at_least",
        "event_id": upcoming(world).id,
        "market": "moneyline",
        "outcome_key": "home",
        "threshold": threshold,
        "odds_format": odds_format,
    }


@pytest.mark.parametrize(
    ("threshold", "odds_format", "code"),
    [
        ("10000000000", "decimal", "odds_out_of_range"),
        ("9999999999.9999995", "decimal", "odds_out_of_range"),  # rounds up past the column
        ("1e30", "decimal", "odds_out_of_range"),
        ("1e9999999", "decimal", "odds_out_of_range"),
        (999999999900, "american", "odds_out_of_range"),
        ("1.0000004", "decimal", "invalid_decimal_odds"),  # would be stored as 1.000000
        (-1000000000, "american", "invalid_decimal_odds"),
        ("1/3000000", "fractional", "invalid_decimal_odds"),
    ],
)
def test_an_alert_threshold_the_column_cannot_hold_is_422_and_nothing_is_saved(
    client: TestClient, world: ControlledProvider, threshold: Any, odds_format: str, code: str
) -> None:
    headers = auth_headers(client)
    response = client.post(
        "/v1/alerts", json=price_alert(world, threshold, odds_format), headers=headers
    )
    assert response.status_code == 422, response.text
    assert_envelope(response.json(), code)
    assert count(client, AlertRule) == 0
    # The list still loads.
    assert client.get("/v1/alerts", headers=headers).status_code == 200


@pytest.mark.parametrize(
    ("threshold", "stored"),
    [
        (MAX_STORED, Decimal(MAX_STORED)),
        ("1.000001", Decimal("1.000001")),
        ("1.0000005", Decimal("1.000001")),  # rounded half up, as a bet price is
    ],
)
def test_an_alert_threshold_at_the_boundary_is_saved_and_reads_back(
    client: TestClient, world: ControlledProvider, threshold: str, stored: Decimal
) -> None:
    headers = auth_headers(client)
    response = client.post(
        "/v1/alerts", json=price_alert(world, threshold, "decimal"), headers=headers
    )
    assert response.status_code == 201, response.text
    with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
        assert_stored(client, db.scalar(select(AlertRule.threshold_decimal)), stored)
    listed = client.get("/v1/alerts", headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()["items"][0]["threshold"]["decimal"] == round(float(stored), 4)


# ------------------------------------------------------------ community picks
@pytest.mark.parametrize(
    ("american", "code"),
    [
        (999999999900, "odds_out_of_range"),  # decimal 10000000000
        (-1000000000, "invalid_decimal_odds"),  # decimal 1.0000001, stored as 1.000000
    ],
)
def test_a_pick_price_the_column_cannot_hold_is_422_and_nothing_is_saved(
    client: TestClient, world: ControlledProvider, american: int, code: str
) -> None:
    enable(client)
    sam = member(client, "sample_sam")
    event = upcoming(world)
    world.set_odds(event.id, "moneyline", [fresh("northline", moneyline(american, -110))])
    response = client.post(
        "/v1/community/picks",
        json={"event_id": event.id, "market": "moneyline", "outcome_key": "home"},
        headers=sam,
    )
    assert response.status_code == 422, response.text
    assert_envelope(response.json(), code)
    assert count(client, CommunityPick) == 0
    assert client.get("/v1/community/picks", headers=sam).status_code == 200


def test_a_pick_price_at_the_boundary_is_saved_and_reads_back(
    client: TestClient, world: ControlledProvider
) -> None:
    enable(client)
    sam = member(client, "sample_sam")
    event = upcoming(world)
    # +999999999899 is decimal 9999999999.99, inside the column.
    world.set_odds(event.id, "moneyline", [fresh("northline", moneyline(999999999899, -110))])
    response = client.post(
        "/v1/community/picks",
        json={"event_id": event.id, "market": "moneyline", "outcome_key": "home"},
        headers=sam,
    )
    assert response.status_code == 201, response.text
    with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
        assert_stored(
            client, db.scalar(select(CommunityPick.price_decimal)), Decimal("9999999999.99")
        )
    pick = client.get(f"/v1/community/picks/{response.json()['id']}", headers=sam)
    assert pick.status_code == 200 and pick.json()["price"]["american"] == 999999999899


# --------------------------------------------------- weekly staking reminder
@pytest.mark.parametrize("threshold", [0.001, 0.004, 0.0049])
def test_a_reminder_threshold_stored_as_zero_is_422_like_a_stake(
    client: TestClient, threshold: float
) -> None:
    headers = auth_headers(client)
    response = client.put(
        "/v1/me/stake-reminder", json={"weekly_stake_threshold": threshold}, headers=headers
    )
    assert response.status_code == 422, response.text
    assert_envelope(response.json(), "invalid_threshold")
    assert response.json()["error"]["details"] == {"min_weekly_stake_threshold": "0.01"}
    assert count(client, StakeReminder) == 0
    reminder = client.get("/v1/me/stake-reminder", headers=headers).json()
    assert reminder["weekly_stake_threshold"] is None and reminder["exceeded"] is False


def test_a_reminder_threshold_of_a_cent_or_more_is_saved_in_cents(client: TestClient) -> None:
    headers = auth_headers(client)
    for sent, kept in ((0.005, 0.01), (0.01, 0.01), (1_000_000, 1_000_000.0), (12.345, 12.35)):
        response = client.put(
            "/v1/me/stake-reminder", json={"weekly_stake_threshold": sent}, headers=headers
        )
        assert response.status_code == 200, response.text
        assert response.json()["weekly_stake_threshold"] == kept
        # Nothing staked this week: a threshold above zero is not reached.
        assert response.json()["exceeded"] is False
    # An existing threshold is left as it was by a refused update.
    refused = client.put(
        "/v1/me/stake-reminder", json={"weekly_stake_threshold": 0.001}, headers=headers
    )
    assert refused.status_code == 422
    assert (
        client.get("/v1/me/stake-reminder", headers=headers).json()["weekly_stake_threshold"]
        == 12.35
    )
