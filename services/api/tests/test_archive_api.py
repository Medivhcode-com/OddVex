"""The snapshot archive routes: flag, sign-in, ownership, books and validation."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from oddvex_api.archive.capture import capture_pass

from .archive_support import (
    ARCHIVE_SETTINGS,
    PREGAME,
    T0,
    capture_schedule_on,
    enable_archive,
)
from .conftest import ADMIN_EMAIL, AppFactory, admin_headers, auth_headers
from .fakes import ControlledProvider

Headers = dict[str, str]


@pytest.fixture
def archived(make_app: AppFactory) -> Iterator[tuple[TestClient, FastAPI, ControlledProvider]]:
    """An app on a controlled provider with the flag on and four captures stored."""
    provider = ControlledProvider()
    app = make_app(provider=provider, admin_emails=ADMIN_EMAIL, **ARCHIVE_SETTINGS)
    with TestClient(app) as client:
        enable_archive(app.state.session_factory)
        capture_schedule_on(app.state.engine, provider, app.state.settings)
        provider.current = T0 + timedelta(hours=1)
        yield client, app, provider


def bet_body(sportsbook: str, outcome_key: str = "home", seconds: int = 100) -> dict[str, Any]:
    return {
        "bet_type": "straight",
        "stake": 10,
        "sportsbook": sportsbook,
        "placed_at": (T0 + timedelta(seconds=seconds)).isoformat(),
        "legs": [
            {
                "selection": f"{outcome_key} ML",
                "market": "moneyline",
                "event_id": PREGAME,
                "outcome_key": outcome_key,
                "odds": -120,
            }
        ],
    }


def place(client: TestClient, headers: Headers, body: dict[str, Any]) -> str:
    response = client.post("/v1/bets", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def test_placement_prices_route_returns_every_leg_and_hides_other_users_bets(
    archived: tuple[TestClient, FastAPI, ControlledProvider],
) -> None:
    client, app, _ = archived
    ada = auth_headers(client, "ada@example.test")
    bet_id = place(client, ada, bet_body("Summit"))
    place(client, ada, bet_body("Mystery Book", seconds=200))
    url = f"/v1/bets/{bet_id}/placement-prices"

    # 1. The books parameter. C0 home: cardinal -110 overall; northline -120 at
    # northline and summit (summit is -125).
    by_query = client.get(url, params={"books": "northline,summit"}, headers=ada)
    assert by_query.status_code == 200, by_query.text
    body = by_query.json()
    assert (body["books"], body["books_source"], body["data_mode"]) == (
        ["northline", "summit"],
        "query",
        "synthetic",
    )
    (leg,) = body["legs"]
    assert leg["status"] == "priced" and leg["reason"] is None
    assert leg["best_overall"]["sportsbook"]["key"] == "cardinal"
    assert leg["best_overall"]["price"]["american"] == -110
    assert leg["best_at_your_books"]["sportsbook"]["key"] == "northline"
    assert leg["best_at_your_books"]["price"]["american"] == -120
    assert leg["your_price"]["american"] == -120
    assert leg["coverage"]["status"] == "captured"

    # 2. Without the parameter: the books of Ada's own bets that the provider has
    # ("Summit" matches; "Mystery Book" matches nothing).
    inferred = client.get(url, headers=ada).json()
    assert (inferred["books"], inferred["books_source"]) == (["summit"], "bets")
    assert inferred["legs"][0]["best_at_your_books"]["price"]["american"] == -125

    # 3. A user whose bets are all at books the provider does not have: no books known.
    grace = auth_headers(client, "grace@example.test")
    unknown_id = place(client, grace, bet_body("Mystery Book"))
    unknown = client.get(f"/v1/bets/{unknown_id}/placement-prices", headers=grace).json()
    assert (unknown["books"], unknown["books_source"]) == ([], "none")
    (leg,) = unknown["legs"]
    assert leg["status"] == "cannot_price" and leg["your_books_reason"] == "books_unknown"
    assert leg["best_overall"]["price"]["american"] == -110 and leg["best_at_your_books"] is None

    # Another user's bet answers exactly like a missing one.
    other = client.get(url, headers=grace)
    missing = client.get("/v1/bets/" + "0" * 32 + "/placement-prices", headers=grace)
    assert other.status_code == missing.status_code == 404
    assert other.json()["error"]["code"] == missing.json()["error"]["code"] == "not_found"

    # Unknown or too many books.
    bad = client.get(url, params={"books": "northline,nowhere"}, headers=ada)
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "unknown_sportsbook"
    many = client.get(url, params={"books": ",".join(f"b{i}" for i in range(21))}, headers=ada)
    assert many.status_code == 422 and many.json()["error"]["code"] == "too_many_books"

    # Off: 404 feature_disabled, for the owner too.
    enable_archive(app.state.session_factory, False)
    off = client.get(url, headers=ada)
    assert off.status_code == 404 and off.json()["error"]["code"] == "feature_disabled"


def test_archive_routes_are_behind_the_flag_and_need_sign_in(
    archived: tuple[TestClient, FastAPI, ControlledProvider],
) -> None:
    client, app, _ = archived
    as_of = {"as_of": (T0 + timedelta(seconds=100)).isoformat()}
    paths = [
        (f"/v1/archive/events/{PREGAME}/odds", {**as_of, "market": "moneyline"}),
        ("/v1/archive/players/plr_nhl_x_1/props", as_of),
        (f"/v1/archive/events/{PREGAME}/status", as_of),
        ("/v1/bets/" + "0" * 32 + "/placement-prices", {}),
    ]
    for path, params in paths:
        response = client.get(path, params=params)
        assert response.status_code == 401, path
        assert response.json()["error"]["code"] == "not_authenticated"
    headers = auth_headers(client)
    enable_archive(app.state.session_factory, False)
    for path, params in paths:
        for extra in ({}, headers):
            response = client.get(path, params=params, headers=extra)
            assert response.status_code == 404, path
            assert response.json()["error"]["code"] == "feature_disabled", path


def test_as_of_needs_an_offset_and_cannot_be_in_the_future(
    archived: tuple[TestClient, FastAPI, ControlledProvider],
) -> None:
    client, _, provider = archived
    headers = auth_headers(client)
    url = f"/v1/archive/events/{PREGAME}/odds"
    naive = client.get(
        url, params={"market": "moneyline", "as_of": "2026-03-14T19:31:00"}, headers=headers
    )
    assert naive.status_code == 422 and naive.json()["error"]["code"] == "as_of_without_offset"
    future = (provider.now() + timedelta(seconds=61)).isoformat()
    ahead = client.get(url, params={"market": "moneyline", "as_of": future}, headers=headers)
    assert ahead.status_code == 422 and ahead.json()["error"]["code"] == "as_of_in_future"
    near = (provider.now() + timedelta(seconds=59)).isoformat()
    assert (
        client.get(url, params={"market": "moneyline", "as_of": near}, headers=headers).status_code
        == 200
    )
    bad_market = client.get(url, params={"market": "corners", "as_of": near}, headers=headers)
    assert bad_market.status_code == 422
    nobody = client.get("/v1/archive/players/nobody/props", params={"as_of": near}, headers=headers)
    assert nobody.status_code == 404 and nobody.json()["error"]["code"] == "not_found"


def test_admin_stats_show_the_archive_whatever_the_flag(
    archived: tuple[TestClient, FastAPI, ControlledProvider],
) -> None:
    client, app, _ = archived
    user = auth_headers(client)
    assert client.get("/v1/admin/archive/stats").status_code == 401
    forbidden = client.get("/v1/admin/archive/stats", headers=user)
    assert forbidden.status_code == 403
    admin = admin_headers(client)
    enable_archive(app.state.session_factory, False)
    stats = client.get("/v1/admin/archive/stats", headers=admin)
    assert stats.status_code == 200, stats.text
    body = stats.json()
    assert body["enabled"] is False
    assert body["max_bytes"] == 1_610_612_736
    assert (body["retention_days"], body["keep_days"]) == (7, 400)
    assert body["rows"]["odds"] > 0 and body["rows"]["events"] > 0 and body["rows"]["runs"] >= 8
    assert body["approx_bytes"] > 0
    assert {run["kind"] for run in body["last_runs"]} >= {"odds", "props", "prune"}
    audit = client.get("/v1/admin/audit", params={"action": "admin.read"}, headers=admin).json()
    assert any(row["entity_type"] == "archive_stats" for row in audit["items"])


def test_capture_with_the_flag_off_writes_nothing_through_the_app(make_app: AppFactory) -> None:
    provider = ControlledProvider()
    app = make_app(provider=provider, admin_emails=ADMIN_EMAIL)
    with TestClient(app) as client:
        assert client.get("/v1/flags").json()["flags"]["snapshot_archive"] is False
        report = capture_pass(app.state.engine, provider, app.state.settings, force=True)
        assert report.enabled is False and report.odds is None and report.prune is None
        admin = admin_headers(client)
        rows = client.get("/v1/admin/archive/stats", headers=admin).json()["rows"]
        assert rows == {"odds": 0, "props": 0, "events": 0, "status": 0, "runs": 0}
