"""The snapshot archive routes: flag, sign-in, ownership, books and validation."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from oddvex_api.archive import view as view_module
from oddvex_api.archive.capture import capture_pass, new_run

from .archive_support import (
    ARCHIVE_SETTINGS,
    PREGAME,
    T0,
    capture_schedule_on,
    enable_archive,
)
from .conftest import (
    ADMIN_EMAIL,
    EXTERNAL_DATABASE_URL,
    AppFactory,
    admin_headers,
    auth_headers,
)
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
    assert leg["reason"] == "books_unknown"  # always a named reason when not priced
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


def test_a_read_the_prune_keeps_disturbing_answers_503_and_never_a_guess(
    archived: tuple[TestClient, FastAPI, ControlledProvider], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read that a prune changes the rows under is made again; if that happens every
    time (for a read of one game it cannot in operation: one prune disturbs it three
    times at most; the placement prices of a parlay read several games), the three
    reading routes answer 503 ``archive_busy`` with ``Retry-After``, not an answer built
    from rows that were not there together."""
    client, _, provider = archived
    headers = auth_headers(client)
    bet_id = place(client, headers, bet_body("Summit"))
    player = provider.list_players()[0]
    as_of = (T0 + timedelta(seconds=100)).isoformat()
    urls: list[tuple[str, dict[str, str]]] = [
        (f"/v1/archive/events/{PREGAME}/odds", {"market": "moneyline", "as_of": as_of}),
        (f"/v1/archive/players/{player.id}/props", {"as_of": as_of}),
        (f"/v1/bets/{bet_id}/placement-prices", {}),
    ]
    for url, params in urls:
        assert client.get(url, params=params, headers=headers).status_code == 200
    readings = iter(range(10_000))
    monkeypatch.setattr(view_module, "prune_marker", lambda session: next(readings))
    for url, params in urls:
        busy = client.get(url, params=params, headers=headers)
        assert busy.status_code == 503, url
        assert busy.json()["error"]["code"] == "archive_busy"
        assert busy.headers["Retry-After"] == "5"
    # The status route reads its rows in one statement and is never refused.
    status = client.get(
        f"/v1/archive/events/{PREGAME}/status", params={"as_of": as_of}, headers=headers
    )
    assert status.status_code == 200


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
    # The ceiling on the files, and the files themselves where the database reports them.
    assert body["max_disk_bytes"] == 2_147_483_648
    if EXTERNAL_DATABASE_URL:
        assert 0 < body["disk_bytes"] < body["max_disk_bytes"]
    else:
        assert body["disk_bytes"] is None
    assert {run["kind"] for run in body["last_runs"]} >= {"odds", "props", "prune"}
    for run in body["last_runs"]:
        assert run["finished_at"] is not None
        assert run["error"] is None  # nothing failed
        if run["kind"] != "reclaim":
            assert run["indexes_rebuilt"] is None and run["bytes_freed"] is None
            assert run["failed_indexes"] is None
    # The status read says what it covers.
    status = client.get(
        f"/v1/archive/events/{PREGAME}/status",
        params={"as_of": (T0 + timedelta(seconds=400)).isoformat()},
        headers=admin,
    )
    assert status.status_code == 404  # the flag is off
    enable_archive(app.state.session_factory, True)
    status = client.get(
        f"/v1/archive/events/{PREGAME}/status",
        params={"as_of": (T0 + timedelta(seconds=400)).isoformat()},
        headers=admin,
    )
    assert status.status_code == 200, status.text
    coverage = status.json()["coverage"]
    assert (coverage["status"], coverage["captured_at"]) == ("not_captured", None)
    # Records are kept 400 days back from the newest prune.
    kept_from = datetime.fromisoformat(coverage["kept_from"])
    assert timedelta(days=399) < T0 - kept_from <= timedelta(days=400)
    assert status.json()["entries"] == []
    enable_archive(app.state.session_factory, False)
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


def test_a_suspended_account_is_refused_by_the_archive_routes_with_the_flag_on(
    archived: tuple[TestClient, FastAPI, ControlledProvider],
) -> None:
    client, _, provider = archived
    ada = auth_headers(client, "ada@example.test")
    bet_id = place(client, ada, bet_body("Summit"))
    player_id = provider.list_players()[0].id
    user_id = client.get("/v1/me", headers=ada).json()["id"]
    as_of = {"as_of": (T0 + timedelta(seconds=100)).isoformat()}
    urls = [
        (f"/v1/archive/events/{PREGAME}/odds", {**as_of, "market": "moneyline"}),
        (f"/v1/archive/players/{player_id}/props", as_of),
        (f"/v1/archive/events/{PREGAME}/status", as_of),
        (f"/v1/bets/{bet_id}/placement-prices", {}),
    ]
    for url, params in urls:
        assert client.get(url, params=params, headers=ada).status_code == 200, url
    admin = admin_headers(client)
    suspended = client.post(
        f"/v1/admin/users/{user_id}/suspend", json={"reason": "review"}, headers=admin
    )
    assert suspended.status_code == 200, suspended.text
    for url, params in urls:
        response = client.get(url, params=params, headers=ada)
        assert response.status_code == 401, url
        assert response.json()["error"]["code"] == "account_suspended", url


def test_admin_stats_name_what_failed(
    archived: tuple[TestClient, FastAPI, ControlledProvider],
) -> None:
    """Review round 5, operations: nobody has a shell on the preview server, so the
    statistics are the only place an operator can see why a run failed. A failed capture
    or prune shows the class name of its error, and a failed index rebuild the index and
    the class of its error (``QueryCanceled`` is the one that says "raise the rebuild's
    time limit"). Names only, as the runs record them."""
    client, app, provider = archived
    settings = app.state.settings
    with app.state.session_factory() as db:
        failed = new_run(provider, settings, "odds", provider.now(), status="failed")
        failed.detail = {"error": "ConnectionError"}
        reclaim = new_run(provider, settings, "reclaim", provider.now(), status="failed")
        reclaim.detail = {
            "rebuilt": {"ix_odds_snapshots_captured_at": [3_000_000, 2_000_000, 50_000]},
            "dropped": {},
            "failed": {"uq_odds_snapshots_key": "QueryCanceled"},
            "skipped": ["uq_prop_snapshots_key"],
            "freed_bytes": 1_000_000,
            "over_ceiling": False,
        }
        db.add_all([failed, reclaim])
        db.commit()
    stats = client.get("/v1/admin/archive/stats", headers=admin_headers(client))
    assert stats.status_code == 200, stats.text
    runs = {run["kind"]: run for run in stats.json()["last_runs"]}
    assert (runs["odds"]["status"], runs["odds"]["error"]) == ("failed", "ConnectionError")
    assert runs["odds"]["failed_indexes"] is None
    assert runs["reclaim"]["status"] == "failed" and runs["reclaim"]["error"] is None
    assert runs["reclaim"]["failed_indexes"] == {"uq_odds_snapshots_key": "QueryCanceled"}
    assert (runs["reclaim"]["indexes_failed"], runs["reclaim"]["indexes_rebuilt"]) == (1, 1)
    assert runs["props"]["error"] is None  # the latest props run did not fail
