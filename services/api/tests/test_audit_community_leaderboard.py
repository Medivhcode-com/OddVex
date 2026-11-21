"""Audit finding api-data#6: the leaderboard says what its order leaves out.

The order is unchanged (the Wilson lower bound of the win rate). Every row carries the
average price and the flat-stake return of the record, and the method text says that the
price is not part of the order and that a high win rate at short prices can still lose
money.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from oddvex_api.community import guidelines
from oddvex_api.quant import american_to_decimal

from .community_support import COMMUNITY_APP, enable, insert_graded_picks, member
from .conftest import AppFactory
from .fakes import ControlledProvider
from .test_notification_copy import BANNED_PHRASES


@pytest.fixture
def world() -> ControlledProvider:
    return ControlledProvider()


@pytest.fixture
def app(make_app: AppFactory, world: ControlledProvider) -> FastAPI:
    return make_app(provider=world, **COMMUNITY_APP)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def test_a_short_price_record_that_loses_money_can_rank_first_and_the_api_says_so(
    client: TestClient, world: ControlledProvider
) -> None:
    enable(client, leaderboard=True)
    viewer = member(client, "viewer_vee")
    member(client, "short_sid")
    member(client, "even_ella")
    now = world.current
    # 24 of 30 at -500: 80% wins, and a loss of 1.2 units.
    insert_graded_picks(client, "short_sid", "W" * 24 + "L" * 6, graded_at=now, price="1.2")
    # 114 of 200 at -110: 57% wins, and a profit.
    insert_graded_picks(client, "even_ella", "W" * 114 + "L" * 86, graded_at=now)

    board = client.get("/v1/community/leaderboard", headers=viewer).json()
    first, second = board["items"]
    assert (first["handle"], second["handle"]) == ("short_sid", "even_ella")  # order unchanged
    # Every row carries the price and the return of the record, computed by the API.
    assert first["record"]["average_price"]["american"] == -500
    assert first["record"]["average_price"]["decimal"] == float(american_to_decimal(-500))
    assert first["record"]["flat_stake_roi"] == -0.04
    assert first["record"]["units_profit"] == -1.2
    assert second["record"]["average_price"]["american"] == -110
    assert second["record"]["flat_stake_roi"] > 0

    method = board["method"]
    assert method == guidelines.LEADERBOARD_METHOD.format(minimum=30)
    assert "Wilson 95%" in method and "30 graded picks" in method
    assert "The price of a pick is not part of the order" in method
    assert "a high win rate at short prices can still lose money" in method
    assert "average price" in method and "flat-stake return" in method
    lowered = method.lower()
    for phrase in (*BANNED_PHRASES, "!"):
        assert phrase not in lowered, phrase
