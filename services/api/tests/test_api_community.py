"""Community: profiles, picks, grading, records, follows, feed, comments, likes, blocks,
reports, rate limits, notifications and the account lifecycle.

Moderation is in ``test_api_community_moderation.py``; the content rules themselves in
``test_community_content_rules.py``; the record math in ``quant/test_record.py``."""

from __future__ import annotations

import importlib.util
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from oddvex_api.community import guidelines, service
from oddvex_api.db import (
    CommunityBlock,
    CommunityComment,
    CommunityFollow,
    CommunityLike,
    CommunityPick,
    CommunityProfile,
    CommunityReport,
    Notification,
)
from oddvex_api.quant import american_to_decimal, grade_leg, wilson_interval
from oddvex_api.quant.record import FLAT_STAKE_METHOD

from .community_support import (
    COMMUNITY_APP,
    Headers,
    audit_actions,
    audit_rows,
    code,
    enable,
    feed,
    finish,
    fresh,
    insert_graded_picks,
    member,
    post_pick,
    priced,
    upcoming,
    user_id,
)
from .conftest import FROZEN_NOW, AppFactory, SettingsFactory, auth_headers, set_flag
from .fakes import ControlledProvider, moneyline
from .test_notification_copy import BANNED_PHRASES

API_ROOT = Path(__file__).resolve().parents[1]
PROFILE = "/v1/community/profile"
PICKS = "/v1/community/picks"


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


@pytest.fixture
def admin(client: TestClient) -> Headers:
    return enable(client)


@pytest.fixture
def sam(client: TestClient, admin: Headers) -> Headers:
    return member(client, "sample_sam")


@pytest.fixture
def mara(client: TestClient, admin: Headers) -> Headers:
    return member(client, "madeup_mara")


def count(client: TestClient, model: type) -> int:
    with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
        return int(db.scalar(select(func.count()).select_from(model)) or 0)


def notifications(client: TestClient, headers: Headers, kind: str) -> list[dict[str, Any]]:
    items = client.get("/v1/notifications", headers=headers).json()["items"]
    return [item for item in items if item["kind"] == kind]


# ------------------------------------------------------------------- the flag
def community_calls(client: TestClient) -> list[tuple[str, str]]:
    schema = client.get("/openapi.json").json()
    return [
        (method.upper(), path.replace("{", "").replace("}", ""))
        for path, item in schema["paths"].items()
        if path.startswith(("/v1/community", "/v1/admin/community"))
        for method in item
    ]


def test_every_route_is_404_feature_disabled_while_the_flag_is_off(client: TestClient) -> None:
    assert client.get("/v1/flags").json()["flags"]["community"] is False
    headers = auth_headers(client)
    calls = community_calls(client)
    assert len(calls) == 26
    for method, path in calls:
        for who in ({}, headers):
            response = client.request(method, path, json={}, headers=who)
            assert response.status_code == 404, (method, path)
            assert response.json()["error"] == {
                "code": "feature_disabled",
                "message": "This feature is not available",
                "details": {"flag": "community"},
            }
    for model in (CommunityProfile, CommunityPick, CommunityReport):
        assert count(client, model) == 0


def test_turning_the_flag_off_again_closes_everything_but_keeps_the_data(
    client: TestClient, admin: Headers, sam: Headers, world: ControlledProvider
) -> None:
    pick = post_pick(client, sam, upcoming(world))
    set_flag(client, admin, "community", False)
    assert client.get(f"{PICKS}/{pick['id']}", headers=sam).status_code == 404
    assert client.get("/v1/community/guidelines").status_code == 404
    assert count(client, CommunityPick) == 1
    # The data is still the user's: it stays in the export.
    export = client.get("/v1/me/export", headers=sam).json()["community"]
    assert export["profile"]["handle"] == "sample_sam" and len(export["picks"]) == 1
    set_flag(client, admin, "community", True)
    assert client.get(f"{PICKS}/{pick['id']}", headers=sam).status_code == 200


def test_the_leaderboard_needs_its_own_flag_as_well(
    client: TestClient, admin: Headers, sam: Headers
) -> None:
    flags = client.get("/v1/flags").json()["flags"]
    assert (flags["community"], flags["community_leaderboard"]) == (True, False)
    response = client.get("/v1/community/leaderboard", headers=sam)
    assert response.status_code == 404
    assert response.json()["error"]["details"] == {"flag": "community_leaderboard"}
    # The leaderboard flag alone is not enough either.
    set_flag(client, admin, "community_leaderboard", True)
    assert client.get("/v1/community/leaderboard", headers=sam).status_code == 200
    set_flag(client, admin, "community", False)
    response = client.get("/v1/community/leaderboard", headers=sam)
    assert response.status_code == 404
    assert response.json()["error"]["details"] == {"flag": "community"}


# ----------------------------------------------------------------- guidelines
def test_guidelines_are_one_structured_list_and_need_no_sign_in(
    client: TestClient, admin: Headers
) -> None:
    response = client.get("/v1/community/guidelines")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"version", "intro", "rules", "enforcement", "help"}
    assert [rule["key"] for rule in body["rules"]] == [
        "be_civil",
        "no_guarantees_or_inducements",
        "no_selling_or_links",
        "no_personal_information",
        "adults_only",
        "opinions_not_advice",
    ]
    assert all(rule["title"] and rule["text"] for rule in body["rules"])
    by_key = {rule["key"]: rule["text"] for rule in body["rules"]}
    assert "21" in by_key["adults_only"]
    assert "not betting advice" in by_key["opinions_not_advice"]
    assert "mocking" in by_key["be_civil"]  # RESPONSIBLE_GAMBLING.md: no mocking losses
    assert "1-800-GAMBLER" in body["help"] and "21+" in body["help"]
    # The rules describe what is banned without using hype themselves.
    text = " ".join([body["intro"], body["enforcement"], *by_key.values()]).lower()
    for phrase in ("best bet", "top pick", "can't lose", "free money", "!"):
        assert phrase not in text


