"""Community moderation: the report queue, the four decisions and what each one does to
what people can read. Every decision is audited with actor, target and reason."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from oddvex_api.community.guidelines import MODERATED_PLACEHOLDER
from oddvex_api.db import CommunityReport, User

from .community_support import (
    COMMUNITY_APP,
    Headers,
    audit_rows,
    code,
    enable,
    feed,
    finish,
    member,
    post_pick,
    upcoming,
    user_id,
)
from .conftest import ADMIN_EMAIL, PASSWORD, AppFactory, admin_headers, auth_headers, set_flag
from .fakes import ControlledProvider

PICKS = "/v1/community/picks"
PROFILE = "/v1/community/profile"
REPORTS = "/v1/admin/community/reports"
ADMIN_COMMUNITY_CALLS: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", "/v1/admin/community/overview", None),
    ("GET", REPORTS, None),
    ("POST", f"{REPORTS}/{{id}}/resolve", {"action": "dismiss", "note": "testing"}),
    (
        "POST",
        "/v1/admin/community/restore",
        {"target_type": "profile", "target_id": "madeup_mara", "note": "testing"},
    ),
]


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
    return member(client, "sample_sam", bio="Totals, mostly.")


@pytest.fixture
def mara(client: TestClient, admin: Headers) -> Headers:
    return member(client, "madeup_mara")


def report(client: TestClient, who: Headers, target_type: str, target_id: str, **extra: Any) -> str:
    response = client.post(
        "/v1/community/reports",
        json={"target_type": target_type, "target_id": target_id, "reason": "spam", **extra},
        headers=who,
    )
    assert response.status_code in (200, 201), response.text
    return str(response.json()["id"])


def resolve(client: TestClient, admin: Headers, report_id: str, action: str, note: str = "") -> Any:
    return client.post(
        f"{REPORTS}/{report_id}/resolve",
        json={"action": action, "note": note or f"decided: {action}"},
        headers=admin,
    )


def queue(client: TestClient, admin: Headers, **params: Any) -> dict[str, Any]:
    response = client.get(REPORTS, params=params, headers=admin)
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


# ---------------------------------------------------------------------- authz
def test_moderation_is_for_administrators_only(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    pick = post_pick(client, sam, upcoming(world))
    report_id = report(client, mara, "pick", pick["id"])
    for method, template, body in ADMIN_COMMUNITY_CALLS:
        path = template.replace("{id}", report_id)
        anonymous = client.request(method, path, json=body)
        assert anonymous.status_code == 401, path
        assert code(anonymous) == "not_authenticated"
        # Neither the reporter nor the reported person can read or decide a report.
        for who in (sam, mara):
            forbidden = client.request(method, path, json=body, headers=who)
            assert forbidden.status_code == 403, path
            assert forbidden.json() == {
                "error": {"code": "forbidden", "message": "Administrator role required"}
            }
    # Nothing they tried had any effect.
    with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
        stored = db.get(CommunityReport, report_id)
        assert (stored.status, stored.resolved_by, stored.resolution_action) == ("open", None, None)
    assert client.get(f"{PICKS}/{pick['id']}", headers=mara).status_code == 200
    assert not audit_rows(client, "community.report_resolved")
    assert not audit_rows(client, "community.content_restored")
    assert not audit_rows(client, "admin.read")


def test_moderation_routes_are_behind_the_flag_too(
    client: TestClient, admin: Headers, sam: Headers
) -> None:
    set_flag(client, admin, "community", False)
    for method, template, body in ADMIN_COMMUNITY_CALLS:
        for who in ({}, sam, admin):
            response = client.request(method, template.replace("{id}", "x"), json=body, headers=who)
            assert response.status_code == 404, template
            assert code(response) == "feature_disabled"


# ---------------------------------------------------------------------- queue
def test_the_queue_shows_what_was_reported_by_whom(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    assert queue(client, admin) == {"items": [], "total": 0, "limit": 50, "offset": 0}
    pick = post_pick(client, sam, upcoming(world), analysis="Research only.")
    comment = client.post(
        f"{PICKS}/{pick['id']}/comments", json={"body": "my own take"}, headers=sam
    ).json()
    world.advance(minutes=1)
    first = report(client, mara, "pick", pick["id"], reason="misleading_claims", details="why")
    world.advance(minutes=1)
    second = report(client, mara, "comment", comment["id"], reason="harassment")
    world.advance(minutes=1)
    third = report(client, mara, "profile", "sample_sam", reason="other")

    listed = queue(client, admin)
    assert (listed["total"], [r["id"] for r in listed["items"]]) == (3, [first, second, third])
    sam_id, mara_id = user_id(client, sam), user_id(client, mara)
    on_pick, on_comment, on_profile = listed["items"]
    assert on_pick == {
        "id": first,
        "status": "open",
        "created_at": on_pick["created_at"],
        "reason": "misleading_claims",
        "details": "why",
        "target_type": "pick",
        "target_id": pick["id"],
        "target_exists": True,
        "target_text": "Research only.",
        "target_summary": f"{pick['selection']} ({pick['event_label']})",
        "target_moderation_status": "visible",
        "reported_text": "Research only.",
        "reported_summary": f"{pick['selection']} ({pick['event_label']})",
        "target_changed_since_report": False,
        "author_edit": False,
        "author_earlier_removals": 0,
        "author": {"user_id": sam_id, "handle": "sample_sam", "status": "active"},
        "reporter": {"user_id": mara_id, "handle": "madeup_mara", "status": "active"},
        "resolved_at": None,
        "resolved_by": None,
        "resolution_action": None,
        "resolution_note": None,
    }
    assert (on_comment["target_text"], on_comment["target_summary"]) == ("my own take", None)
    assert (on_profile["target_text"], on_profile["target_summary"]) == (
        "Totals, mostly.",
        "@sample_sam",
    )
    # No email address, password hash or token in the queue.
    text = str(listed).lower()
    assert "example.test" not in text and "password" not in text and "token" not in text

    assert [r["id"] for r in queue(client, admin, limit=1, offset=1)["items"]] == [second]
    assert queue(client, admin, status="resolved")["items"] == []
    assert client.get(REPORTS, params={"status": "closed"}, headers=admin).status_code == 422
    # Reading the queue is audited, coarsely.
    reads = audit_rows(client, "admin.read")
    assert {r.entity_type for r in reads} == {"admin_community_reports"}
    assert all(r.details is None and r.user_id == user_id(client, admin) for r in reads)


def test_overview_counts(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    def overview() -> dict[str, int]:
        response = client.get("/v1/admin/community/overview", headers=admin)
        assert response.status_code == 200, response.text
        return response.json()  # type: ignore[no-any-return]

    assert overview() == {
        "profiles": 2,
        "public_profiles": 2,
        "picks": 0,
        "graded_picks": 0,
        "comments": 0,
        "open_reports": 0,
        "hidden_or_removed_items": 0,
    }
    member(client, "private_pat", is_public=False)
    event, later = upcoming(world), upcoming(world, index=1)
    first = post_pick(client, sam, event)
    post_pick(client, mara, later)
    client.post(f"{PICKS}/{first['id']}/comments", json={"body": "one"}, headers=mara)
    report_id = report(client, mara, "pick", first["id"])
    finish(world, event, 100, 90)
    feed(client, sam)
    assert overview() == {
        "profiles": 3,
        "public_profiles": 2,
        "picks": 2,
        "graded_picks": 1,
        "comments": 1,
        "open_reports": 1,
        "hidden_or_removed_items": 0,
    }
    assert resolve(client, admin, report_id, "hide_content").status_code == 200
    after = overview()
    assert (after["open_reports"], after["hidden_or_removed_items"], after["picks"]) == (0, 1, 2)


# ------------------------------------------------------------------ decisions
def test_dismiss_changes_nothing_but_the_report(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    pick = post_pick(client, sam, upcoming(world), analysis="Research only.")
    nia = member(client, "notreal_nia")
    mine = report(client, mara, "pick", pick["id"])
    other = report(client, nia, "pick", pick["id"])

    dismissed = resolve(client, admin, mine, "dismiss", "  Nothing wrong with it  ")
    assert dismissed.status_code == 200, dismissed.text
    body = dismissed.json()
    assert (body["status"], body["resolution_action"], body["resolution_note"]) == (
        "resolved",
        "dismiss",
        "Nothing wrong with it",
    )
    assert body["resolved_by"] == user_id(client, admin) and body["resolved_at"]
    assert body["target_moderation_status"] == "visible"
    assert client.get(f"{PICKS}/{pick['id']}", headers=mara).json()["analysis"] == "Research only."
    # Someone else's report on the same pick stays open: a dismissal is per report.
    assert [r["id"] for r in queue(client, admin)["items"]] == [other]
    assert [r["id"] for r in queue(client, admin, status="resolved")["items"]] == [mine]

    again = resolve(client, admin, mine, "hide_content")
    assert again.status_code == 409 and code(again) == "report_already_resolved"
    assert resolve(client, admin, "nope", "dismiss").status_code == 404
    # The reporter can report it again later; that is a new report.
    assert report(client, mara, "pick", pick["id"]) != mine

    (entry,) = audit_rows(client, "community.report_resolved")
    assert (entry.user_id, entry.entity_type, entry.entity_id) == (
        user_id(client, admin),
        "community_report",
        mine,
    )
    assert entry.details == {
        "action": "dismiss",
        "reason": "Nothing wrong with it",
        "report_reason": "spam",
        "target_type": "pick",
        "target_id": pick["id"],
        "target_user_id": user_id(client, sam),
        "reports_closed": 1,
    }


@pytest.mark.parametrize(
    ("action", "status"), [("hide_content", "hidden"), ("remove_content", "removed")]
)
def test_a_hidden_or_removed_pick_disappears_from_every_public_read(
    client: TestClient,
    admin: Headers,
    sam: Headers,
    mara: Headers,
    world: ControlledProvider,
    action: str,
    status: str,
) -> None:
    event = upcoming(world)
    pick = post_pick(client, sam, event, analysis="Borderline text.")
    kept = post_pick(client, sam, upcoming(world, index=1))
    nia = member(client, "notreal_nia")
    client.post("/v1/community/follows/sample_sam", headers=mara)
    client.post(f"{PICKS}/{pick['id']}/comments", json={"body": "a comment"}, headers=mara)
    client.put(f"{PICKS}/{pick['id']}/like", headers=mara)
    first = report(client, mara, "pick", pick["id"])
    second = report(client, nia, "pick", pick["id"])

    resolved = resolve(client, admin, first, action, "Breaks the guidelines")
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["target_moderation_status"] == status
    # Every open report on the same pick is closed by the one decision.
    assert queue(client, admin)["total"] == 0
    closed = {r["id"]: r for r in queue(client, admin, status="resolved")["items"]}
    assert set(closed) == {first, second}
    assert {r["resolution_action"] for r in closed.values()} == {action}

    # Gone for everyone else, wherever they look.
    for viewer in (mara, nia, admin):
        assert client.get(f"{PICKS}/{pick['id']}", headers=viewer).status_code == 404
        assert client.get(f"{PICKS}/{pick['id']}/comments", headers=viewer).status_code == 404
        assert [p["id"] for p in feed(client, viewer)] == [kept["id"]]
        listed = client.get(PICKS, params={"handle": "sample_sam"}, headers=viewer).json()
        assert [p["id"] for p in listed["items"]] == [kept["id"]]
        by_event = client.get(PICKS, params={"event_id": event.id}, headers=viewer).json()
        assert by_event["items"] == []
    assert [p["id"] for p in feed(client, mara, "following")] == [kept["id"]]
    assert client.put(f"{PICKS}/{pick['id']}/like", headers=mara).status_code == 404
    assert (
        client.post(f"{PICKS}/{pick['id']}/comments", json={"body": "x"}, headers=mara).status_code
        == 404
    )
    assert report_again(client, mara, pick["id"]) == 404

    # The author still sees the item, with a placeholder instead of the text.
    own = client.get(f"{PICKS}/{pick['id']}", headers=sam)
    assert own.status_code == 200
    assert (
        own.json()["moderation_status"],
        own.json()["moderation_note"],
        own.json()["analysis"],
    ) == (
        status,
        MODERATED_PLACEHOLDER,
        None,
    )
    assert MODERATED_PLACEHOLDER == "Removed by moderators."
    assert {p["id"]: p["moderation_status"] for p in feed(client, sam)} == {
        pick["id"]: status,
        kept["id"]: "visible",
    }
    # Nobody can comment on it or like it any more, the author included.
    assert client.put(f"{PICKS}/{pick['id']}/like", headers=sam).status_code == 404
    assert (
        client.post(f"{PICKS}/{pick['id']}/comments", json={"body": "x"}, headers=sam).status_code
        == 404
    )
    # A moderated pick cannot be made to vanish from the record: it is still graded.
    finish(world, event, 100, 90)
    assert client.get(f"{PICKS}/{pick['id']}", headers=sam).json()["result"] == "won"
    record = client.get("/v1/community/profiles/sample_sam", headers=mara).json()["record"]
    assert (record["picks"], record["wins"]) == (1, 1)

    (entry,) = audit_rows(client, "community.report_resolved")
    assert entry.details == {
        "action": action,
        "reason": "Breaks the guidelines",
        "report_reason": "spam",
        "target_type": "pick",
        "target_id": pick["id"],
        "target_user_id": user_id(client, sam),
        "before": {"moderation_status": "visible"},
        "after": {"moderation_status": status},
        "reports_closed": 2,
    }
    assert entry.user_id == user_id(client, admin) and entry.request_id


def report_again(client: TestClient, who: Headers, pick_id: str) -> int:
    return client.post(
        "/v1/community/reports",
        json={"target_type": "pick", "target_id": pick_id, "reason": "spam"},
        headers=who,
    ).status_code


def test_a_removed_comment_is_gone_for_others_and_a_placeholder_for_its_author(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    pick = post_pick(client, sam, upcoming(world))
    url = f"{PICKS}/{pick['id']}/comments"
    bad = client.post(url, json={"body": "something unkind"}, headers=mara).json()
    world.advance(minutes=1)
    good = client.post(url, json={"body": "something fine"}, headers=mara).json()
    report_id = report(client, sam, "comment", bad["id"], reason="harassment")

    assert resolve(client, admin, report_id, "remove_content").status_code == 200
    for viewer in (sam, admin):
        items = client.get(url, headers=viewer).json()["items"]
        assert [c["id"] for c in items] == [good["id"]]
    assert client.get(f"{PICKS}/{pick['id']}", headers=sam).json()["comment_count"] == 1
    mine = client.get(url, headers=mara).json()["items"]
    assert [c["id"] for c in mine] == [good["id"], bad["id"]]
    assert mine[1] == {
        **bad,
        "body": None,
        "moderation_status": "removed",
        "moderation_note": "Removed by moderators.",
    }
    assert "something unkind" not in client.get(url, headers=mara).text
    # The export still has the row, without the removed text.
    exported = client.get("/v1/me/export", headers=mara).json()["community"]["comments"]
    assert [c["body"] for c in exported] == [None, "something fine"]
    # The author can still delete their own removed comment; the report keeps its copy.
    assert client.delete(f"/v1/community/comments/{bad['id']}", headers=mara).status_code == 204
    resolved = queue(client, admin, status="resolved")["items"][0]
    assert (resolved["target_exists"], resolved["target_text"]) == (False, None)
    assert resolved["reported_text"] == "something unkind"


def test_a_hidden_profile_stays_hidden_when_its_owner_replaces_the_content(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    pick = post_pick(client, sam, upcoming(world))
    client.post("/v1/community/follows/sample_sam", headers=mara)
    report_id = report(client, mara, "profile", "sample_sam", reason="other")
    resolved = resolve(client, admin, report_id, "hide_content", "Bio breaks the rules")
    assert resolved.status_code == 200 and resolved.json()["target_moderation_status"] == "hidden"

    assert client.get("/v1/community/profiles/sample_sam", headers=mara).status_code == 404
    assert client.get(f"{PICKS}/{pick['id']}", headers=mara).status_code == 404
    assert feed(client, mara) == [] and feed(client, mara, "following") == []
    assert client.get(PROFILE, headers=mara).json()["following_count"] == 0
    own = client.get(PROFILE, headers=sam).json()
    assert (own["moderation_status"], own["moderation_note"], own["bio"], own["can_post"]) == (
        "hidden",
        "Removed by moderators.",
        None,
        False,
    )
    blocked = client.post(
        PICKS,
        json={
            "event_id": upcoming(world, index=1).id,
            "market": "moneyline",
            "outcome_key": "home",
        },
        headers=sam,
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["details"] == {"reason": "profile_moderated"}

    # Saving the same content again changes nothing. Replacing it does not bring it back
    # either: the edit is saved and goes to the moderators, who alone can restore it.
    same = client.put(
        PROFILE,
        json={"handle": "sample_sam", "bio": "Totals, mostly.", "is_public": True},
        headers=sam,
    )
    assert same.status_code == 200 and same.json()["moderation_status"] == "hidden"
    assert client.get("/v1/community/profiles/sample_sam", headers=mara).status_code == 404
    assert queue(client, admin)["total"] == 0
    replaced = client.put(
        PROFILE, json={"handle": "sample_sam", "bio": "A new bio.", "is_public": True}, headers=sam
    )
    assert replaced.json()["moderation_status"] == "hidden" and replaced.json()["can_post"] is False
    assert client.get("/v1/community/profiles/sample_sam", headers=mara).status_code == 404
    (entry,) = queue(client, admin)["items"]
    assert entry["author_edit"] is True and entry["target_text"] == "A new bio."
    restored = client.post(
        "/v1/admin/community/restore",
        json={"target_type": "profile", "target_id": "sample_sam", "note": "New bio is fine"},
        headers=admin,
    )
    assert restored.status_code == 200, restored.text
    assert (
        client.get("/v1/community/profiles/sample_sam", headers=mara).json()["bio"] == "A new bio."
    )
    assert len(feed(client, mara)) == 1
    updates = audit_rows(client, "community.profile_updated")
    assert updates[-1].details["moderation_status"] == "hidden"
    assert updates[-1].details["review_report_id"] == entry["id"]


def test_suspend_author_reuses_the_account_suspension(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    pick = post_pick(client, sam, upcoming(world), analysis="Research only.")
    client.post(f"{PICKS}/{pick['id']}/comments", json={"body": "by sam"}, headers=sam)
    report_id = report(client, mara, "pick", pick["id"], reason="inducement_to_bet")
    sam_id = user_id(client, sam)

    resolved = resolve(client, admin, report_id, "suspend_author", "Repeated inducement")
    assert resolved.status_code == 200, resolved.text
    body = resolved.json()
    assert (body["resolution_action"], body["author"]["status"]) == ("suspend_author", "suspended")
    assert body["target_moderation_status"] == "visible"  # the account, not the item

    # Exactly the existing suspension: tokens rejected, login refused, data kept.
    rejected = client.get("/v1/me", headers=sam)
    assert rejected.status_code == 401 and code(rejected) == "account_suspended"
    login = client.post(
        "/v1/auth/login", json={"email": "sample_sam@example.test", "password": PASSWORD}
    )
    assert login.status_code == 403 and code(login) == "account_suspended"
    listed = client.get("/v1/admin/users", params={"status": "suspended"}, headers=admin).json()
    assert [u["id"] for u in listed["items"]] == [sam_id]
    # Everything they posted is out of every read.
    assert client.get(f"{PICKS}/{pick['id']}", headers=mara).status_code == 404
    assert feed(client, mara) == []
    assert client.get("/v1/community/profiles/sample_sam", headers=mara).status_code == 404

    (suspended,) = audit_rows(client, "admin.user_suspended")
    assert (suspended.user_id, suspended.entity_id) == (user_id(client, admin), sam_id)
    assert suspended.details == {
        "before": {"status": "active"},
        "after": {"status": "suspended"},
        "reason": "Repeated inducement",
        "report_id": report_id,
    }
    (decision,) = audit_rows(client, "community.report_resolved")
    assert decision.details["action"] == "suspend_author"
    assert decision.details["suspended"] is True
    assert decision.details["target_user_id"] == sam_id
    assert decision.details["reason"] == "Repeated inducement"

    # Lifting the suspension the usual way brings the content back.
    assert client.post(f"/v1/admin/users/{sam_id}/unsuspend", headers=admin).status_code == 200
    assert client.get(f"{PICKS}/{pick['id']}", headers=mara).status_code == 200


def test_an_administrator_cannot_be_suspended_through_a_report(
    make_app: AppFactory, world: ControlledProvider
) -> None:
    app = make_app(
        provider=world, **{**COMMUNITY_APP, "admin_emails": f"{ADMIN_EMAIL},chief@example.test"}
    )
    with TestClient(app) as client:
        boss = enable(client)
        chief = admin_headers(client, "chief@example.test")
        created = client.put(PROFILE, json={"handle": "chief_c", "is_public": True}, headers=chief)
        assert created.status_code == 201
        reporter = auth_headers(client, "reporter@example.test")
        report_id = report(client, reporter, "profile", "chief_c")
        refused = resolve(client, boss, report_id, "suspend_author")
        assert refused.status_code == 409 and code(refused) == "cannot_suspend_admin"
        # Nothing was saved: the report is still open and nothing was audited.
        assert queue(client, boss)["total"] == 1
        assert not audit_rows(client, "community.report_resolved")
        assert not audit_rows(client, "admin.user_suspended")
        with app.state.session_factory() as db:
            assert {u.status for u in db.scalars(select(User))} == {"active"}
        assert client.get("/v1/me", headers=chief).status_code == 200
        # The other decisions still work on an administrator's content.
        assert resolve(client, boss, report_id, "hide_content").status_code == 200


def test_resolve_validation(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    pick = post_pick(client, sam, upcoming(world))
    report_id = report(client, mara, "pick", pick["id"])
    url = f"{REPORTS}/{report_id}/resolve"
    for body in (
        {"action": "dismiss"},  # a note is required: every decision carries its reason
        {"action": "dismiss", "note": ""},
        {"action": "dismiss", "note": "ab"},
        {"action": "dismiss", "note": "   "},
        {"action": "dismiss", "note": "x" * 501},
        {"action": "ban_forever", "note": "testing"},
        {"note": "testing"},
        {"action": "dismiss", "note": "testing", "resolved_by": "someone"},
    ):
        invalid = client.post(url, json=body, headers=admin)
        assert invalid.status_code == 422 and code(invalid) == "validation_error", body
    assert queue(client, admin)["total"] == 1
    assert not audit_rows(client, "community.report_resolved")


def test_a_decision_on_content_that_was_deleted_meanwhile(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    pick = post_pick(client, sam, upcoming(world))
    report_id = report(client, mara, "pick", pick["id"])
    assert client.delete(f"{PICKS}/{pick['id']}", headers=sam).status_code == 204
    (row,) = queue(client, admin)["items"]
    assert (row["target_exists"], row["target_text"], row["target_moderation_status"]) == (
        False,
        None,
        None,
    )
    resolved = resolve(client, admin, report_id, "remove_content")
    assert resolved.status_code == 200
    (entry,) = audit_rows(client, "community.report_resolved")
    assert entry.details["before"] == entry.details["after"] == {"moderation_status": None}
