"""Watchlist: owner-scoped favourites resolved against the data provider."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from oddvex_api.db import AuditLog, WatchlistItem
from oddvex_api.providers import SyntheticProvider

from .conftest import FROZEN_NOW, AppFactory, auth_headers
from .test_platform import assert_envelope

Headers = dict[str, str]


def add(
    client: TestClient, headers: Headers, kind: str, ref_id: str, status: int = 201
) -> dict[str, Any]:
    response = client.post("/v1/watchlist", json={"kind": kind, "ref_id": ref_id}, headers=headers)
    assert response.status_code == status, response.text
    return response.json()


def events(client: TestClient, status: str) -> list[dict[str, Any]]:
    return client.get("/v1/events", params={"status": status}).json()


def player(client: TestClient, league: str = "nba") -> dict[str, Any]:
    return client.get("/v1/players", params={"league": league}).json()[0]


# ------------------------------------------------------------------ add / list
def test_add_and_list_team_player_and_event(client: TestClient, headers: Headers) -> None:
    event = events(client, "upcoming")[0]
    team = event["home_team"]
    plr = player(client)

    team_item = add(client, headers, "team", team["id"])
    assert set(team_item) == {
        "id",
        "kind",
        "ref_id",
        "label",
        "league",
        "created_at",
        "available",
        "team",
        "player",
        "event",
    }
    assert team_item["kind"] == "team" and team_item["ref_id"] == team["id"]
    assert team_item["label"] == team["name"] and team_item["league"] == event["league"]
    assert team_item["available"] is True
    assert team_item["team"] == team
    assert team_item["player"] is None and team_item["event"] is None

    player_item = add(client, headers, "player", plr["id"])
    assert player_item["label"] == plr["name"] and player_item["league"] == "nba"
    assert player_item["player"] == plr and player_item["team"] is None

    event_item = add(client, headers, "event", event["id"])
    assert event_item["label"] == f"{event['away_team']['name']} at {event['home_team']['name']}"
    assert event_item["event"]["id"] == event["id"]
    assert event_item["event"]["home_team"] == team

    listing = client.get("/v1/watchlist", headers=headers)
    assert listing.status_code == 200
    assert listing.headers["cache-control"] == "no-store"
    body = listing.json()
    assert set(body) == {"items"}
    assert {item["id"] for item in body["items"]} == {
        team_item["id"],
        player_item["id"],
        event_item["id"],
    }

    only_players = client.get("/v1/watchlist", params={"kind": "player"}, headers=headers).json()
    assert [item["id"] for item in only_players["items"]] == [player_item["id"]]
    assert client.get("/v1/watchlist", params={"kind": "event"}, headers=headers).json()[
        "items"
    ] == [event_item]


def test_list_is_newest_first_and_empty_by_default(client: TestClient, headers: Headers) -> None:
    assert client.get("/v1/watchlist", headers=headers).json() == {"items": []}
    teams = [e["home_team"]["id"] for e in events(client, "upcoming")[:3]]
    ids = [add(client, headers, "team", team_id)["id"] for team_id in dict.fromkeys(teams)]
    listed = [item["id"] for item in client.get("/v1/watchlist", headers=headers).json()["items"]]
    assert sorted(listed) == sorted(ids) and len(listed) == len(ids)
    created = [
        item["created_at"] for item in client.get("/v1/watchlist", headers=headers).json()["items"]
    ]
    assert created == sorted(created, reverse=True)


def test_adding_twice_is_idempotent(client: TestClient, headers: Headers, app) -> None:  # type: ignore[no-untyped-def]
    team_id = events(client, "upcoming")[0]["home_team"]["id"]
    first = add(client, headers, "team", team_id, status=201)
    again = add(client, headers, "team", team_id, status=200)
    assert again == first
    assert len(client.get("/v1/watchlist", headers=headers).json()["items"]) == 1
    # The same id under another kind is a different item.
    with app.state.session_factory() as db:
        assert len(list(db.scalars(select(WatchlistItem)))) == 1
        actions = [row.action for row in db.scalars(select(AuditLog)) if "watchlist" in row.action]
    assert actions == ["watchlist.add"]


def test_unknown_reference_is_404(client: TestClient, headers: Headers) -> None:
    for kind, ref_id in (
        ("team", "team_nba_zzz"),
        ("player", "plr_nba_zzz_1"),
        ("event", "evt_nba_19990101_0"),
        ("event", "nonsense"),
    ):
        response = client.post(
            "/v1/watchlist", json={"kind": kind, "ref_id": ref_id}, headers=headers
        )
        assert response.status_code == 404, (kind, response.text)
        assert_envelope(response.json(), "not_found")
    # A real team id is not a player id.
    team_id = events(client, "upcoming")[0]["home_team"]["id"]
    assert (
        client.post(
            "/v1/watchlist", json={"kind": "player", "ref_id": team_id}, headers=headers
        ).status_code
        == 404
    )
    assert client.get("/v1/watchlist", headers=headers).json() == {"items": []}


def test_validation_errors_use_the_envelope(client: TestClient, headers: Headers) -> None:
    for body in (
        {"kind": "league", "ref_id": "nba"},
        {"kind": "team"},
        {"kind": "team", "ref_id": ""},
        {"kind": "team", "ref_id": "x" * 65},
    ):
        response = client.post("/v1/watchlist", json=body, headers=headers)
        assert response.status_code == 422, body
        assert_envelope(response.json(), "validation_error")
    bad_kind = client.get("/v1/watchlist", params={"kind": "league"}, headers=headers)
    assert bad_kind.status_code == 422
    assert_envelope(bad_kind.json(), "validation_error")


def test_watchlist_is_capped_at_200_items(client: TestClient, headers: Headers) -> None:
    refs = [("player", p["id"]) for p in client.get("/v1/players").json()]
    refs += [("event", e["id"]) for e in client.get("/v1/events").json()]
    assert len(refs) > 200
    for kind, ref_id in refs[:200]:
        add(client, headers, kind, ref_id)
    extra_kind, extra_id = refs[200]
    full = client.post(
        "/v1/watchlist", json={"kind": extra_kind, "ref_id": extra_id}, headers=headers
    )
    assert full.status_code == 409
    assert_envelope(full.json(), "watchlist_full")
    assert full.json()["error"]["details"] == {"max_items": 200}
    # Re-adding an existing item is still fine, and removing one frees a slot.
    existing = add(client, headers, *refs[0], status=200)
    assert client.delete(f"/v1/watchlist/{existing['id']}", headers=headers).status_code == 204
    add(client, headers, extra_kind, extra_id, status=201)
    assert len(client.get("/v1/watchlist", headers=headers).json()["items"]) == 200


# --------------------------------------------------------------------- remove
def test_remove(client: TestClient, headers: Headers, app) -> None:  # type: ignore[no-untyped-def]
    item = add(client, headers, "team", events(client, "upcoming")[0]["home_team"]["id"])
    response = client.delete(f"/v1/watchlist/{item['id']}", headers=headers)
    assert response.status_code == 204 and response.content == b""
    assert client.get("/v1/watchlist", headers=headers).json() == {"items": []}
    gone = client.delete(f"/v1/watchlist/{item['id']}", headers=headers)
    assert gone.status_code == 404
    assert_envelope(gone.json(), "not_found")
    with app.state.session_factory() as db:
        rows = [row for row in db.scalars(select(AuditLog)) if row.action == "watchlist.remove"]
    assert len(rows) == 1 and rows[0].entity_id == item["id"]
    assert rows[0].details == {"kind": "team", "ref_id": item["ref_id"]}


# ---------------------------------------------------------------------- authz
def test_requires_authentication(client: TestClient) -> None:
    for response in (
        client.get("/v1/watchlist"),
        client.get("/v1/watchlist/events"),
        client.post("/v1/watchlist", json={"kind": "team", "ref_id": "team_nba_hct"}),
        client.delete("/v1/watchlist/abc"),
    ):
        assert response.status_code == 401
        assert_envelope(response.json(), "not_authenticated")


def test_users_cannot_see_or_remove_each_others_items(
    client: TestClient, headers: Headers, other_headers: Headers
) -> None:
    team_id = events(client, "upcoming")[0]["home_team"]["id"]
    mine = add(client, headers, "team", team_id)
    assert client.get("/v1/watchlist", headers=other_headers).json() == {"items": []}
    assert client.get("/v1/watchlist/events", headers=other_headers).json() == []
    stolen = client.delete(f"/v1/watchlist/{mine['id']}", headers=other_headers)
    assert stolen.status_code == 404
    assert_envelope(stolen.json(), "not_found")
    # The other user can watch the same team: a separate item, not the first user's.
    theirs = add(client, other_headers, "team", team_id, status=201)
    assert theirs["id"] != mine["id"]
    assert [i["id"] for i in client.get("/v1/watchlist", headers=headers).json()["items"]] == [
        mine["id"]
    ]


def test_deleting_the_account_deletes_the_watchlist(
    client: TestClient, headers: Headers, other_headers: Headers, app
) -> None:  # type: ignore[no-untyped-def]
    team_id = events(client, "upcoming")[0]["home_team"]["id"]
    add(client, headers, "team", team_id)
    kept = add(client, other_headers, "team", team_id)
    assert client.delete("/v1/me", headers=headers).status_code == 204
    with app.state.session_factory() as db:
        assert [item.id for item in db.scalars(select(WatchlistItem))] == [kept["id"]]


# ------------------------------------------------------------- watched events
def test_watchlist_events_for_team_player_and_event(client: TestClient, headers: Headers) -> None:
    assert client.get("/v1/watchlist/events", headers=headers).json() == []
    live = events(client, "live")
    upcoming = events(client, "upcoming")
    assert live and upcoming
    team_id = live[0]["home_team"]["id"]
    add(client, headers, "team", team_id)

    watched = client.get("/v1/watchlist/events", headers=headers).json()
    assert watched and all(e["status"] in ("live", "upcoming") for e in watched)
    assert all(team_id in (e["home_team"]["id"], e["away_team"]["id"]) for e in watched)
    assert watched[0]["id"] == live[0]["id"]
    expected = [
        e["id"]
        for e in client.get("/v1/events").json()
        if e["status"] != "final" and team_id in (e["home_team"]["id"], e["away_team"]["id"])
    ]
    assert sorted(e["id"] for e in watched) == sorted(expected)

    # A player on that same team adds nothing new; the directly watched live event is
    # already there too. No duplicates.
    teammate = next(p for p in client.get("/v1/players").json() if p["team"]["id"] == team_id)
    add(client, headers, "player", teammate["id"])
    add(client, headers, "event", live[0]["id"])
    again = client.get("/v1/watchlist/events", headers=headers).json()
    assert [e["id"] for e in again] == [e["id"] for e in watched]
    assert len({e["id"] for e in again}) == len(again)

    # An unrelated upcoming event watched directly is added.
    other = next(
        e
        for e in upcoming
        if team_id not in (e["home_team"]["id"], e["away_team"]["id"])
        and e["id"] not in {w["id"] for w in watched}
    )
    add(client, headers, "event", other["id"])
    final = client.get("/v1/watchlist/events", headers=headers).json()
    assert other["id"] in {e["id"] for e in final} and len(final) == len(watched) + 1

    # Live first, then by start time.
    statuses = [e["status"] for e in final]
    assert statuses == sorted(statuses, key=lambda s: s != "live")
    for status in ("live", "upcoming"):
        starts = [e["start_time"] for e in final if e["status"] == status]
        assert starts == sorted(starts)


def test_watchlist_events_follow_a_watched_players_team(
    client: TestClient, headers: Headers
) -> None:
    plr = player(client, "nfl")
    add(client, headers, "player", plr["id"])
    watched = client.get("/v1/watchlist/events", headers=headers).json()
    assert watched
    team_id = plr["team"]["id"]
    assert all(team_id in (e["home_team"]["id"], e["away_team"]["id"]) for e in watched)


def test_a_watched_final_event_is_listed_but_not_in_watched_events(
    client: TestClient, headers: Headers
) -> None:
    final = events(client, "final")[0]
    item = add(client, headers, "event", final["id"])
    assert item["event"]["status"] == "final" and item["event"]["score"] is not None
    assert client.get("/v1/watchlist/events", headers=headers).json() == []


def test_item_is_unavailable_once_the_provider_drops_the_event(make_app: AppFactory) -> None:
    clock = {"now": FROZEN_NOW}
    provider = SyntheticProvider(seed=20260101, clock=lambda: clock["now"])
    with TestClient(make_app(provider=provider)) as client:
        headers = auth_headers(client)
        event = events(client, "upcoming")[0]
        item = add(client, headers, "event", event["id"])
        team = add(client, headers, "team", event["home_team"]["id"])
        assert item["available"] is True

        clock["now"] = FROZEN_NOW + timedelta(days=500)  # far outside the provider's range
        assert client.get(f"/v1/events/{event['id']}").status_code == 404
        listed = {i["id"]: i for i in client.get("/v1/watchlist", headers=headers).json()["items"]}
        stale = listed[item["id"]]
        assert stale["available"] is False
        assert stale["event"] is None and stale["team"] is None and stale["player"] is None
        assert stale["label"] == item["label"] and stale["ref_id"] == event["id"]
        assert listed[team["id"]]["available"] is True  # teams do not expire
        # The stale event contributes nothing; the watched team still has games.
        watched = client.get("/v1/watchlist/events", headers=headers).json()
        assert watched and event["id"] not in {e["id"] for e in watched}
        # It can still be removed.
        assert client.delete(f"/v1/watchlist/{item['id']}", headers=headers).status_code == 204
