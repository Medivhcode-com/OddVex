"""Audit finding api-data#5: a report keeps a copy of what was reported.

The moderator judges the text as it was reported, even after its author deleted or edited
it. The copy is stored on the report row and goes when the report goes: with the
reporter's account or with the author's.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from oddvex_api.db import CommunityReport

from .community_support import (
    COMMUNITY_APP,
    Headers,
    enable,
    member,
    post_pick,
    upcoming,
    user_id,
)
from .conftest import AppFactory
from .fakes import ControlledProvider
from .test_api_community_moderation import queue, report, resolve

PICKS = "/v1/community/picks"
PROFILE = "/v1/community/profile"


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


def stored_reports(client: TestClient) -> list[CommunityReport]:
    with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
        return list(db.scalars(select(CommunityReport).order_by(CommunityReport.created_at)))


def test_a_deleted_comment_can_still_be_judged(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    pick = post_pick(client, sam, upcoming(world))
    comment = client.post(
        f"{PICKS}/{pick['id']}/comments", json={"body": "something unkind"}, headers=mara
    ).json()
    report_id = report(client, sam, "comment", comment["id"], reason="harassment")
    (before,) = queue(client, admin)["items"]
    assert (before["target_text"], before["reported_text"], before["reported_summary"]) == (
        "something unkind",
        "something unkind",
        None,
    )
    assert before["target_changed_since_report"] is False

    assert client.delete(f"/v1/community/comments/{comment['id']}", headers=mara).status_code == 204
    (row,) = queue(client, admin)["items"]
    # The live fields mean what they meant before; the copy is next to them.
    assert (row["target_exists"], row["target_text"], row["target_moderation_status"]) == (
        False,
        None,
        None,
    )
    assert row["reported_text"] == "something unkind"
    assert row["target_changed_since_report"] is True
    # The moderator can still act on the author.
    assert resolve(client, admin, report_id, "suspend_author").status_code == 200
    (decided,) = queue(client, admin, status="resolved")["items"]
    assert decided["reported_text"] == "something unkind"


def test_a_deleted_pick_and_a_pick_deleted_with_its_parent(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    pick = post_pick(client, sam, upcoming(world), analysis="Harassing analysis.")
    comment = client.post(
        f"{PICKS}/{pick['id']}/comments", json={"body": "an unkind reply"}, headers=mara
    ).json()
    on_pick = report(client, mara, "pick", pick["id"])
    on_comment = report(client, sam, "comment", comment["id"])
    # Deleting the pick deletes the comments on it as well.
    assert client.delete(f"{PICKS}/{pick['id']}", headers=sam).status_code == 204
    rows = {r["id"]: r for r in queue(client, admin)["items"]}
    assert rows[on_pick]["target_exists"] is False
    assert (rows[on_pick]["reported_text"], rows[on_pick]["reported_summary"]) == (
        "Harassing analysis.",
        f"{pick['selection']} ({pick['event_label']})",
    )
    assert rows[on_comment]["target_exists"] is False
    assert rows[on_comment]["reported_text"] == "an unkind reply"
    assert all(r["target_changed_since_report"] for r in rows.values())


def test_an_edited_profile_shows_both_versions(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers
) -> None:
    report(client, mara, "profile", "sample_sam", reason="harassment")
    edited = client.put(
        PROFILE,
        json={"handle": "quiet_sam", "bio": "Nothing to see.", "is_public": True},
        headers=sam,
    )
    assert edited.status_code == 200
    (row,) = queue(client, admin)["items"]
    assert (row["target_exists"], row["target_text"], row["target_summary"]) == (
        True,
        "Nothing to see.",
        "@quiet_sam",
    )
    assert (row["reported_text"], row["reported_summary"]) == ("Totals, mostly.", "@sample_sam")
    assert row["target_changed_since_report"] is True


def test_the_copy_is_not_shown_to_the_reporter(
    client: TestClient, admin: Headers, sam: Headers, mara: Headers, world: ControlledProvider
) -> None:
    pick = post_pick(client, sam, upcoming(world), analysis="Research only.")
    created = client.post(
        "/v1/community/reports",
        json={"target_type": "pick", "target_id": pick["id"], "reason": "spam"},
        headers=mara,
    )
    assert created.status_code == 201
    assert "Research only." not in created.text
    exported = client.get("/v1/me/export", headers=mara).json()["community"]["reports"]
    assert len(exported) == 1 and "Research only." not in str(exported)
    (stored,) = stored_reports(client)
    assert (stored.target_text_snapshot, stored.target_summary_snapshot) == (
        "Research only.",
        f"{pick['selection']} ({pick['event_label']})",
    )


@pytest.mark.parametrize("who", ["reporter", "author"])
@pytest.mark.parametrize("how", ["own", "admin"])
def test_the_copy_goes_with_the_reporters_or_the_authors_account(
    client: TestClient,
    admin: Headers,
    sam: Headers,
    mara: Headers,
    world: ControlledProvider,
    who: str,
    how: str,
) -> None:
    pick = post_pick(client, sam, upcoming(world), analysis="Text to judge.")
    report(client, mara, "pick", pick["id"])
    report(client, mara, "profile", "sample_sam")
    nia = member(client, "notreal_nia")
    kept = report(client, nia, "profile", "madeup_mara" if who == "author" else "sample_sam")
    assert len(stored_reports(client)) == 3

    leaving, email = (mara, "madeup_mara") if who == "reporter" else (sam, "sample_sam")
    if how == "own":
        assert client.delete("/v1/me", headers=leaving).status_code == 204
    else:
        gone = client.post(
            f"/v1/admin/users/{user_id(client, leaving)}/delete",
            json={"reason": "data request", "confirm_email": f"{email}@example.test"},
            headers=admin,
        )
        assert gone.status_code == 204, gone.text
    remaining = stored_reports(client)
    assert [r.id for r in remaining] == [kept]
    with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
        texts = db.scalars(select(CommunityReport.target_text_snapshot)).all()
        assert "Text to judge." not in texts
        assert db.scalar(select(func.count()).select_from(CommunityReport)) == 1
