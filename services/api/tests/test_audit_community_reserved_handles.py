"""Audit finding api-data#2: the handle of an account deleted while suspended stays taken.

A suspended member who deletes the account (or whose account an administrator deletes)
cannot come back under the same community handle. The refusal is the one a taken handle
gets, so it does not say why. Nothing about the email address is kept.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from oddvex_api.db import User
from oddvex_api.db.models import CommunityReservedHandle

from .community_support import COMMUNITY_APP, Headers, enable, member, user_id
from .conftest import AppFactory, auth_headers
from .fakes import ControlledProvider

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


def suspend(client: TestClient, admin: Headers, who: Headers) -> None:
    target = user_id(client, who)
    response = client.post(
        f"/v1/admin/users/{target}/suspend", json={"reason": "abusive"}, headers=admin
    )
    assert response.status_code == 200, response.text


def delete(client: TestClient, admin: Headers, who: Headers, handle: str, how: str) -> None:
    if how == "own":
        assert client.delete("/v1/me", headers=who).status_code == 204
        return
    with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
        target = db.scalar(select(User.id).where(User.email == f"{handle}@example.test"))
    response = client.post(
        f"/v1/admin/users/{target}/delete",
        json={"reason": "data request", "confirm_email": f"{handle}@example.test"},
        headers=admin,
    )
    assert response.status_code == 204, response.text


def claim(client: TestClient, who: Headers, handle: str) -> object:
    return client.put(PROFILE, json={"handle": handle, "is_public": True}, headers=who)


def reserved(client: TestClient) -> list[str]:
    with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
        return list(db.scalars(select(CommunityReservedHandle.handle)))


@pytest.mark.parametrize("how", ["own", "admin"])
def test_a_suspended_accounts_handle_stays_taken_after_deletion(
    client: TestClient, admin: Headers, how: str
) -> None:
    abuser = member(client, "rude_rex")
    holder = member(client, "taken_tia")
    # What a handle that is in use answers today, to compare with.
    newcomer = auth_headers(client, "newcomer@example.test")
    taken = claim(client, newcomer, "taken_tia")
    assert taken.status_code == 409  # type: ignore[attr-defined]

    suspend(client, admin, abuser)
    # "own": the suspended account still holds a token that works on DELETE /v1/me.
    delete(client, admin, abuser, "rude_rex", how)
    assert reserved(client) == ["rude_rex"]

    # The same email registers again (nothing about it was kept), but the handle is refused
    # with exactly the answer a handle in use gets, whatever the case typed.
    again = auth_headers(client, "rude_rex@example.test")
    for attempt in ("rude_rex", "RUDE_REX", "  Rude_Rex "):
        refused = claim(client, again, attempt)
        assert refused.status_code == 409, attempt  # type: ignore[attr-defined]
        assert refused.json() == taken.json()  # type: ignore[attr-defined]
    # Renaming an existing profile to it is refused the same way.
    renamed = claim(client, holder, "rude_rex")
    assert renamed.status_code == 409 and renamed.json() == taken.json()  # type: ignore[attr-defined]
    # Other handles are unaffected.
    assert claim(client, again, "rex_returns").status_code == 201  # type: ignore[attr-defined]


@pytest.mark.parametrize("how", ["own", "admin"])
def test_an_active_accounts_handle_is_free_after_deletion(
    client: TestClient, admin: Headers, how: str
) -> None:
    leaving = member(client, "leaving_lou")
    delete(client, admin, leaving, "leaving_lou", how)
    assert reserved(client) == []
    newcomer = auth_headers(client, "newcomer@example.test")
    assert claim(client, newcomer, "leaving_lou").status_code == 201  # type: ignore[attr-defined]


def test_a_suspended_account_without_a_profile_reserves_nothing(
    client: TestClient, admin: Headers
) -> None:
    quiet = auth_headers(client, "quiet@example.test")
    suspend(client, admin, quiet)
    assert client.delete("/v1/me", headers=quiet).status_code == 204
    assert reserved(client) == []


def test_only_the_handle_is_kept(client: TestClient, admin: Headers) -> None:
    abuser = member(client, "rude_rex", bio="unkind")
    suspend(client, admin, abuser)
    assert client.delete("/v1/me", headers=abuser).status_code == 204
    with client.app.state.session_factory() as db:  # type: ignore[attr-defined]
        columns = {
            c["name"] for c in inspect(db.get_bind()).get_columns("community_reserved_handles")
        }
        assert columns == {"handle", "reserved_at"}
        (row,) = db.scalars(select(CommunityReservedHandle))
        assert row.handle == "rude_rex" and row.reserved_at is not None
