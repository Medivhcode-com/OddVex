"""Audit finding api-data#1: a moderation decision sticks.

An author cannot clear a moderator's decision on their own content. An edited profile that
moderators hid or removed stays moderated and goes back to the report queue; only an
administrator restores content; and the queue shows how often an author's content was
hidden or removed before, so a repeat offender can be suspended.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from .community_support import (
    COMMUNITY_APP,
    Headers,
    audit_rows,
    code,
    enable,
    feed,
    member,
    post_pick,
    upcoming,
    user_id,
)
from .conftest import AppFactory, set_flag
from .fakes import ControlledProvider
from .test_api_community_moderation import queue, report, resolve

PICKS = "/v1/community/picks"
PROFILE = "/v1/community/profile"
RESTORE = "/v1/admin/community/restore"


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


def save_profile(client: TestClient, who: Headers, handle: str, bio: str | None) -> Any:
    response = client.put(
        PROFILE, json={"handle": handle, "bio": bio, "is_public": True}, headers=who
    )
    assert response.status_code == 200, response.text
    return response.json()


def restore(
    client: TestClient, admin: Headers, target_type: str, target_id: str, **extra: Any
) -> Any:
    body = {"target_type": target_type, "target_id": target_id, "note": "Fine after review"}
    return client.post(RESTORE, json={**body, **extra}, headers=admin)


# ------------------------------------------------------------- profile edits
@pytest.mark.parametrize(
    ("action", "status"), [("hide_content", "hidden"), ("remove_content", "removed")]
)
def test_an_author_edit_does_not_clear_a_moderated_profile(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, action: str, status: str
) -> None:
    decided = report(client, mara, "profile", "sample_sam", reason="harassment")
    assert resolve(client, admin, decided, action).status_code == 200
    assert queue(client, admin)["total"] == 0

    # One character added to the bio: saved, but still moderated and still not public.
    edited = save_profile(client, sam, "sample_sam", "Totals, mostly!")
    assert (edited["moderation_status"], edited["can_post"], edited["bio"]) == (status, False, None)
    assert client.get("/v1/community/profiles/sample_sam", headers=mara).status_code == 404
    blocked = client.post(
        PICKS, json={"event_id": "x", "market": "moneyline", "outcome_key": "home"}, headers=sam
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["details"] == {"reason": "profile_moderated"}

    # The edit is back in the queue, as an entry that says what happened.
    (entry,) = queue(client, admin)["items"]
    sam_id = user_id(client, sam)
    assert entry["author_edit"] is True
    assert (entry["target_type"], entry["target_id"], entry["reason"]) == (
        "profile",
        "sample_sam",
        "other",
    )
    assert entry["details"] == (
        "The author edited this profile after moderators hid or removed it. Restore it if "
        "the new handle and bio follow the guidelines."
    )
    assert entry["author"]["user_id"] == entry["reporter"]["user_id"] == sam_id
    assert (entry["target_text"], entry["target_moderation_status"]) == ("Totals, mostly!", status)
    assert (entry["reported_text"], entry["reported_summary"]) == ("Totals, mostly!", "@sample_sam")
    assert entry["author_earlier_removals"] == 1

    # Changing the bio back, or again, keeps it moderated and refreshes the one entry.
    again = save_profile(client, sam, "sam_renamed", "Totals, mostly.")
    assert (again["moderation_status"], again["can_post"]) == (status, False)
    (refreshed,) = queue(client, admin)["items"]
    assert refreshed["id"] == entry["id"]
    assert (refreshed["reported_text"], refreshed["reported_summary"]) == (
        "Totals, mostly.",
        "@sam_renamed",
    )
    assert client.get("/v1/community/profiles/sam_renamed", headers=mara).status_code == 404
    # Saving the same content (only the visibility switch) opens nothing new.
    client.put(
        PROFILE,
        json={"handle": "sam_renamed", "bio": "Totals, mostly.", "is_public": False},
        headers=sam,
    )
    assert queue(client, admin)["total"] == 1

    update = audit_rows(client, "community.profile_updated")[-2]
    assert update.details["moderation_status"] == status
    assert update.details["review_report_id"] == entry["id"]


def test_the_review_entry_is_in_the_authors_export_without_the_decision(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers
) -> None:
    decided = report(client, mara, "profile", "sample_sam")
    assert resolve(client, admin, decided, "remove_content").status_code == 200
    save_profile(client, sam, "sample_sam", "A new bio.")
    (entry,) = queue(client, admin)["items"]
    (exported,) = client.get("/v1/me/export", headers=sam).json()["community"]["reports"]
    assert exported == {
        "id": entry["id"],
        "target_type": "profile",
        "target_id": "sample_sam",
        "reason": "other",
        "details": entry["details"],
        "status": "open",
        "created_at": exported["created_at"],
    }
    # Who reported the profile is still not shown to its author.
    assert user_id(client, mara) not in str(exported) and decided != exported["id"]


def test_restoring_the_edited_profile_closes_its_review_entry(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers
) -> None:
    decided = report(client, mara, "profile", "sample_sam")
    assert resolve(client, admin, decided, "remove_content").status_code == 200
    save_profile(client, sam, "sample_sam", "A new bio.")
    (entry,) = queue(client, admin)["items"]

    restored = restore(client, admin, "profile", "sample_sam")
    assert restored.status_code == 200, restored.text
    assert restored.json() == {
        "target_type": "profile",
        "target_id": "sample_sam",
        "moderation_status": "visible",
        "reports_closed": 1,
    }
    assert queue(client, admin)["total"] == 0
    closed = {r["id"]: r for r in queue(client, admin, status="resolved")["items"]}
    assert closed[entry["id"]]["resolution_action"] == "restore_content"
    assert closed[entry["id"]]["resolution_note"] == "Fine after review"
    own = client.get(PROFILE, headers=sam).json()
    assert (own["moderation_status"], own["can_post"], own["bio"]) == (
        "visible",
        True,
        "A new bio.",
    )
    assert (
        client.get("/v1/community/profiles/sample_sam", headers=mara).json()["bio"] == "A new bio."
    )


# ------------------------------------------------------------------- restore
def test_an_administrator_restores_a_pick_a_comment_and_a_profile(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    pick = post_pick(client, sam, upcoming(world), analysis="Research only.")
    comment = client.post(
        f"{PICKS}/{pick['id']}/comments", json={"body": "by mara"}, headers=mara
    ).json()
    for target_type, target_id, who in (
        ("pick", pick["id"], mara),
        ("comment", comment["id"], sam),
        ("profile", "sample_sam", mara),
    ):
        decided = report(client, who, target_type, target_id)
        assert resolve(client, admin, decided, "hide_content").status_code == 200
    assert client.get(f"{PICKS}/{pick['id']}", headers=mara).status_code == 404

    restored = restore(client, admin, "comment", comment["id"], note="  Not harassment  ")
    assert restored.status_code == 200, restored.text
    assert restored.json()["reports_closed"] == 0  # the decision already closed its report
    assert restore(client, admin, "pick", pick["id"]).status_code == 200
    assert restore(client, admin, "profile", "sample_sam").status_code == 200

    shown = client.get(f"{PICKS}/{pick['id']}", headers=mara).json()
    assert (shown["analysis"], shown["moderation_status"]) == ("Research only.", "visible")
    comments = client.get(f"{PICKS}/{pick['id']}/comments", headers=sam).json()["items"]
    assert [(c["body"], c["moderation_status"]) for c in comments] == [("by mara", "visible")]
    assert client.get("/v1/community/profiles/sample_sam", headers=mara).status_code == 200
    assert [p["id"] for p in feed(client, mara)] == [pick["id"]]

    entries = audit_rows(client, "community.content_restored")
    assert [e.entity_type for e in entries] == [
        "community_comment",
        "community_pick",
        "community_profile",
    ]
    first = entries[0]
    assert (first.user_id, first.entity_id) == (user_id(client, admin), comment["id"])
    assert first.details == {
        "reason": "Not harassment",
        "target_type": "comment",
        "target_id": comment["id"],
        "target_user_id": user_id(client, mara),
        "before": {"moderation_status": "hidden"},
        "after": {"moderation_status": "visible"},
        "reports_closed": 0,
    }
    assert entries[2].entity_id == user_id(client, sam)


def test_restore_refusals(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    pick = post_pick(client, sam, upcoming(world))
    visible = restore(client, admin, "pick", pick["id"])
    assert visible.status_code == 409 and code(visible) == "content_not_moderated"
    missing = restore(client, admin, "comment", "nope")
    assert missing.status_code == 404
    assert restore(client, admin, "profile", "nobody_here").status_code == 404
    for body in (
        {"target_type": "pick", "target_id": pick["id"]},
        {"target_type": "pick", "target_id": pick["id"], "note": "  "},
        {"target_type": "event", "target_id": pick["id"], "note": "testing"},
    ):
        invalid = client.post(RESTORE, json=body, headers=admin)
        assert invalid.status_code == 422, body
    # Administrators only, and behind the flag like the other moderation routes.
    for who in ({}, sam, mara):
        refused = restore(client, who, "pick", pick["id"])
        assert refused.status_code in (401, 403)
    set_flag(client, admin, "community", False)
    off = restore(client, admin, "pick", pick["id"])
    assert off.status_code == 404 and code(off) == "feature_disabled"
    assert not audit_rows(client, "community.content_restored")


# ---------------------------------------------------- repeat offenders in the queue
def test_the_queue_counts_earlier_removals_of_the_author(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    nia = member(client, "notreal_nia")
    first = post_pick(client, sam, upcoming(world), analysis="Harassing text.")
    one = report(client, mara, "pick", first["id"])
    two = report(client, nia, "pick", first["id"])
    (row, _) = queue(client, admin)["items"]
    assert row["author_earlier_removals"] == 0
    # One decision closing two reports on one pick is one removal, and a decided report
    # does not count its own decision.
    decided = resolve(client, admin, one, "remove_content")
    assert decided.status_code == 200 and decided.json()["author_earlier_removals"] == 0
    resolved = {r["id"]: r for r in queue(client, admin, status="resolved")["items"]}
    assert resolved[one]["author_earlier_removals"] == resolved[two]["author_earlier_removals"] == 0

    # The author deletes the removed pick and posts the same text again: allowed, but the
    # report on the re-post shows the earlier removal.
    assert client.delete(f"{PICKS}/{first['id']}", headers=sam).status_code == 204
    again = post_pick(client, sam, upcoming(world), analysis="Harassing text.")
    comment = client.post(
        f"{PICKS}/{again['id']}/comments", json={"body": "mine"}, headers=sam
    ).json()
    dismissed = report(client, mara, "comment", comment["id"])
    assert resolve(client, admin, dismissed, "dismiss").status_code == 200  # not a removal
    hidden = report(client, mara, "comment", comment["id"])
    assert resolve(client, admin, hidden, "hide_content").status_code == 200
    latest = report(client, nia, "pick", again["id"])
    (row,) = queue(client, admin)["items"]
    assert (row["id"], row["author_earlier_removals"]) == (latest, 2)
    # Another author's queue row counts only that author's history.
    mara_pick = post_pick(client, mara, upcoming(world, index=1))
    other = report(client, nia, "pick", mara_pick["id"])
    counts = {r["id"]: r["author_earlier_removals"] for r in queue(client, admin)["items"]}
    assert counts == {latest: 2, other: 0}
