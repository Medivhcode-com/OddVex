"""Helpers shared by the community tests: a controllable world, members and picks."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from oddvex_api.db import AuditLog, CommunityPick, CommunityProfile, User
from oddvex_api.providers import Event

from .conftest import ADMIN_EMAIL, admin_headers, auth_headers, set_flag
from .fakes import ControlledProvider, Quote, moneyline, spread, total

Headers = dict[str, str]
#: Settings for an app whose community the tests control completely.
COMMUNITY_APP: dict[str, Any] = {"admin_emails": ADMIN_EMAIL, "community_grade_min_seconds": 0}


def enable(client: TestClient, *, leaderboard: bool = False) -> Headers:
    """Turn the community on through the admin route. Returns the admin's headers."""
    admin = admin_headers(client)
    set_flag(client, admin, "community", True)
    if leaderboard:
        set_flag(client, admin, "community_leaderboard", True)
    return admin


def member(
    client: TestClient,
    handle: str,
    *,
    is_public: bool = True,
    bio: str | None = None,
    email: str | None = None,
) -> Headers:
    """Register an account and give it a community profile."""
    headers = auth_headers(client, email or f"{handle}@example.test")
    response = client.put(
        "/v1/community/profile",
        json={"handle": handle, "bio": bio, "is_public": is_public},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return headers


def user_id(client: TestClient, headers: Headers) -> str:
    return str(client.get("/v1/me", headers=headers).json()["id"])


def fresh(book: str, outcomes: list[tuple[str, float | None, int]], age: float = 10.0) -> Quote:
    return (book, "open", age, outcomes)


def upcoming(world: ControlledProvider, league: str = "nba", index: int = 0) -> Event:
    return world.list_events(league=league, status="upcoming")[index]


def priced(world: ControlledProvider, event: Event) -> None:
    """Simple, known quotes on every market: -110 both ways at two books, on -3.5 and 200.5."""
    world.set_odds(
        event.id,
        "moneyline",
        [fresh("northline", moneyline(-120, 100)), fresh("cardinal", moneyline(-115, -105))],
    )
    if "spread" in event.markets:
        world.set_odds(
            event.id,
            "spread",
            [fresh("northline", spread(-3.5)), fresh("cardinal", spread(-3.5, -108, -112))],
        )
    world.set_odds(
        event.id,
        "total",
        [fresh("northline", total(200.5)), fresh("cardinal", total(200.5, -105, -115))],
    )


def post_pick(
    client: TestClient,
    headers: Headers,
    event: Event,
    market: str = "moneyline",
    outcome: str = "home",
    line: float | None = None,
    analysis: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"event_id": event.id, "market": market, "outcome_key": outcome}
    if line is not None:
        body["line"] = line
    if analysis is not None:
        body["analysis"] = analysis
    response = client.post("/v1/community/picks", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def finish(world: ControlledProvider, event: Event, home: int, away: int) -> None:
    """Move the clock past the start of ``event`` and make it final with this score."""
    if world.current <= event.start_time:
        world.current = event.start_time + timedelta(hours=4)
    world.finish(event.id, home, away)


def feed(client: TestClient, headers: Headers, scope: str = "everyone") -> list[dict[str, Any]]:
    response = client.get("/v1/community/feed", params={"scope": scope}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["items"]  # type: ignore[no-any-return]


def code(response: Any) -> str:
    return str(response.json()["error"]["code"])


def audit_actions(client: TestClient, prefix: str = "community.") -> list[str]:
    app: FastAPI = client.app  # type: ignore[assignment]
    with app.state.session_factory() as db:
        rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at, AuditLog.id))
        return [row.action for row in rows if row.action.startswith(prefix)]


def audit_rows(client: TestClient, action: str) -> list[AuditLog]:
    app: FastAPI = client.app  # type: ignore[assignment]
    with app.state.session_factory() as db:
        return list(
            db.scalars(
                select(AuditLog)
                .where(AuditLog.action == action)
                .order_by(AuditLog.created_at, AuditLog.id)
            )
        )


def insert_graded_picks(
    client: TestClient,
    handle: str,
    results: str,
    *,
    graded_at: datetime,
    league: str = "nba",
    price: str = "1.909091",
    prefix: str = "x",
) -> None:
    """Write graded picks straight into the database: ``results`` is a string of W, L and
    P. For record and leaderboard tests that need more picks than there are events."""
    app: FastAPI = client.app  # type: ignore[assignment]
    with app.state.session_factory() as db:
        owner = db.scalar(select(CommunityProfile).where(CommunityProfile.handle == handle))
        assert owner is not None, handle
        assert db.get(User, owner.user_id) is not None
        for index, letter in enumerate(results):
            db.add(
                CommunityPick(
                    user_id=owner.user_id,
                    event_id=f"evt_{prefix}_{handle}_{index}",
                    league=league,
                    event_label="Away at Home",
                    selection="Home moneyline",
                    event_start_time=graded_at - timedelta(hours=3),
                    market="moneyline",
                    outcome_key="home",
                    price_decimal=Decimal(price),
                    sportsbook_key="northline",
                    sportsbook_name="Northline",
                    posted_at=graded_at - timedelta(hours=6),
                    status="graded",
                    result={"W": "won", "L": "lost", "P": "push"}[letter],
                    graded_at=graded_at,
                    home_score=1,
                    away_score=0,
                )
            )
        db.commit()