# ------------------------------------------------------------------- profiles
def test_create_read_and_update_a_profile(client: TestClient, admin: Headers) -> None:
    headers = auth_headers(client, "ada@example.test")
    missing = client.get(PROFILE, headers=headers)
    assert missing.status_code == 404 and code(missing) == "not_found"

    created = client.put(
        PROFILE,
        json={"handle": "  Sample_Sam ", "bio": "Totals, mostly.", "is_public": True},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    profile = created.json()
    assert profile == {
        "handle": "sample_sam",  # lowered and trimmed
        "bio": "Totals, mostly.",
        "joined": FROZEN_NOW.strftime("%Y-%m"),
        "follower_count": 0,
        "following_count": 0,
        "record": profile["record"],
        "is_following": False,
        "is_blocked": False,
        "is_me": True,
        "is_public": True,
        "can_post": True,
        "moderation_status": "visible",
        "moderation_note": None,
    }
    assert profile["record"]["picks"] == 0 and profile["record"]["verified"] is True
    assert client.get(PROFILE, headers=headers).json() == profile

    updated = client.put(
        PROFILE, json={"handle": "sample_sam", "is_public": False}, headers=headers
    )
    assert updated.status_code == 200
    assert (updated.json()["bio"], updated.json()["is_public"], updated.json()["can_post"]) == (
        None,
        False,
        False,
    )
    renamed = client.put(PROFILE, json={"handle": "sam_two", "is_public": True}, headers=headers)
    assert renamed.status_code == 200 and renamed.json()["handle"] == "sam_two"
    assert count(client, CommunityProfile) == 1
    assert audit_actions(client) == [
        "community.profile_created",
        "community.profile_updated",
        "community.profile_updated",
    ]


def test_a_profile_never_exposes_account_data(
    client: TestClient, admin: Headers, mara: Headers
) -> None:
    owner = auth_headers(client, "private.person@example.test")
    account = client.get("/v1/me", headers=owner).json()
    client.put(PROFILE, json={"handle": "sample_sam", "is_public": True}, headers=owner)
    for viewer, path in ((mara, "/v1/community/profiles/sample_sam"), (owner, PROFILE)):
        response = client.get(path, headers=viewer)
        assert response.status_code == 200
        text = response.text.lower()
        for secret in ("private.person", "example.test", account["id"], "ada", "plan", "email"):
            assert secret.lower() not in text, secret
    public = client.get("/v1/community/profiles/sample_sam", headers=mara).json()
    assert set(public) == {
        "handle",
        "bio",
        "joined",
        "follower_count",
        "following_count",
        "record",
        "is_following",
        "is_blocked",
        "is_me",
    }
    assert public["is_me"] is False


@pytest.mark.parametrize(
    ("handle", "expected"),
    [
        ("ab", "invalid_handle"),
        ("a" * 21, "invalid_handle"),
        ("has space", "invalid_handle"),
        ("dash-ed", "invalid_handle"),
        ("dot.ted", "invalid_handle"),
        ("émile", "invalid_handle"),
        ("semi;colon", "invalid_handle"),
        ("", "invalid_handle"),
        ("admin", "handle_reserved"),
        ("ADMIN", "handle_reserved"),
        ("oddvex", "handle_reserved"),
        ("support", "handle_reserved"),
        ("moderator", "handle_reserved"),
        ("staff", "handle_reserved"),
        ("official", "handle_reserved"),
        ("help", "handle_reserved"),
        ("root", "handle_reserved"),
        ("system", "handle_reserved"),
        ("oddvex_team", "handle_reserved"),
        ("the_oddvexer", "handle_reserved"),
        ("official_picks", "handle_reserved"),
        ("admin_jo", "handle_reserved"),
        ("jo_support", "handle_reserved"),
        ("guaranteed_wins", "content_not_allowed"),
        ("dm_me_picks", "content_not_allowed"),
        ("free_money_fan", "content_not_allowed"),
    ],
)
def test_handle_rules_have_clear_codes(
    client: TestClient, admin: Headers, handle: str, expected: str
) -> None:
    headers = auth_headers(client)
    response = client.put(PROFILE, json={"handle": handle, "is_public": True}, headers=headers)
    assert response.status_code == 422, response.text
    assert code(response) == expected
    assert response.json()["error"]["details"]["field"] == "handle"
    assert count(client, CommunityProfile) == 0


@pytest.mark.parametrize("handle", ["abc", "a" * 20, "sam_2026", "___", "9lives", "helper_mo"])
def test_valid_handles(client: TestClient, admin: Headers, handle: str) -> None:
    response = client.put(
        PROFILE, json={"handle": handle, "is_public": True}, headers=auth_headers(client)
    )
    assert response.status_code == 201, response.text


def test_handles_are_unique_whatever_the_case(
    client: TestClient, admin: Headers, sam: Headers
) -> None:
    other = auth_headers(client, "other@example.test")
    for attempt in ("sample_sam", "SAMPLE_SAM", "Sample_Sam"):
        taken = client.put(PROFILE, json={"handle": attempt, "is_public": True}, headers=other)
        assert taken.status_code == 409 and code(taken) == "handle_taken", attempt
    # Keeping your own handle is not a conflict.
    same = client.put(PROFILE, json={"handle": "SAMPLE_SAM", "is_public": True}, headers=sam)
    assert same.status_code == 200 and same.json()["handle"] == "sample_sam"


def test_bio_rules(client: TestClient, admin: Headers) -> None:
    headers = auth_headers(client)

    def put(bio: Any) -> Any:
        return client.put(
            PROFILE, json={"handle": "sample_sam", "bio": bio, "is_public": True}, headers=headers
        )

    too_long = put("x" * 281)
    assert too_long.status_code == 422 and code(too_long) == "validation_error"
    for bio in ("see https://example.test", "http://example.test", "www.example.test"):
        link = put(bio)
        assert link.status_code == 422 and code(link) == "links_not_allowed", bio
        assert link.json()["error"]["details"] == {"field": "bio", "rule": "links"}
    banned = put("Guaranteed winners daily, DM me")
    assert banned.status_code == 422 and code(banned) == "content_not_allowed"
    assert banned.json()["error"]["details"] == {"field": "bio", "rule": "guaranteed_outcome"}
    control = put("nul\x00byte")
    assert control.status_code == 422 and code(control) == "invalid_text"
    extra = client.put(
        PROFILE,
        json={"handle": "sample_sam", "is_public": True, "display_name": "x"},
        headers=headers,
    )
    assert extra.status_code == 422
    assert count(client, CommunityProfile) == 0

    # Plain text is stored and returned exactly as sent; the client escapes it.
    verbatim = "<b>Totals</b> & unders — 100% research.\nLine two."
    assert len("x" * 280) == 280 and put("x" * 280).status_code == 201
    assert put(verbatim).json()["bio"] == verbatim
    assert put("   ").json()["bio"] is None


def test_a_profile_is_only_discoverable_while_it_is_public(
    client: TestClient, admin: Headers, mara: Headers
) -> None:
    hidden = member(client, "private_pat", is_public=False)
    unknown = client.get("/v1/community/profiles/nobody_here", headers=mara)
    private = client.get("/v1/community/profiles/private_pat", headers=mara)
    assert unknown.status_code == private.status_code == 404
    # Same code and same wording: a private handle is indistinguishable from a free one.
    assert code(unknown) == code(private) == "not_found"
    assert private.json()["error"]["message"].replace("private_pat", "X") == unknown.json()[
        "error"
    ]["message"].replace("nobody_here", "X")
    for odd in ("../etc", "a", "x" * 64, "has space", "%00"):
        assert client.get(f"/v1/community/profiles/{odd}", headers=mara).status_code == 404
    # Its owner sees it, and it cannot post.
    own = client.get("/v1/community/profiles/private_pat", headers=hidden)
    assert own.status_code == 200 and own.json()["is_me"] is True
    assert client.get(PROFILE, headers=hidden).json()["can_post"] is False
    assert client.get("/v1/community/profiles/PRIVATE_PAT", headers=hidden).status_code == 200


def test_posting_needs_a_public_profile(
    client: TestClient, admin: Headers, sam: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world)
    pick = post_pick(client, sam, event)
    nobody = auth_headers(client, "nobody@example.test")
    private = member(client, "private_pat", is_public=False)
    for headers, reason in ((nobody, "no_profile"), (private, "profile_not_public")):
        attempts = [
            client.post(
                PICKS,
                json={"event_id": event.id, "market": "moneyline", "outcome_key": "home"},
                headers=headers,
            ),
            client.post(f"{PICKS}/{pick['id']}/comments", json={"body": "hi"}, headers=headers),
            client.post("/v1/community/follows/sample_sam", headers=headers),
        ]
        for response in attempts:
            assert response.status_code == 403, response.text
            assert code(response) == "profile_required"
            assert response.json()["error"]["details"] == {"reason": reason}
    assert count(client, CommunityPick) == 1 and count(client, CommunityComment) == 0
    # Reading, liking, blocking and reporting do not need a profile.
    assert client.get(f"{PICKS}/{pick['id']}", headers=nobody).status_code == 200
    assert client.put(f"{PICKS}/{pick['id']}/like", headers=nobody).json()["like_count"] == 1
    assert client.put("/v1/community/blocks/sample_sam", headers=private).status_code == 200


# ---------------------------------------------------------------------- picks
def test_a_pick_snapshots_the_best_open_non_stale_price(
    client: TestClient, sam: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world)
    world.set_odds(
        event.id,
        "moneyline",
        [
            fresh("northline", moneyline(-120, 100)),
            fresh("cardinal", moneyline(-115, -105)),
            # Better prices that must not count: stale, suspended, unavailable.
            ("oldmill", "open", 5000.0, moneyline(150, 150)),
            ("summit", "suspended", 10.0, moneyline(140, 140)),
            ("kestrel", "unavailable", 10.0, []),
        ],
    )
    pick = post_pick(client, sam, event, analysis="Pace is up over the last five.")
    assert pick["price"]["american"] == -115 and pick["sportsbook"] == {
        "key": "cardinal",
        "name": "Cardinal Sports",
    }
    assert pick["price"]["decimal"] == round(float(american_to_decimal(-115)), 4)
    # Exactly what the odds endpoint calls the best price at this moment.
    odds = client.get(f"/v1/events/{event.id}/odds", params={"market": "moneyline"}).json()
    best_home = next(o for o in odds["best"] if o["outcome_key"] == "home")
    assert (best_home["price"], best_home["sportsbook_key"]) == (pick["price"], "cardinal")

    assert pick["posted_at"] == world.current.isoformat().replace("+00:00", "Z")
    assert pick["event_start_time"] > pick["posted_at"]
    assert (pick["status"], pick["result"], pick["graded_at"], pick["final_score"]) == (
        "pending",
        None,
        None,
        None,
    )
    assert pick["verified"] is True and pick["data_mode"] == "synthetic"
    assert pick["author"] == {"handle": "sample_sam"} and pick["is_mine"] is True
    assert pick["analysis"] == "Pace is up over the last five."
    assert pick["selection"].endswith(" moneyline") and " at " in pick["event_label"]
    assert (pick["like_count"], pick["comment_count"], pick["liked_by_me"]) == (0, 0, False)
    assert (pick["league"], pick["market"], pick["outcome_key"], pick["line"]) == (
        "nba",
        "moneyline",
        "home",
        None,
    )
    # No stake, no units, no confidence, no account data: neither in nor out.
    assert not {"stake", "units", "confidence", "user_id", "email"} & set(pick)
    assert client.get(f"{PICKS}/{pick['id']}", headers=sam).json() == pick


def test_the_price_never_comes_from_the_client(
    client: TestClient, sam: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world)
    base = {"event_id": event.id, "market": "moneyline", "outcome_key": "home"}
    for extra in (
        {"price": 5.0},
        {"odds": 500},
        {"stake": 100},
        {"units": 5},
        {"confidence": 10},
        {"posted_at": "2020-01-01T00:00:00Z"},
        {"result": "won"},
        {"verified": False},
    ):
        response = client.post(PICKS, json={**base, **extra}, headers=sam)
        assert response.status_code == 422, extra
        assert code(response) == "validation_error"
    assert count(client, CommunityPick) == 0


def test_spread_and_total_picks_are_priced_at_their_line(
    client: TestClient, sam: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world)
    priced(world, event)
    home = post_pick(client, sam, event, "spread", "home", line=-3.5)
    assert (home["line"], home["price"]["american"], home["sportsbook"]["key"]) == (
        -3.5,
        -108,
        "cardinal",
    )
    assert home["selection"].endswith("-3.5 spread")
    over = post_pick(client, sam, event, "total", "over", line=200.5)
    assert (over["line"], over["price"]["american"], over["sportsbook"]["key"]) == (
        200.5,
        -105,
        "cardinal",
    )
    assert over["selection"].startswith("Over 200.5 in ")

    other = upcoming(world, index=1)
    priced(world, other)
    away = post_pick(client, sam, other, "spread", "away", line=3.5)
    assert (away["price"]["american"], away["sportsbook"]["key"]) == (-110, "northline")
    assert away["selection"].endswith("+3.5 spread")


def test_pick_validation_codes(client: TestClient, sam: Headers, world: ControlledProvider) -> None:
    event = upcoming(world)
    priced(world, event)
    soccer = upcoming(world, "soccer")
    live = world.list_events(status="live")[0]
    final = world.list_events(status="final")[0]

    def post(**body: Any) -> Any:
        return client.post(PICKS, json=body, headers=sam)

    cases = [
        ({"event_id": "evt_nope", "market": "moneyline", "outcome_key": "home"}, "unknown_event"),
        ({"event_id": live.id, "market": "moneyline", "outcome_key": "home"}, "event_not_open"),
        ({"event_id": final.id, "market": "moneyline", "outcome_key": "home"}, "event_not_open"),
        (
            {"event_id": soccer.id, "market": "spread", "outcome_key": "home", "line": -0.5},
            "market_not_available",
        ),
        ({"event_id": event.id, "market": "moneyline", "outcome_key": "draw"}, "invalid_selection"),
        ({"event_id": event.id, "market": "moneyline", "outcome_key": "over"}, "invalid_selection"),
        ({"event_id": event.id, "market": "total", "outcome_key": "home"}, "invalid_selection"),
        ({"event_id": event.id, "market": "spread", "outcome_key": "home"}, "invalid_selection"),
        ({"event_id": event.id, "market": "total", "outcome_key": "over"}, "invalid_selection"),
        (
            {"event_id": event.id, "market": "moneyline", "outcome_key": "home", "line": -3.5},
            "invalid_selection",
        ),
        # A line nobody is quoting cannot be priced, so it cannot be a pick.
        (
            {"event_id": event.id, "market": "spread", "outcome_key": "home", "line": -9.5},
            "price_not_available",
        ),
        (
            {"event_id": event.id, "market": "total", "outcome_key": "over", "line": 150.5},
            "price_not_available",
        ),
    ]
    for body, expected in cases:
        response = post(**body)
        assert response.status_code == 422, (body, response.text)
        assert code(response) == expected, body
    for body in (
        {"event_id": event.id, "market": "player_points", "outcome_key": "over", "line": 20.5},
        {"event_id": event.id, "market": "moneyline", "outcome_key": "tides"},
        {"event_id": event.id, "market": "moneyline"},
        {"market": "moneyline", "outcome_key": "home"},
        {"event_id": event.id, "market": "spread", "outcome_key": "home", "line": "abc"},
        {"event_id": "", "market": "moneyline", "outcome_key": "home"},
    ):
        response = post(**body)
        assert response.status_code == 422 and code(response) == "validation_error", body
    # Events that are live or final report the status they are in.
    assert post(event_id=live.id, market="moneyline", outcome_key="home").json()["error"][
        "details"
    ] == {"event_status": "live"}
    # A draw is a valid moneyline outcome where the league has one.
    assert post_pick(client, sam, soccer, "moneyline", "draw")["outcome_key"] == "draw"
    assert count(client, CommunityPick) == 1


def test_no_price_means_no_pick(
    client: TestClient, sam: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world)
    world.set_odds(
        event.id,
        "moneyline",
        [("oldmill", "open", 5000.0, moneyline(-110, -110)), ("summit", "suspended", 5.0, [])],
    )
    response = client.post(
        PICKS,
        json={"event_id": event.id, "market": "moneyline", "outcome_key": "home"},
        headers=sam,
    )
    assert response.status_code == 422 and code(response) == "price_not_available"


def test_analysis_rules(client: TestClient, sam: Headers, world: ControlledProvider) -> None:
    event = upcoming(world)

    def post(analysis: Any) -> Any:
        return client.post(
            PICKS,
            json={
                "event_id": event.id,
                "market": "moneyline",
                "outcome_key": "home",
                "analysis": analysis,
            },
            headers=sam,
        )

    assert code(post("x" * 1001)) == "validation_error"
    for text in ("more at https://example.test", "http://x.test", "www.example.test"):
        link = post(text)
        assert link.status_code == 422 and code(link) == "links_not_allowed"
        assert link.json()["error"]["details"] == {"field": "analysis", "rule": "links"}
    for text, rule in (
        ("Lock of the week. Bet the house.", "guaranteed_outcome"),
        ("Max bet this one", "inducement_to_bet"),
        ("Full card on venmo", "selling_or_promotion"),
        ("Telegram for more", "contact_solicitation"),
        ("call 555-123-4567", "contact_details"),
    ):
        banned = post(text)
        assert banned.status_code == 422 and code(banned) == "content_not_allowed", text
        assert banned.json()["error"]["details"] == {"field": "analysis", "rule": rule}
        assert banned.json()["error"]["message"]
    assert count(client, CommunityPick) == 0
    verbatim = "The locker room is healthy again: <3 of 5> starters & the bench.\n\tPace 101.2."
    created = post(verbatim)
    assert created.status_code == 201 and created.json()["analysis"] == verbatim
    assert count(client, CommunityPick) == 1


def test_one_pick_per_user_per_event_and_market(
    client: TestClient, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world)
    priced(world, event)
    first = post_pick(client, sam, event, "moneyline", "home")
    again = client.post(
        PICKS,
        json={"event_id": event.id, "market": "moneyline", "outcome_key": "away"},
        headers=sam,
    )
    assert again.status_code == 409 and code(again) == "pick_exists"
    assert again.json()["error"]["details"] == {"pick_id": first["id"]}
    # Another market of the same event, another event and another user are all fine.
    post_pick(client, sam, event, "total", "under", line=200.5)
    post_pick(client, sam, upcoming(world, index=1))
    post_pick(client, mara, event, "moneyline", "away")
    assert count(client, CommunityPick) == 4


def test_list_picks_filters_and_pages(
    client: TestClient, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    nba, nfl = upcoming(world), upcoming(world, "nfl")
    priced(world, nba)
    first = post_pick(client, sam, nba)
    world.advance(minutes=1)
    second = post_pick(client, mara, nba, "total", "over", line=200.5)
    world.advance(minutes=1)
    third = post_pick(client, sam, nfl)

    def ids(**params: Any) -> list[str]:
        response = client.get(PICKS, params=params, headers=mara)
        assert response.status_code == 200, response.text
        return [p["id"] for p in response.json()["items"]]

    assert ids() == [third["id"], second["id"], first["id"]]  # newest first
    assert ids(handle="sample_sam") == [third["id"], first["id"]]
    assert ids(handle="SAMPLE_SAM") == [third["id"], first["id"]]
    assert ids(event_id=nba.id) == [second["id"], first["id"]]
    assert ids(league="nfl") == ids(league=" NFL ") == [third["id"]]
    assert ids(status="pending") == [third["id"], second["id"], first["id"]]
    assert ids(status="graded") == [] and ids(league="nhl") == []
    assert ids(handle="sample_sam", league="nba", event_id=nba.id) == [first["id"]]
    assert client.get(PICKS, params={"handle": "nobody"}, headers=mara).status_code == 404
    assert client.get(PICKS, params={"status": "won"}, headers=mara).status_code == 422
    assert client.get(PICKS, params={"limit": 0}, headers=mara).status_code == 422
    assert client.get(PICKS, params={"limit": 101}, headers=mara).status_code == 422

    page = client.get(PICKS, params={"limit": 2}, headers=mara).json()
    assert [p["id"] for p in page["items"]] == [third["id"], second["id"]]
    rest = client.get(PICKS, params={"limit": 2, "before": page["next_before"]}, headers=mara)
    assert [p["id"] for p in rest.json()["items"]] == [first["id"]]
    assert rest.json()["next_before"] is None
    for bad in ("garbage", "12-", "-abc"):
        invalid = client.get(PICKS, params={"before": bad}, headers=mara)
        assert invalid.status_code == 422 and code(invalid) == "invalid_cursor"
    assert client.get(f"{PICKS}/nope", headers=mara).status_code == 404


def test_delete_only_by_the_author_and_only_while_the_event_is_upcoming(
    client: TestClient, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    event, later = upcoming(world), upcoming(world, index=1)
    pick = post_pick(client, sam, event)
    keep = post_pick(client, sam, later)
    client.put(f"{PICKS}/{pick['id']}/like", headers=mara)
    client.post(f"{PICKS}/{pick['id']}/comments", json={"body": "noted"}, headers=mara)

    forbidden = client.delete(f"{PICKS}/{pick['id']}", headers=mara)
    assert forbidden.status_code == 403 and code(forbidden) == "forbidden"
    assert client.delete(f"{PICKS}/nope", headers=sam).status_code == 404
    deleted = client.delete(f"{PICKS}/{pick['id']}", headers=sam)
    assert deleted.status_code == 204
    assert client.get(f"{PICKS}/{pick['id']}", headers=sam).status_code == 404
    # Its comments and likes go with it; a new pick on the same market is possible again.
    assert count(client, CommunityComment) == 0 and count(client, CommunityLike) == 0
    post_pick(client, sam, event)

    # Once the event has started the pick stays, whatever happens next.
    world.current = later.start_time + timedelta(minutes=1)
    locked = client.delete(f"{PICKS}/{keep['id']}", headers=sam)
    assert locked.status_code == 409 and code(locked) == "pick_locked"
    assert locked.json()["error"]["details"] == {"event_status": "live"}
    finish(world, later, 100, 90)
    locked = client.delete(f"{PICKS}/{keep['id']}", headers=sam)
    assert locked.status_code == 409 and code(locked) == "pick_locked"
    assert client.get(f"{PICKS}/{keep['id']}", headers=sam).json()["status"] == "graded"
    assert audit_actions(client).count("community.pick_deleted") == 1


# -------------------------------------------------------------------- grading
def test_picks_are_graded_lazily_from_the_final_score(
    client: TestClient, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world)
    priced(world, event)
    home_ml = post_pick(client, sam, event, "moneyline", "home")
    home_spread = post_pick(client, sam, event, "spread", "home", line=-3.5)
    over = post_pick(client, sam, event, "total", "over", line=200.5)
    away_ml = post_pick(client, mara, event, "moneyline", "away")
    under = post_pick(client, mara, event, "total", "under", line=200.5)

    # In play: nothing is graded yet.
    world.current = event.start_time + timedelta(minutes=30)
    assert {p["status"] for p in feed(client, sam)} == {"pending"}
    assert notifications(client, sam, "pick_graded") == []

    # Home wins 102-99: by 3, so -3.5 loses; 201 points, so over 200.5 wins.
    finish(world, event, 102, 99)
    graded = {p["id"]: p for p in feed(client, sam)}
    assert {p["status"] for p in graded.values()} == {"graded"}
    assert graded[home_ml["id"]]["result"] == "won"
    assert graded[home_spread["id"]]["result"] == "lost"
    assert graded[over["id"]]["result"] == "won"
    assert graded[away_ml["id"]]["result"] == "lost"
    assert graded[under["id"]]["result"] == "lost"
    for pick in graded.values():
        assert pick["final_score"] == {"home": 102, "away": 99}
        assert pick["graded_at"] == world.current.isoformat().replace("+00:00", "Z")
        assert pick["verified"] is True
    # The price is still the one recorded when the pick was posted.
    assert graded[home_ml["id"]]["price"] == home_ml["price"]

    # One notification per graded pick, to its author only, worded as a plain fact.
    mine = notifications(client, sam, "pick_graded")
    assert len(mine) == 3 and len(notifications(client, mara, "pick_graded")) == 2
    won = next(n for n in mine if n["data"]["pick_id"] == home_ml["id"])
    assert won["title"] == "Pick graded: won"
    assert won["body"] == (
        f"Your pick, {home_ml['selection']}, was graded as won. "
        f"Final score: {home_ml['event_label']}, 99 to 102."
    )
    assert won["href"] == f"/app/community/picks/{home_ml['id']}"
    assert won["data"] == {
        "pick_id": home_ml["id"],
        "result": "won",
        "home_score": 102,
        "away_score": 99,
    }
    for item in mine:
        for phrase in (*BANNED_PHRASES, "!"):
            assert phrase not in (item["title"] + item["body"]).lower()

    # Reading again grades nothing twice.
    feed(client, sam)
    client.get(PICKS, headers=sam)
    assert len(notifications(client, sam, "pick_graded")) == 3
    assert audit_actions(client).count("community.pick_graded") == 5
    assert client.get(PICKS, params={"status": "graded"}, headers=sam).json()["items"]


@pytest.mark.parametrize(
    ("market", "outcome", "line", "home", "away", "expected"),
    [
        ("moneyline", "home", None, 100, 100, "push"),
        ("moneyline", "away", None, 90, 100, "won"),
        ("spread", "home", -3.5, 104, 100, "won"),
        ("spread", "away", 3.5, 104, 100, "lost"),
        ("spread", "away", 3.5, 103, 100, "won"),
        ("total", "under", 200.5, 100, 100, "won"),
        ("total", "over", 200.5, 100, 100, "lost"),
    ],
)
def test_grading_uses_the_trackers_grading_function(
    client: TestClient,
    sam: Headers,
    world: ControlledProvider,
    market: str,
    outcome: str,
    line: float | None,
    home: int,
    away: int,
    expected: str,
) -> None:
    event = upcoming(world)
    priced(world, event)
    pick = post_pick(client, sam, event, market, outcome, line=line)
    # The same selection as a structured leg in the bet tracker.
    leg = {
        "selection": "same thing",
        "market": market,
        "event_id": event.id,
        "outcome_key": outcome,
        "odds": -110,
        **({"line": line} if line is not None else {}),
    }
    bet = client.post(
        "/v1/bets",
        json={"bet_type": "straight", "stake": 10, "sportsbook": "Northline", "legs": [leg]},
        headers=sam,
    ).json()
    finish(world, event, home, away)

    graded = client.get(f"{PICKS}/{pick['id']}", headers=sam).json()
    assert graded["result"] == expected == grade_leg(market, outcome, line, home, away)
    settled = client.post("/v1/bets/auto-settle", headers=sam).json()["settled"]
    assert [b["id"] for b in settled] == [bet["id"]]
    assert settled[0]["legs"][0]["result"] == expected  # one grading function, two callers


def test_a_three_way_moneyline_grades_a_tie_as_a_draw_win(
    client: TestClient, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world, "soccer")
    draw = post_pick(client, sam, event, "moneyline", "draw")
    home = post_pick(client, mara, event, "moneyline", "home")
    finish(world, event, 1, 1)
    assert client.get(f"{PICKS}/{draw['id']}", headers=sam).json()["result"] == "won"
    assert client.get(f"{PICKS}/{home['id']}", headers=sam).json()["result"] == "lost"


def test_a_pick_on_an_event_the_provider_dropped_is_voided_after_a_week(
    client: TestClient, sam: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world)
    pick = post_pick(client, sam, event)
    world.hide(event.id)
    world.current = event.start_time + timedelta(days=6)
    assert client.get(f"{PICKS}/{pick['id']}", headers=sam).json()["status"] == "pending"
    world.current = event.start_time + timedelta(days=7, minutes=1)
    voided = client.get(f"{PICKS}/{pick['id']}", headers=sam).json()
    assert (voided["status"], voided["result"], voided["final_score"]) == ("void", None, None)
    # A void pick is in no record and cannot be deleted either.
    assert client.get(PROFILE, headers=sam).json()["record"]["picks"] == 0
    assert client.delete(f"{PICKS}/{pick['id']}", headers=sam).status_code == 409
    assert notifications(client, sam, "pick_graded") == []


def test_grading_is_throttled_between_reads(
    make_app: AppFactory, world: ControlledProvider
) -> None:
    app = make_app(provider=world, **{**COMMUNITY_APP, "community_grade_min_seconds": 60})
    with TestClient(app) as client:
        enable(client)
        sam = member(client, "sample_sam")
        event = upcoming(world)
        pick = post_pick(client, sam, event)
        feed(client, sam)  # a grading pass ran (and found nothing) just now
        world.current = event.start_time + timedelta(hours=4)
        world.finish(event.id, 100, 90)
        feed(client, sam)  # the clock moved on by hours: a new pass
        assert client.get(f"{PICKS}/{pick['id']}", headers=sam).json()["status"] == "graded"

        other = upcoming(world)
        second = post_pick(client, sam, other)
        world.current = other.start_time + timedelta(seconds=1)
        feed(client, sam)  # a pass: the game has started but is not final
        world.finish(other.id, 100, 90)
        world.advance(seconds=30)  # final now, but the last pass was 30 seconds ago
        assert client.get(f"{PICKS}/{second['id']}", headers=sam).json()["status"] == "pending"
        world.advance(seconds=60)
        assert client.get(f"{PICKS}/{second['id']}", headers=sam).json()["status"] == "graded"


def load_script(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, API_ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_grading_script_grades_without_anyone_reading(
    client: TestClient,
    app: FastAPI,
    sam: Headers,
    mara: Headers,
    world: ControlledProvider,
) -> None:
    script = load_script("grade_picks")
    first, second, third = (upcoming(world, index=i) for i in range(3))
    picks = [post_pick(client, sam, event) for event in (first, second, third)]
    post_pick(client, mara, first, "moneyline", "away")
    assert script.run(app.state.settings, provider=world) == {
        "passes": 1,
        "checked": 0,
        "graded": 0,
        "voided": 0,
    }
    finish(world, first, 100, 90)
    world.current = second.start_time + timedelta(minutes=5)  # second in play, third ahead

    dry = script.run(app.state.settings, provider=world, dry_run=True)
    assert (dry["checked"], dry["graded"]) == (2, 2)  # two started events, two picks graded
    assert count(client, Notification) == 0  # a dry run saves nothing

    totals = script.run(app.state.settings, provider=world)
    assert (totals["checked"], totals["graded"], totals["voided"]) == (2, 2, 0)
    assert script.run(app.state.settings, provider=world)["graded"] == 0  # idempotent
    with app.state.session_factory() as db:
        statuses = {p.id: (p.status, p.result) for p in db.scalars(select(CommunityPick))}
    assert statuses[picks[0]["id"]] == ("graded", "won")
    assert statuses[picks[1]["id"]] == statuses[picks[2]["id"]] == ("pending", None)
    assert len(notifications(client, sam, "pick_graded")) == 1
    assert len(notifications(client, mara, "pick_graded")) == 1


# --------------------------------------------------------------------- record
def test_the_record_is_computed_from_graded_picks_only(
    client: TestClient, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    events = [upcoming(world, index=i) for i in range(4)]
    for event in events:
        priced(world, event)
    # Home moneyline at -115 on three games and one total; a fourth pick stays pending.
    post_pick(client, sam, events[0], "moneyline", "home")
    post_pick(client, sam, events[1], "moneyline", "home")
    post_pick(client, sam, events[2], "moneyline", "home")
    post_pick(client, sam, events[0], "total", "over", line=200.5)  # -105
    post_pick(client, sam, events[3], "moneyline", "home")
    empty = client.get("/v1/community/profiles/sample_sam", headers=mara).json()["record"]
    assert (empty["picks"], empty["win_rate"], empty["win_rate_interval"]) == (0, None, None)
    assert (empty["average_price"], empty["flat_stake_roi"], empty["units_profit"]) == (
        None,
        None,
        0.0,
    )
    assert "0 graded picks" in empty["sample_note"]

    finish(world, events[2], 100, 100)  # push
    world.finish(events[1].id, 90, 100)  # lost
    world.finish(events[0].id, 110, 100)  # moneyline won, 210 points: over won
    record = client.get("/v1/community/profiles/sample_sam", headers=mara).json()["record"]
    # Prices are stored to six decimal places.
    price_ml = round(float(american_to_decimal(-115)), 6)
    price_over = round(float(american_to_decimal(-105)), 6)
    units = (price_ml - 1) + (price_over - 1) - 1 + 0
    low, high = wilson_interval(2, 3)
    assert record == {
        "verified": True,
        "picks": 4,
        "wins": 2,
        "losses": 1,
        "pushes": 1,
        "win_rate": round(2 / 3, 6),
        "win_rate_interval": {
            "low": round(low, 6),
            "high": round(high, 6),
            "confidence_level": 0.95,
        },
        "average_price": record["average_price"],
        "flat_stake_roi": round(units / 4, 6),
        "units_profit": round(units, 4),
        "method": FLAT_STAKE_METHOD,
        "sample_note": (
            "Small sample: 4 graded picks. Fewer than 30 is too few to tell skill from luck."
        ),
        "caveat": guidelines.RECORD_CAVEAT,
    }
    assert record["average_price"]["decimal"] == round((3 * price_ml + price_over) / 4, 4)
    assert "do not predict" in record["caveat"]
    assert client.get(PROFILE, headers=sam).json()["record"] == record


def test_the_sample_note_goes_away_at_thirty_graded_picks(client: TestClient, sam: Headers) -> None:
    insert_graded_picks(client, "sample_sam", "W" * 15 + "L" * 13 + "P", graded_at=FROZEN_NOW)
    record = client.get(PROFILE, headers=sam).json()["record"]
    assert record["picks"] == 29 and "29 graded picks" in record["sample_note"]
    insert_graded_picks(client, "sample_sam", "W", graded_at=FROZEN_NOW, prefix="y")
    record = client.get(PROFILE, headers=sam).json()["record"]
    assert (record["picks"], record["wins"], record["sample_note"]) == (30, 16, None)
    assert record["caveat"] and record["method"]  # still stated at any sample size
    assert service.sample_note(1) == (
        "Small sample: 1 graded pick. Fewer than 30 is too few to tell skill from luck."
    )


# -------------------------------------------------------------------- follows
def test_follow_and_unfollow(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers
) -> None:
    followed = client.post("/v1/community/follows/sample_sam", headers=mara)
    assert followed.status_code == 200
    assert followed.json() == {"handle": "sample_sam", "is_following": True}
    again = client.post("/v1/community/follows/SAMPLE_SAM", headers=mara)
    assert again.status_code == 200 and count(client, CommunityFollow) == 1

    theirs = client.get("/v1/community/profiles/sample_sam", headers=mara).json()
    assert (theirs["follower_count"], theirs["following_count"], theirs["is_following"]) == (
        1,
        0,
        True,
    )
    mine = client.get(PROFILE, headers=mara).json()
    assert (mine["follower_count"], mine["following_count"]) == (0, 1)
    following = client.get("/v1/community/following", headers=mara).json()["items"]
    assert [(f["handle"], f["is_following"]) for f in following] == [("sample_sam", True)]
    assert set(following[0]) == {"handle", "bio", "since", "is_following"}
    followers = client.get("/v1/community/followers", headers=sam).json()["items"]
    assert [(f["handle"], f["is_following"]) for f in followers] == [("madeup_mara", False)]
    assert client.get("/v1/community/followers", headers=mara).json() == {"items": []}

    # One notification for the followed profile, a plain fact, and never a second one.
    (note,) = notifications(client, sam, "new_follower")
    assert (note["title"], note["body"]) == (
        "New follower",
        "@madeup_mara follows your community profile.",
    )
    assert note["href"] == "/app/community/profiles/madeup_mara"
    assert note["data"] == {"handle": "madeup_mara"}

    assert client.delete("/v1/community/follows/sample_sam", headers=mara).status_code == 204
    assert client.delete("/v1/community/follows/sample_sam", headers=mara).status_code == 204
    assert client.delete("/v1/community/follows/nobody_here", headers=mara).status_code == 204
    assert count(client, CommunityFollow) == 0
    client.post("/v1/community/follows/sample_sam", headers=mara)
    assert len(notifications(client, sam, "new_follower")) == 1
    assert audit_actions(client)[-3:] == [
        "community.followed",
        "community.unfollowed",
        "community.followed",
    ]


def test_follow_rules(client: TestClient, admin: Headers, sam: Headers, mara: Headers) -> None:
    own = client.post("/v1/community/follows/sample_sam", headers=sam)
    assert own.status_code == 422 and code(own) == "cannot_follow_self"
    assert client.post("/v1/community/follows/nobody_here", headers=sam).status_code == 404
    member(client, "private_pat", is_public=False)
    assert client.post("/v1/community/follows/private_pat", headers=sam).status_code == 404

    # A profile that blocked you looks like one that does not exist.
    client.put("/v1/community/blocks/sample_sam", headers=mara)
    blocked = client.post("/v1/community/follows/madeup_mara", headers=sam)
    assert blocked.status_code == 404 and code(blocked) == "not_found"
    # And you cannot follow someone you blocked yourself.
    mine = client.post("/v1/community/follows/sample_sam", headers=mara)
    assert mine.status_code == 409 and code(mine) == "profile_blocked"
    assert count(client, CommunityFollow) == 0


def test_a_follower_who_goes_private_drops_out_of_counts_and_lists(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers
) -> None:
    client.post("/v1/community/follows/sample_sam", headers=mara)
    client.put(PROFILE, json={"handle": "madeup_mara", "is_public": False}, headers=mara)
    assert client.get(PROFILE, headers=sam).json()["follower_count"] == 0
    assert client.get("/v1/community/followers", headers=sam).json()["items"] == []
    client.put(PROFILE, json={"handle": "madeup_mara", "is_public": True}, headers=mara)
    assert client.get(PROFILE, headers=sam).json()["follower_count"] == 1


# ----------------------------------------------------------------------- feed
def test_feed_scopes_order_and_paging(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    nia = member(client, "notreal_nia")
    events = [upcoming(world, index=i) for i in range(3)]
    first = post_pick(client, sam, events[0])
    world.advance(minutes=1)
    second = post_pick(client, nia, events[0])
    world.advance(minutes=1)
    third = post_pick(client, sam, events[1])
    world.advance(minutes=1)
    own = post_pick(client, mara, events[2])

    everyone = [p["id"] for p in feed(client, mara)]
    assert everyone == [own["id"], third["id"], second["id"], first["id"]]
    assert feed(client, mara, "following") == []  # the default scope, following nobody
    assert client.get("/v1/community/feed", headers=mara).json()["items"] == []
    client.post("/v1/community/follows/sample_sam", headers=mara)
    following = feed(client, mara, "following")
    assert [p["id"] for p in following] == [third["id"], first["id"]]
    assert {p["author"]["handle"] for p in following} == {"sample_sam"}

    page = client.get(
        "/v1/community/feed", params={"scope": "everyone", "limit": 3}, headers=mara
    ).json()
    assert [p["id"] for p in page["items"]] == everyone[:3] and page["next_before"]
    rest = client.get(
        "/v1/community/feed",
        params={"scope": "everyone", "limit": 3, "before": page["next_before"]},
        headers=mara,
    ).json()
    assert [p["id"] for p in rest["items"]] == everyone[3:] and rest["next_before"] is None
    assert (
        client.get("/v1/community/feed", params={"scope": "popular"}, headers=mara).status_code
        == 422
    )


def test_feed_leaves_out_private_and_suspended_authors(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    event = upcoming(world)
    pick = post_pick(client, sam, event)
    client.post("/v1/community/follows/sample_sam", headers=mara)
    assert len(feed(client, mara)) == len(feed(client, mara, "following")) == 1

    # The author goes private: gone for everyone else, still there for the author.
    client.put(PROFILE, json={"handle": "sample_sam", "is_public": False}, headers=sam)
    assert feed(client, mara) == [] and feed(client, mara, "following") == []
    assert client.get(f"{PICKS}/{pick['id']}", headers=mara).status_code == 404
    assert [p["id"] for p in feed(client, sam)] == [pick["id"]]
    client.put(PROFILE, json={"handle": "sample_sam", "is_public": True}, headers=sam)
    assert len(feed(client, mara)) == 1

    # The author is suspended: gone everywhere, including the profile and the lists.
    suspended = client.post(
        f"/v1/admin/users/{user_id(client, sam)}/suspend",
        json={"reason": "testing"},
        headers=admin,
    )
    assert suspended.status_code == 200
    assert feed(client, mara) == [] and feed(client, mara, "following") == []
    assert client.get(f"{PICKS}/{pick['id']}", headers=mara).status_code == 404
    assert client.get("/v1/community/profiles/sample_sam", headers=mara).status_code == 404
    assert client.get(PICKS, params={"handle": "sample_sam"}, headers=mara).status_code == 404
    assert client.get("/v1/community/following", headers=mara).json()["items"] == []
    assert client.get(PROFILE, headers=mara).json()["following_count"] == 0
    assert client.get(PICKS, headers=sam).status_code == 401  # and they are locked out


# ------------------------------------------------------------------- comments
def test_comments_are_stored_and_returned_verbatim(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    pick = post_pick(client, sam, upcoming(world))
    url = f"{PICKS}/{pick['id']}/comments"
    body = "<script>alert('x')</script> & \"quotes\" — naïve café 🏀\n  second line"
    created = client.post(url, json={"body": body}, headers=mara)
    assert created.status_code == 201, created.text
    comment = created.json()
    assert comment == {
        "id": comment["id"],
        "pick_id": pick["id"],
        "author": {"handle": "madeup_mara"},
        "body": body,  # not escaped, not trimmed: the client escapes when it renders
        "created_at": comment["created_at"],
        "is_mine": True,
        "moderation_status": "visible",
        "moderation_note": None,
    }
    world.advance(minutes=1)
    reply = client.post(url, json={"body": "Fair point."}, headers=sam).json()
    listed = client.get(url, headers=sam).json()
    assert [c["id"] for c in listed["items"]] == [reply["id"], comment["id"]]  # newest first
    assert [c["is_mine"] for c in listed["items"]] == [True, False]
    assert listed["items"][1]["body"] == body and listed["next_before"] is None
    assert client.get(f"{PICKS}/{pick['id']}", headers=sam).json()["comment_count"] == 2

    page = client.get(url, params={"limit": 1}, headers=sam).json()
    assert [c["id"] for c in page["items"]] == [reply["id"]] and page["next_before"]
    older = client.get(url, params={"limit": 1, "before": page["next_before"]}, headers=sam)
    assert [c["id"] for c in older.json()["items"]] == [comment["id"]]

    # The author of the pick is told about someone else's comment, not about their own,
    # and the notification does not repeat what was written.
    (note,) = notifications(client, sam, "pick_comment")
    assert note["title"] == "New comment on your pick"
    assert note["body"] == f"@madeup_mara commented on your pick: {pick['selection']}."
    assert "script" not in note["body"] and note["href"] == f"/app/community/picks/{pick['id']}"
    assert notifications(client, mara, "pick_comment") == []
    assert (
        client.post(f"{PICKS}/nope/comments", json={"body": "x"}, headers=mara).status_code == 404
    )
    assert client.get(f"{PICKS}/nope/comments", headers=mara).status_code == 404


def test_comment_rules(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    pick = post_pick(client, sam, upcoming(world))
    url = f"{PICKS}/{pick['id']}/comments"

    def post(body: Any) -> Any:
        return client.post(url, json={"body": body}, headers=mara)

    for body in (
        "more at http://example.test",
        "more at https://example.test/x?ref=affiliate",
        "see www.example.test",
        "HTTPS://EXAMPLE.TEST",
    ):
        link = post(body)
        assert link.status_code == 422 and code(link) == "links_not_allowed", body
        assert link.json()["error"]["details"] == {"field": "body", "rule": "links"}
    for body, rule in (
        ("This is guaranteed", "guaranteed_outcome"),
        ("you can't lose", "guaranteed_outcome"),
        ("chase those losses", "inducement_to_bet"),
        ("promo code TIDES", "selling_or_promotion"),
        ("dm me", "contact_solicitation"),
        ("me@example.test", "contact_details"),
    ):
        banned = post(body)
        assert banned.status_code == 422 and code(banned) == "content_not_allowed", body
        assert banned.json()["error"]["details"] == {"field": "body", "rule": rule}
    assert code(post("x" * 501)) == "validation_error"
    assert code(post("")) == "validation_error"
    blank = post("   \n ")
    assert blank.status_code == 422 and code(blank) == "invalid_text"
    assert code(post("bell\x07")) == "invalid_text"
    assert client.post(url, json={"body": "ok", "pick_id": "x"}, headers=mara).status_code == 422
    assert count(client, CommunityComment) == 0
    assert post("x" * 500).status_code == 201
    assert post("The locker room talk is about pace, not about a lock.").status_code == 201
    assert notifications(client, sam, "pick_comment")[0]["kind"] == "pick_comment"


def test_delete_a_comment_as_author_or_moderator(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    pick = post_pick(client, sam, upcoming(world))
    url = f"{PICKS}/{pick['id']}/comments"
    first = client.post(url, json={"body": "one"}, headers=mara).json()
    second = client.post(url, json={"body": "two"}, headers=mara).json()

    # Not the author of the comment, even though it is on their pick: not allowed.
    forbidden = client.delete(f"/v1/community/comments/{first['id']}", headers=sam)
    assert forbidden.status_code == 403 and code(forbidden) == "forbidden"
    assert client.delete("/v1/community/comments/nope", headers=mara).status_code == 404
    assert count(client, CommunityComment) == 2

    assert client.delete(f"/v1/community/comments/{first['id']}", headers=mara).status_code == 204
    assert client.delete(f"/v1/community/comments/{first['id']}", headers=mara).status_code == 404
    # A moderator can delete anyone's comment, and that is audited as such.
    assert client.delete(f"/v1/community/comments/{second['id']}", headers=admin).status_code == 204
    assert client.delete("/v1/community/comments/nope", headers=admin).status_code == 404
    assert client.get(url, headers=sam).json()["items"] == []
    by_author, by_moderator = audit_rows(client, "community.comment_deleted")
    assert by_author.details == {"pick_id": pick["id"], "by_moderator": False}
    assert by_moderator.details == {
        "pick_id": pick["id"],
        "by_moderator": True,
        "author_id": user_id(client, mara),
    }
    assert by_moderator.user_id == user_id(client, admin)


# ---------------------------------------------------------------------- likes
def test_likes_are_idempotent(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    pick = post_pick(client, sam, upcoming(world))
    url = f"{PICKS}/{pick['id']}/like"
    for _ in range(3):
        liked = client.put(url, headers=mara)
        assert liked.status_code == 200
        assert liked.json() == {"pick_id": pick["id"], "liked_by_me": True, "like_count": 1}
    assert client.put(url, headers=sam).json()["like_count"] == 2  # your own pick, why not
    seen = client.get(f"{PICKS}/{pick['id']}", headers=mara).json()
    assert (seen["like_count"], seen["liked_by_me"]) == (2, True)
    assert feed(client, admin)[0]["liked_by_me"] is False

    for _ in range(2):
        unliked = client.delete(url, headers=mara)
        assert unliked.status_code == 200
        assert unliked.json() == {"pick_id": pick["id"], "liked_by_me": False, "like_count": 1}
    assert count(client, CommunityLike) == 1
    assert client.put(f"{PICKS}/nope/like", headers=mara).status_code == 404
    assert client.delete(f"{PICKS}/nope/like", headers=mara).status_code == 404
    assert notifications(client, sam, "pick_comment") == []  # a like notifies nobody


# --------------------------------------------------------------------- blocks
def test_blocking_removes_follows_and_hides_each_from_the_other_everywhere(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    nia = member(client, "notreal_nia")
    event = upcoming(world)
    sams = post_pick(client, sam, event)
    maras = post_pick(client, mara, event)
    nias = post_pick(client, nia, event)
    client.post("/v1/community/follows/sample_sam", headers=mara)
    client.post("/v1/community/follows/madeup_mara", headers=sam)
    client.post(f"{PICKS}/{nias['id']}/comments", json={"body": "from sam"}, headers=sam)
    client.post(f"{PICKS}/{nias['id']}/comments", json={"body": "from mara"}, headers=mara)
    assert count(client, CommunityFollow) == 2

    blocked = client.put("/v1/community/blocks/sample_sam", headers=mara)
    assert blocked.status_code == 200
    assert blocked.json() == {"handle": "sample_sam", "is_blocked": True}
    assert client.put("/v1/community/blocks/SAMPLE_SAM", headers=mara).status_code == 200
    assert count(client, CommunityBlock) == 1
    assert count(client, CommunityFollow) == 0  # both directions
    (entry,) = audit_rows(client, "community.blocked")
    assert entry.details == {"follows_removed": 2}

    listed = client.get("/v1/community/blocks", headers=mara).json()["items"]
    assert [b["handle"] for b in listed] == ["sample_sam"] and set(listed[0]) == {"handle", "since"}
    assert client.get("/v1/community/blocks", headers=sam).json() == {"items": []}

    # The blocked person: the blocker has vanished. Nothing says "you are blocked".
    for path in (
        "/v1/community/profiles/madeup_mara",
        f"{PICKS}/{maras['id']}",
        f"{PICKS}/{maras['id']}/comments",
    ):
        gone = client.get(path, headers=sam)
        assert gone.status_code == 404 and code(gone) == "not_found", path
    assert client.get(PICKS, params={"handle": "madeup_mara"}, headers=sam).status_code == 404
    assert client.put(f"{PICKS}/{maras['id']}/like", headers=sam).status_code == 404
    assert (
        client.post(f"{PICKS}/{maras['id']}/comments", json={"body": "hi"}, headers=sam).status_code
        == 404
    )
    assert client.post("/v1/community/follows/madeup_mara", headers=sam).status_code == 404
    report = client.post(
        "/v1/community/reports",
        json={"target_type": "pick", "target_id": maras["id"], "reason": "spam"},
        headers=sam,
    )
    assert report.status_code == 404
    assert {p["id"] for p in feed(client, sam)} == {sams["id"], nias["id"]}
    comments = client.get(f"{PICKS}/{nias['id']}/comments", headers=sam).json()["items"]
    assert [c["body"] for c in comments] == ["from sam"]
    assert client.get(f"{PICKS}/{nias['id']}", headers=sam).json()["comment_count"] == 1

    # The blocker: the same in the other direction, except that the profile can still
    # be looked up, which is how it gets unblocked.
    assert {p["id"] for p in feed(client, mara)} == {maras["id"], nias["id"]}
    assert client.get(f"{PICKS}/{sams['id']}", headers=mara).status_code == 404
    assert client.get(PICKS, params={"handle": "sample_sam"}, headers=mara).status_code == 404
    comments = client.get(f"{PICKS}/{nias['id']}/comments", headers=mara).json()["items"]
    assert [c["body"] for c in comments] == ["from mara"]
    profile = client.get("/v1/community/profiles/sample_sam", headers=mara)
    assert profile.status_code == 200 and profile.json()["is_blocked"] is True
    # Everybody else sees both.
    assert len(feed(client, nia)) == 3
    assert len(client.get(f"{PICKS}/{nias['id']}/comments", headers=nia).json()["items"]) == 2

    assert client.delete("/v1/community/blocks/sample_sam", headers=mara).status_code == 204
    assert client.delete("/v1/community/blocks/sample_sam", headers=mara).status_code == 204
    assert client.delete("/v1/community/blocks/nobody_here", headers=mara).status_code == 204
    assert len(feed(client, sam)) == len(feed(client, mara)) == 3
    assert client.get("/v1/community/profiles/madeup_mara", headers=sam).status_code == 200
    assert count(client, CommunityFollow) == 0  # unblocking does not restore the follows
    assert audit_actions(client)[-1] == "community.unblocked"


def test_block_rules(client: TestClient, admin: Headers, sam: Headers, mara: Headers) -> None:
    own = client.put("/v1/community/blocks/sample_sam", headers=sam)
    assert own.status_code == 422 and code(own) == "cannot_block_self"
    assert client.put("/v1/community/blocks/nobody_here", headers=sam).status_code == 404
    member(client, "private_pat", is_public=False)
    assert client.put("/v1/community/blocks/private_pat", headers=sam).status_code == 404
    assert count(client, CommunityBlock) == 0


# -------------------------------------------------------------------- reports
def test_report_a_pick_a_comment_and_a_profile(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    pick = post_pick(client, sam, upcoming(world), analysis="Research only.")
    comment = client.post(
        f"{PICKS}/{pick['id']}/comments", json={"body": "my take"}, headers=sam
    ).json()

    def report(**body: Any) -> Any:
        return client.post("/v1/community/reports", json=body, headers=mara)

    created = report(
        target_type="pick", target_id=pick["id"], reason="misleading_claims", details="  why  "
    )
    assert created.status_code == 201, created.text
    assert created.json() == {
        "id": created.json()["id"],
        "target_type": "pick",
        "target_id": pick["id"],
        "reason": "misleading_claims",
        "details": "why",
        "status": "open",
        "created_at": created.json()["created_at"],
    }
    # One open report per person and target: the same one comes back.
    again = report(target_type="pick", target_id=pick["id"], reason="spam")
    assert again.status_code == 200 and again.json() == created.json()
    assert (
        report(target_type="comment", target_id=comment["id"], reason="harassment").status_code
        == 201
    )
    by_handle = report(target_type="profile", target_id="Sample_Sam", reason="other")
    assert by_handle.status_code == 201 and by_handle.json()["target_id"] == "sample_sam"
    assert report(target_type="profile", target_id="sample_sam", reason="spam").status_code == 200
    assert count(client, CommunityReport) == 3
    # Someone else's report on the same thing is a report of its own.
    other = member(client, "notreal_nia")
    assert (
        client.post(
            "/v1/community/reports",
            json={"target_type": "pick", "target_id": pick["id"], "reason": "spam"},
            headers=other,
        ).status_code
        == 201
    )
    # The reported person is told nothing.
    assert client.get("/v1/notifications", headers=sam).json()["items"] == []
    assert audit_actions(client).count("community.reported") == 4


def test_report_rules(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    pick = post_pick(client, sam, upcoming(world))

    def report(who: Headers, **body: Any) -> Any:
        return client.post("/v1/community/reports", json=body, headers=who)

    own = report(sam, target_type="pick", target_id=pick["id"], reason="spam")
    assert own.status_code == 422 and code(own) == "cannot_report_own_content"
    own = report(sam, target_type="profile", target_id="sample_sam", reason="spam")
    assert own.status_code == 422 and code(own) == "cannot_report_own_content"
    for target_type, target_id in (("pick", "nope"), ("comment", "nope"), ("profile", "nobody")):
        missing = report(mara, target_type=target_type, target_id=target_id, reason="spam")
        assert missing.status_code == 404, target_type
    for body in (
        {"target_type": "user", "target_id": pick["id"], "reason": "spam"},
        {"target_type": "pick", "target_id": pick["id"], "reason": "i_lost_money"},
        {"target_type": "pick", "target_id": pick["id"]},
        {"target_type": "pick", "reason": "spam"},
        {"target_type": "pick", "target_id": "", "reason": "spam"},
        {"target_type": "pick", "target_id": pick["id"], "reason": "spam", "details": "x" * 501},
        {"target_type": "pick", "target_id": pick["id"], "reason": "spam", "status": "resolved"},
    ):
        invalid = client.post("/v1/community/reports", json=body, headers=mara)
        assert invalid.status_code == 422 and code(invalid) == "validation_error", body
    for reason in (
        "spam",
        "harassment",
        "inducement_to_bet",
        "misleading_claims",
        "personal_information",
        "other",
    ):
        reporter = auth_headers(client, f"{reason}@example.test")
        ok = report(reporter, target_type="pick", target_id=pick["id"], reason=reason)
        assert ok.status_code == 201, reason
    assert count(client, CommunityReport) == 6


# ---------------------------------------------------------------- rate limits
def limited_app(make_app: AppFactory, world: ControlledProvider, **limits: int) -> FastAPI:
    return make_app(
        provider=world,
        **COMMUNITY_APP,
        rate_limit_enabled=True,
        rate_limit_auth_per_minute=1000,
        **limits,
    )


def assert_limited(response: Any) -> None:
    assert response.status_code == 429, response.text
    assert code(response) == "rate_limited"
    assert int(response.headers["retry-after"]) >= 1
    assert response.json()["error"]["details"]["retry_after_seconds"] >= 1


def test_picks_are_limited_per_user_per_day(
    make_app: AppFactory, world: ControlledProvider
) -> None:
    with TestClient(limited_app(make_app, world, community_picks_per_day=2)) as client:
        enable(client)
        sam, mara = member(client, "sample_sam"), member(client, "madeup_mara")
        events = [upcoming(world, index=i) for i in range(4)]
        # Requests that are refused do not use up the allowance.
        for _ in range(3):
            bad = client.post(
                PICKS,
                json={"event_id": "evt_nope", "market": "moneyline", "outcome_key": "home"},
                headers=sam,
            )
            assert bad.status_code == 422
        post_pick(client, sam, events[0])
        post_pick(client, sam, events[1])
        third = client.post(
            PICKS,
            json={"event_id": events[2].id, "market": "moneyline", "outcome_key": "home"},
            headers=sam,
        )
        assert_limited(third)
        assert int(third.headers["retry-after"]) > 80_000  # a day, not a minute
        # Deleting a pick does not give the slot back; another user has their own.
        deleted = client.get(PICKS, params={"handle": "sample_sam"}, headers=sam).json()["items"]
        assert client.delete(f"{PICKS}/{deleted[0]['id']}", headers=sam).status_code == 204
        again = client.post(
            PICKS,
            json={"event_id": events[3].id, "market": "moneyline", "outcome_key": "home"},
            headers=sam,
        )
        assert_limited(again)
        post_pick(client, mara, events[0])
        assert count(client, CommunityPick) == 2


def test_the_default_pick_limit_is_twenty_a_day(make_settings: SettingsFactory) -> None:
    settings = make_settings()
    assert settings.community_picks_per_day == 20
    assert settings.community_comments_per_hour == 30
    assert settings.community_reports_per_hour == 10


def test_comments_reports_and_follows_are_limited_per_user_per_hour(
    make_app: AppFactory, world: ControlledProvider
) -> None:
    app = limited_app(
        make_app,
        world,
        community_comments_per_hour=2,
        community_reports_per_hour=1,
        community_follows_per_hour=1,
    )
    with TestClient(app) as client:
        enable(client)
        sam, mara = member(client, "sample_sam"), member(client, "madeup_mara")
        member(client, "notreal_nia")
        first = post_pick(client, sam, upcoming(world))
        second = post_pick(client, sam, upcoming(world, index=1))
        url = f"{PICKS}/{first['id']}/comments"

        assert client.post(url, json={"body": "see www.x.test"}, headers=mara).status_code == 422
        assert client.post(url, json={"body": "one"}, headers=mara).status_code == 201
        assert client.post(url, json={"body": "two"}, headers=mara).status_code == 201
        limited = client.post(url, json={"body": "three"}, headers=mara)
        assert_limited(limited)
        assert 3000 < int(limited.headers["retry-after"]) <= 3600
        assert client.post(url, json={"body": "mine"}, headers=sam).status_code == 201

        def report(target: str) -> Any:
            return client.post(
                "/v1/community/reports",
                json={"target_type": "pick", "target_id": target, "reason": "spam"},
                headers=mara,
            )

        assert report(first["id"]).status_code == 201
        assert report(first["id"]).status_code == 200  # the open one again: not a new report
        assert_limited(report(second["id"]))

        assert client.post("/v1/community/follows/sample_sam", headers=mara).status_code == 200
        assert client.post("/v1/community/follows/sample_sam", headers=mara).status_code == 200
        assert_limited(client.post("/v1/community/follows/notreal_nia", headers=mara))
        # Each kind of action has its own allowance.
        assert client.put(f"{PICKS}/{second['id']}/like", headers=mara).status_code == 200
        assert client.put("/v1/community/blocks/notreal_nia", headers=mara).status_code == 200
        assert count(client, CommunityComment) == 3 and count(client, CommunityReport) == 1


# -------------------------------------------------------------- notifications
def test_community_notifications_respect_the_preferences(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    preferences = client.get("/v1/me/notification-preferences", headers=sam).json()["in_app"]
    assert preferences["new_follower"] is preferences["pick_comment"] is True
    assert preferences["pick_graded"] is True
    updated = client.put(
        "/v1/me/notification-preferences",
        json={"in_app": {"new_follower": False, "pick_comment": False, "pick_graded": False}},
        headers=sam,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["in_app"]["price_alert"] is True  # the others are untouched

    event = upcoming(world)
    pick = post_pick(client, sam, event)
    client.post("/v1/community/follows/sample_sam", headers=mara)
    client.post(f"{PICKS}/{pick['id']}/comments", json={"body": "hello"}, headers=mara)
    finish(world, event, 100, 90)
    # Everything still happened; only the notifications were not created.
    assert client.get(f"{PICKS}/{pick['id']}", headers=sam).json()["result"] == "won"
    assert client.get(PROFILE, headers=sam).json()["follower_count"] == 1
    assert client.get("/v1/notifications", headers=sam).json()["items"] == []

    client.put(
        "/v1/me/notification-preferences", json={"in_app": {"pick_comment": True}}, headers=sam
    )
    client.post(f"{PICKS}/{pick['id']}/comments", json={"body": "again"}, headers=mara)
    kinds = [n["kind"] for n in client.get("/v1/notifications", headers=sam).json()["items"]]
    assert kinds == ["pick_comment"]


# ------------------------------------------------------------- account lifecycle
def test_deleting_an_account_removes_all_of_its_community_data(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    nia = member(client, "notreal_nia")
    done, ahead = upcoming(world), upcoming(world, index=1)
    graded = post_pick(client, sam, done, analysis="mine")
    pending = post_pick(client, sam, ahead)
    maras = post_pick(client, mara, ahead)
    for who, target in ((sam, "madeup_mara"), (mara, "sample_sam"), (nia, "sample_sam")):
        assert client.post(f"/v1/community/follows/{target}", headers=who).status_code == 200
    client.post(f"{PICKS}/{graded['id']}/comments", json={"body": "on sam's"}, headers=mara)
    client.post(f"{PICKS}/{maras['id']}/comments", json={"body": "by sam"}, headers=sam)
    client.post(f"{PICKS}/{maras['id']}/comments", json={"body": "by nia"}, headers=nia)
    client.put(f"{PICKS}/{maras['id']}/like", headers=sam)
    client.put(f"{PICKS}/{graded['id']}/like", headers=mara)
    client.put("/v1/community/blocks/notreal_nia", headers=sam)
    for who, body in (
        (sam, {"target_type": "pick", "target_id": maras["id"], "reason": "spam"}),
        (mara, {"target_type": "pick", "target_id": graded["id"], "reason": "spam"}),
        (mara, {"target_type": "profile", "target_id": "sample_sam", "reason": "other"}),
    ):
        assert client.post("/v1/community/reports", json=body, headers=who).status_code == 201
    finish(world, done, 100, 90)
    assert client.get(PROFILE, headers=sam).json()["record"]["picks"] == 1
    sam_id = user_id(client, sam)
    before = {
        model: count(client, model)
        for model in (CommunityPick, CommunityComment, CommunityLike, CommunityReport)
    }
    assert before == {
        CommunityPick: 3,
        CommunityComment: 3,
        CommunityLike: 2,
        CommunityReport: 3,
    }

    assert client.delete("/v1/me", headers=sam).status_code == 204

    with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
        assert db.get(CommunityProfile, sam_id) is None
        # Every pick, the graded one included: no public record without an account.
        assert [p.id for p in db.scalars(select(CommunityPick))] == [maras["id"]]
        # Sam's comment and the comment on Sam's pick are gone; Nia's on Mara's pick stays.
        assert [c.body for c in db.scalars(select(CommunityComment))] == ["by nia"]
        assert db.scalar(select(func.count()).select_from(CommunityLike)) == 0
        assert db.scalar(select(func.count()).select_from(CommunityBlock)) == 0
        # Reports made by Sam and reports about Sam's content are gone.
        assert db.scalar(select(func.count()).select_from(CommunityReport)) == 0
        follows = db.execute(select(CommunityFollow.follower_id, CommunityFollow.followed_id))
        assert follows.all() == []
    for path in (
        "/v1/community/profiles/sample_sam",
        f"{PICKS}/{graded['id']}",
        f"{PICKS}/{pending['id']}",
    ):
        assert client.get(path, headers=mara).status_code == 404
    profile = client.get(PROFILE, headers=mara).json()
    assert (profile["follower_count"], profile["following_count"]) == (0, 0)
    assert [p["id"] for p in feed(client, mara)] == [maras["id"]]
    assert client.get(f"{PICKS}/{maras['id']}", headers=mara).json()["like_count"] == 0
    # The handle is free again, and Nia is no longer hidden from anyone.
    assert member(client, "sample_sam", email="new.sam@example.test")
    assert client.get("/v1/community/profiles/notreal_nia", headers=mara).status_code == 200


def test_the_export_includes_the_community_data(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    empty = client.get("/v1/me/export", headers=admin).json()["community"]
    assert empty == {
        "profile": None,
        "picks": [],
        "comments": [],
        "following": [],
        "likes": [],
        "blocks": [],
        "reports": [],
    }
    nia = member(client, "notreal_nia")
    event = upcoming(world)
    mine = post_pick(client, sam, event, analysis="my reasoning")
    theirs = post_pick(client, mara, event)
    comment = client.post(
        f"{PICKS}/{theirs['id']}/comments", json={"body": "my comment"}, headers=sam
    ).json()
    client.post(f"{PICKS}/{mine['id']}/comments", json={"body": "not mine"}, headers=mara)
    client.post("/v1/community/follows/madeup_mara", headers=sam)
    client.put(f"{PICKS}/{theirs['id']}/like", headers=sam)
    client.put("/v1/community/blocks/notreal_nia", headers=sam)
    report = client.post(
        "/v1/community/reports",
        json={"target_type": "profile", "target_id": "madeup_mara", "reason": "other"},
        headers=sam,
    ).json()

    export = client.get("/v1/me/export", headers=sam).json()
    community = export["community"]
    assert community["profile"] == client.get(PROFILE, headers=sam).json()
    assert [p["id"] for p in community["picks"]] == [mine["id"]]
    assert community["picks"][0]["analysis"] == "my reasoning"
    assert community["comments"] == [comment]
    assert community["following"] == ["madeup_mara"]
    assert community["likes"] == [theirs["id"]]
    assert community["blocks"] == ["notreal_nia"]
    assert community["reports"] == [report]
    # Only the caller's own data: nobody else's text, email or id.
    text = str(community)
    assert "not mine" not in text and "example.test" not in text
    assert user_id(client, mara) not in text and user_id(client, nia) not in text
    assert "community.pick_created" in {entry["action"] for entry in export["audit_log"]}


# ---------------------------------------------------------------- leaderboard
def test_the_leaderboard_ranks_by_the_wilson_lower_bound(
    client: TestClient, world: ControlledProvider
) -> None:
    admin = enable(client, leaderboard=True)
    viewer = member(client, "viewer_vee")
    for handle in ("small_hot", "big_steady", "even_eve", "too_few", "all_push"):
        member(client, handle)
    now = world.current
    insert_graded_picks(client, "small_hot", "W" * 21 + "L" * 9, graded_at=now)  # 70% of 30
    insert_graded_picks(client, "big_steady", "W" * 66 + "L" * 34, graded_at=now)  # 66% of 100
    insert_graded_picks(client, "even_eve", "W" * 15 + "L" * 15 + "P" * 5, graded_at=now)
    insert_graded_picks(client, "too_few", "W" * 29, graded_at=now)  # perfect, but only 29
    insert_graded_picks(client, "all_push", "P" * 30, graded_at=now)  # no win rate at all

    response = client.get("/v1/community/leaderboard", headers=viewer)
    assert response.status_code == 200, response.text
    board = response.json()
    assert (board["window"], board["league"], board["minimum_graded_picks"]) == ("90d", None, 30)
    assert board["ranked_by"] == "wilson_lower_bound" and board["data_mode"] == "synthetic"
    rows = board["items"]
    # The bigger sample ranks first although its raw win rate is lower: 0.66 on 100 has a
    # higher lower bound than 0.70 on 30. Neither ROI nor the raw rate decides the order.
    assert [(r["rank"], r["handle"]) for r in rows] == [
        (1, "big_steady"),
        (2, "small_hot"),
        (3, "even_eve"),
    ]
    assert rows[0]["record"]["win_rate"] < rows[1]["record"]["win_rate"]
    lows = [r["record"]["win_rate_interval"]["low"] for r in rows]
    assert lows == sorted(lows, reverse=True)
    assert lows[0] == round(wilson_interval(66, 100)[0], 6)
    assert lows[1] == round(wilson_interval(21, 30)[0], 6)
    for row in rows:
        record = row["record"]
        assert set(row) == {"rank", "handle", "record"}  # a handle and numbers, nothing else
        assert record["picks"] >= 30 and record["sample_note"] is None
        assert record["win_rate_interval"]["confidence_level"] == 0.95
        assert record["win_rate_interval"]["low"] <= record["win_rate"]
    assert rows[2]["record"]["picks"] == 35 and rows[2]["record"]["pushes"] == 5
    assert board["caveat"] == guidelines.LEADERBOARD_CAVEAT
    assert "Past results do not predict future results" in board["caveat"]
    assert "not a recommendation" in board["caveat"]
    assert "Wilson 95%" in board["method"] and "30 graded picks" in board["method"]
    text = (board["caveat"] + board["method"]).lower()
    for phrase in (*BANNED_PHRASES, "best bettor", "top tipster", "sharp", "!"):
        assert phrase not in text, phrase

    # Blocked, private and suspended profiles are not ranked.
    client.put("/v1/community/blocks/big_steady", headers=viewer)
    board = client.get("/v1/community/leaderboard", headers=viewer).json()
    assert [r["handle"] for r in board["items"]] == ["small_hot", "even_eve"]
    with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
        owner = db.scalar(select(CommunityProfile).where(CommunityProfile.handle == "small_hot"))
        hot_id = owner.user_id
    client.post(f"/v1/admin/users/{hot_id}/suspend", json={"reason": "testing"}, headers=admin)
    board = client.get("/v1/community/leaderboard", headers=viewer).json()
    assert [r["handle"] for r in board["items"]] == ["even_eve"]
    assert [r["rank"] for r in board["items"]] == [1]


def test_leaderboard_window_and_league(client: TestClient, world: ControlledProvider) -> None:
    enable(client, leaderboard=True)
    viewer = member(client, "viewer_vee")
    member(client, "recent_ray")
    member(client, "older_ola")
    now = world.current
    insert_graded_picks(
        client, "recent_ray", "W" * 20 + "L" * 10, graded_at=now - timedelta(days=5)
    )
    insert_graded_picks(
        client, "recent_ray", "L" * 30, graded_at=now - timedelta(days=60), league="nfl", prefix="o"
    )
    insert_graded_picks(
        client, "older_ola", "W" * 25 + "L" * 5, graded_at=now - timedelta(days=200)
    )

    def board(**params: Any) -> list[tuple[str, int, int]]:
        response = client.get("/v1/community/leaderboard", params=params, headers=viewer)
        assert response.status_code == 200, response.text
        assert response.json()["window"] == params.get("window", "90d")
        return [
            (r["handle"], r["record"]["picks"], r["record"]["wins"])
            for r in response.json()["items"]
        ]

    assert board(window="30d") == [("recent_ray", 30, 20)]
    assert board() == board(window="90d") == [("recent_ray", 60, 20)]
    assert board(window="all") == [("older_ola", 30, 25), ("recent_ray", 60, 20)]
    assert board(window="all", league="nba") == [("older_ola", 30, 25), ("recent_ray", 30, 20)]
    assert board(window="all", league=" NFL ") == [("recent_ray", 30, 0)]
    assert board(window="30d", league="nfl") == [] and board(league="nhl") == []
    bad = client.get("/v1/community/leaderboard", params={"window": "7d"}, headers=viewer)
    assert bad.status_code == 422
    assert client.get("/v1/community/leaderboard").status_code == 401
