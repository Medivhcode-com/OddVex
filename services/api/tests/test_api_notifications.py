"""Notifications, preferences, the staking reminder, and the events that create them."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from oddvex_api.db import (
    AlertRule,
    AuditLog,
    Notification,
    NotificationPreference,
    StakeReminder,
    User,
)
from oddvex_api.notifications import service as notifications_service
from oddvex_api.notifications import templates
from oddvex_api.notifications.channels import InAppChannel, NotificationChannel
from oddvex_api.notifications.schemas import MAX_NOTIFICATIONS
from oddvex_api.sync import SyncRegistry
from oddvex_api.sync.base import ExternalBet, ExternalLeg, FetchResult, SyncProviderInfo

from .conftest import FROZEN_NOW, AppFactory, SettingsFactory, auth_headers
from .fakes import ControlledProvider, moneyline
from .test_notification_copy import BANNED_PHRASES
from .test_platform import assert_envelope

Headers = dict[str, str]
API_ROOT = Path(__file__).resolve().parents[1]
#: FROZEN_NOW is Saturday 2026-03-14; its ISO week starts on Monday the 9th.
WEEK_START = datetime(2026, 3, 9, tzinfo=UTC)


@pytest.fixture
def world() -> ControlledProvider:
    return ControlledProvider()


@pytest.fixture
def app(make_app: AppFactory, world: ControlledProvider) -> FastAPI:
    return make_app(provider=world, alert_eval_min_seconds=0)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def user_id(client: TestClient, headers: Headers) -> str:
    return str(client.get("/v1/me", headers=headers).json()["id"])


def listing(client: TestClient, headers: Headers, **params: Any) -> dict[str, Any]:
    response = client.get("/v1/notifications", params=params, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"items", "unread_count", "next_before"}
    return body


def unread(client: TestClient, headers: Headers) -> int:
    response = client.get("/v1/notifications/unread-count", headers=headers)
    assert response.status_code == 200, response.text
    assert set(response.json()) == {"unread_count"}
    return int(response.json()["unread_count"])


def seed_notifications(app: FastAPI, owner: str, count: int, prefix: str = "n") -> list[str]:
    """``count`` notifications for ``owner``, oldest first, one second apart."""
    ids = []
    with app.state.session_factory() as db:
        for index in range(count):
            row = Notification(
                user_id=owner,
                kind="game_final",
                title=f"Final: A {index}, B 0",
                body=f"Final score: A {index}, B 0.",
                href="/app/games/evt_x",
                data={"event_id": "evt_x", "n": index},
                dedupe_key=f"{prefix}:{index}",
                created_at=FROZEN_NOW + timedelta(seconds=index),
            )
            db.add(row)
            db.flush()
            ids.append(row.id)
        db.commit()
    return ids


def bet_body(stake: float, placed_at: datetime | None = None, **extra: Any) -> dict[str, Any]:
    return {
        "bet_type": "straight",
        "stake": stake,
        "sportsbook": "Northline",
        "legs": [{"selection": "Tides ML", "market": "moneyline", "odds": -110}],
        "placed_at": (placed_at or FROZEN_NOW).isoformat(),
        **extra,
    }


def place(client: TestClient, headers: Headers, stake: float, **extra: Any) -> dict[str, Any]:
    response = client.post("/v1/bets", json=bet_body(stake, **extra), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def set_reminder(client: TestClient, headers: Headers, threshold: float | None) -> dict[str, Any]:
    response = client.put(
        "/v1/me/stake-reminder", json={"weekly_stake_threshold": threshold}, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


def reminders(client: TestClient, headers: Headers) -> list[dict[str, Any]]:
    return [n for n in listing(client, headers)["items"] if n["kind"] == "stake_reminder"]


# ---------------------------------------------------------------------- lists
def test_list_is_newest_first_with_unread_filter_and_cursor_paging(
    client: TestClient, headers: Headers, app: FastAPI
) -> None:
    assert listing(client, headers) == {"items": [], "unread_count": 0, "next_before": None}
    ids = seed_notifications(app, user_id(client, headers), 7)

    everything = listing(client, headers)
    assert [n["id"] for n in everything["items"]] == ids[::-1]
    assert everything["unread_count"] == 7 and everything["next_before"] is None
    assert set(everything["items"][0]) == {
        "id",
        "kind",
        "title",
        "body",
        "href",
        "data",
        "created_at",
        "read_at",
    }
    assert everything["items"][0]["data"] == {"event_id": "evt_x", "n": 6}

    # Three pages of three.
    seen: list[str] = []
    cursor: str | None = None
    for expected in (3, 3, 1):
        params = {"limit": 3, **({"before": cursor} if cursor else {})}
        page = listing(client, headers, **params)
        assert len(page["items"]) == expected and page["unread_count"] == 7
        seen += [n["id"] for n in page["items"]]
        cursor = page["next_before"]
    assert seen == ids[::-1] and cursor is None

    for newest in ids[-2:]:
        assert client.post(f"/v1/notifications/{newest}/read", headers=headers).status_code == 200
    assert [n["id"] for n in listing(client, headers, unread="true")["items"]] == ids[:5][::-1]
    assert [n["id"] for n in listing(client, headers, unread="false")["items"]] == ids[-2:][::-1]
    assert listing(client, headers, unread="true", limit=2)["unread_count"] == 5
    assert unread(client, headers) == 5


def test_list_parameters_are_validated(client: TestClient, headers: Headers) -> None:
    for params in ({"limit": 0}, {"limit": 101}, {"unread": "maybe"}, {"before": "x" * 81}):
        response = client.get("/v1/notifications", params=params, headers=headers)
        assert response.status_code == 422, params
        assert_envelope(response.json(), "validation_error")
    for cursor in ("garbage", "123", "-abc", "12x-abc", "9" * 30 + "-a"):
        response = client.get("/v1/notifications", params={"before": cursor}, headers=headers)
        assert response.status_code == 422, cursor
        assert response.json()["error"]["code"] in ("invalid_cursor", "validation_error")
    bad = client.get("/v1/notifications", params={"before": "garbage"}, headers=headers)
    assert_envelope(bad.json(), "invalid_cursor")


def test_mark_read_read_all_and_delete(client: TestClient, headers: Headers, app: FastAPI) -> None:
    ids = seed_notifications(app, user_id(client, headers), 4)
    assert unread(client, headers) == 4

    read = client.post(f"/v1/notifications/{ids[0]}/read", headers=headers)
    assert read.status_code == 200
    assert read.json()["id"] == ids[0] and read.json()["read_at"] is not None
    # Marking it again keeps the first timestamp.
    again = client.post(f"/v1/notifications/{ids[0]}/read", headers=headers).json()
    assert again["read_at"] == read.json()["read_at"]
    assert unread(client, headers) == 3

    all_read = client.post("/v1/notifications/read-all", headers=headers)
    assert all_read.status_code == 200 and all_read.json() == {"updated": 3}
    assert client.post("/v1/notifications/read-all", headers=headers).json() == {"updated": 0}
    assert unread(client, headers) == 0
    assert all(n["read_at"] is not None for n in listing(client, headers)["items"])
    assert listing(client, headers, unread="true")["items"] == []

    assert client.delete(f"/v1/notifications/{ids[1]}", headers=headers).status_code == 204
    gone = client.delete(f"/v1/notifications/{ids[1]}", headers=headers)
    assert gone.status_code == 404
    assert_envelope(gone.json(), "not_found")
    missing = client.post("/v1/notifications/nope/read", headers=headers)
    assert missing.status_code == 404
    assert_envelope(missing.json(), "not_found")
    assert [n["id"] for n in listing(client, headers)["items"]] == [ids[3], ids[2], ids[0]]
    with app.state.session_factory() as db:
        audit = db.scalar(select(AuditLog).where(AuditLog.action == "notification.delete"))
        assert audit is not None and audit.entity_id == ids[1]
        assert audit.details == {"kind": "game_final"}


def test_notifications_are_private_to_their_owner(
    client: TestClient, headers: Headers, other_headers: Headers, app: FastAPI
) -> None:
    mine = seed_notifications(app, user_id(client, headers), 2, prefix="mine")
    theirs = seed_notifications(app, user_id(client, other_headers), 1, prefix="theirs")

    assert [n["id"] for n in listing(client, headers)["items"]] == mine[::-1]
    assert [n["id"] for n in listing(client, other_headers)["items"]] == theirs
    assert unread(client, headers) == 2 and unread(client, other_headers) == 1
    for response in (
        client.post(f"/v1/notifications/{mine[0]}/read", headers=other_headers),
        client.delete(f"/v1/notifications/{mine[0]}", headers=other_headers),
    ):
        assert response.status_code == 404
        assert_envelope(response.json(), "not_found")
    # Their read-all and paging cursor do not reach my notifications.
    assert client.post("/v1/notifications/read-all", headers=other_headers).json() == {"updated": 1}
    assert unread(client, headers) == 2
    my_cursor = listing(client, headers, limit=1)["next_before"]
    # A cursor only positions the reader in their own list.
    assert [n["id"] for n in listing(client, other_headers, before=my_cursor)["items"]] == theirs
    assert all(n["read_at"] is None for n in listing(client, headers)["items"])


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/v1/notifications"),
        ("GET", "/v1/notifications/unread-count"),
        ("POST", "/v1/notifications/read-all"),
        ("POST", "/v1/notifications/abc/read"),
        ("DELETE", "/v1/notifications/abc"),
        ("GET", "/v1/me/notification-preferences"),
        ("PUT", "/v1/me/notification-preferences"),
        ("GET", "/v1/me/stake-reminder"),
        ("PUT", "/v1/me/stake-reminder"),
    ],
)
def test_routes_require_authentication(client: TestClient, method: str, path: str) -> None:
    response = client.request(method, path, json={})
    assert response.status_code == 401
    assert_envelope(response.json(), "not_authenticated")


def test_at_most_500_notifications_are_kept_oldest_read_first(
    client: TestClient, headers: Headers, app: FastAPI
) -> None:
    assert MAX_NOTIFICATIONS == 500
    owner = user_id(client, headers)
    ids = seed_notifications(app, owner, 503)
    with app.state.session_factory() as db:
        # Two read notifications that are *not* the oldest, and the newest one.
        for row_id in (ids[100], ids[200], ids[502]):
            db.get(Notification, row_id).read_at = FROZEN_NOW  # type: ignore[union-attr]
        db.commit()
        draft = templates.sync_finished(
            run_id="r",
            connection_id="c",
            label="Mock account",
            succeeded=True,
            imported=1,
            duplicates=0,
            attempts=1,
        )
        assert notifications_service.notify(db, owner, draft) == "delivered"
        assert notifications_service.trim(db, owner) == 4
        db.commit()
        kept = set(db.scalars(select(Notification.id).where(Notification.user_id == owner)))
        assert len(kept) == 500
    # Gone: the read ones first (oldest read first), then the oldest unread.
    assert not {ids[100], ids[200], ids[502], ids[0]} & kept
    assert {ids[1], ids[501]} <= kept
    assert unread(client, headers) == 500
    with app.state.session_factory() as db:  # at the cap there is nothing to trim
        assert notifications_service.trim(db, owner) == 0


# ------------------------------------------------------- lazy evaluation
def _met_price_alert(
    client: TestClient, headers: Headers, world: ControlledProvider, index: int
) -> str:
    event = world.list_events(league="nba", status="upcoming")[index]
    world.set_odds(event.id, "moneyline", [("northline", "open", 10.0, moneyline(150, -170))])
    response = client.post(
        "/v1/alerts",
        json={
            "kind": "price_at_least",
            "event_id": event.id,
            "market": "moneyline",
            "outcome_key": "home",
            "threshold": 145,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def test_reading_notifications_evaluates_rules_at_most_once_per_30_seconds(
    make_app: AppFactory, world: ControlledProvider
) -> None:
    app = make_app(provider=world)  # the default throttle
    assert app.state.settings.alert_eval_min_seconds == 30
    with TestClient(app) as client:
        headers = auth_headers(client)
        other = auth_headers(client, "grace@example.test")
        _met_price_alert(client, headers, world, 0)
        assert unread(client, headers) == 1  # first read evaluates

        _met_price_alert(client, headers, world, 1)
        # Within 30 seconds neither read route evaluates again.
        assert unread(client, headers) == 1
        world.advance(seconds=29)
        assert len(listing(client, headers)["items"]) == 1
        # The throttle is per user: someone else's first read is not held back.
        _met_price_alert(client, other, world, 2)
        assert unread(client, other) == 1

        world.advance(seconds=1)  # 30 seconds after the first evaluation
        body = listing(client, headers)
        assert len(body["items"]) == 2 and body["unread_count"] == 2

        # The explicit refresh is never throttled, and counts as an evaluation.
        _met_price_alert(client, headers, world, 3)
        assert unread(client, headers) == 2
        evaluated = client.post("/v1/alerts/evaluate", headers=headers).json()
        assert evaluated == {"evaluated": 1, "fired": 1, "expired": 0}
        assert unread(client, headers) == 3


def test_throttle_can_be_changed_or_switched_off(
    make_app: AppFactory, world: ControlledProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(make_app(provider=world, alert_eval_min_seconds=0)) as client:
        headers = auth_headers(client)
        for index in range(3):
            _met_price_alert(client, headers, world, index)
            assert unread(client, headers) == index + 1  # every read evaluates
    monkeypatch.setenv("ODDVEX_ALERT_EVAL_MIN_SECONDS", "7")
    from oddvex_api.config import Settings

    assert Settings(_env_file=None).alert_eval_min_seconds == 7  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        Settings(_env_file=None, alert_eval_min_seconds=-1)  # type: ignore[call-arg]


def test_a_failing_evaluation_does_not_break_reading_notifications(
    client: TestClient,
    headers: Headers,
    world: ControlledProvider,
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_notifications(app, user_id(client, headers), 1)
    _met_price_alert(client, headers, world, 0)

    def boom(*_: Any, **__: Any) -> Any:
        raise RuntimeError("provider is down")

    monkeypatch.setattr(world, "get_odds", boom)
    assert unread(client, headers) == 1
    assert len(listing(client, headers)["items"]) == 1
    monkeypatch.undo()
    assert unread(client, headers) == 2


# ----------------------------------------------------------------- preferences
ALL_ON = {
    "price_alert": True,
    "line_move": True,
    "game_start": True,
    "game_final": True,
    "bet_settled": True,
    "sync_finished": True,
    "stake_reminder": True,
}


def test_preferences_default_to_everything_enabled_and_update_partially(
    client: TestClient, headers: Headers, other_headers: Headers, app: FastAPI
) -> None:
    url = "/v1/me/notification-preferences"
    assert client.get(url, headers=headers).json() == {"in_app": ALL_ON}

    updated = client.put(
        url, json={"in_app": {"bet_settled": False, "line_move": False}}, headers=headers
    )
    assert updated.status_code == 200
    expected = {**ALL_ON, "bet_settled": False, "line_move": False}
    assert updated.json() == {"in_app": expected}
    assert client.get(url, headers=headers).json() == {"in_app": expected}
    # Kinds left out keep their value; switching one back on works.
    back = client.put(url, json={"in_app": {"line_move": True}}, headers=headers).json()
    assert back == {"in_app": {**ALL_ON, "bet_settled": False}}
    assert client.put(url, json={"in_app": {}}, headers=headers).json() == back
    # Per user.
    assert client.get(url, headers=other_headers).json() == {"in_app": ALL_ON}

    # No push, email or quiet-hours settings exist, and unknown kinds are rejected.
    for body in (
        {"in_app": {"marketing": False}},
        {"in_app": {"price_alert": "nope"}},
        {"in_app": ALL_ON, "push": ALL_ON},
        {"in_app": ALL_ON, "email": ALL_ON},
        {"in_app": ALL_ON, "quiet_hours": {"start": "22:00"}},
        {},
        {"price_alert": False},
    ):
        response = client.put(url, json=body, headers=headers)
        assert response.status_code == 422, body
        assert_envelope(response.json(), "validation_error")
    assert set(client.get(url, headers=headers).json()) == {"in_app"}

    with app.state.session_factory() as db:
        audits = list(
            db.scalars(
                select(AuditLog)
                .where(AuditLog.action == "notification_preferences.update")
                .order_by(AuditLog.created_at, AuditLog.id)
            )
        )
    assert [a.details for a in audits] == [
        {"in_app": {"bet_settled": False, "line_move": False}},
        {"in_app": {"line_move": True}},
    ]


# ------------------------------------------------------------ staking reminder
def test_stake_reminder_defaults_and_validation(client: TestClient, headers: Headers) -> None:
    url = "/v1/me/stake-reminder"
    assert client.get(url, headers=headers).json() == {
        "weekly_stake_threshold": None,
        "staked_this_week": 0.0,
        "week_start": "2026-03-09T00:00:00Z",
        "exceeded": False,
    }
    assert set_reminder(client, headers, 250.5) == {
        "weekly_stake_threshold": 250.5,
        "staked_this_week": 0.0,
        "week_start": "2026-03-09T00:00:00Z",
        "exceeded": False,
    }
    assert set_reminder(client, headers, 1_000_000)["weekly_stake_threshold"] == 1_000_000
    assert set_reminder(client, headers, None)["weekly_stake_threshold"] is None
    for body in (
        {"weekly_stake_threshold": 0},
        {"weekly_stake_threshold": -5},
        {"weekly_stake_threshold": 1_000_000.01},
        {"weekly_stake_threshold": "lots"},
        {},
        {"weekly_stake_threshold": 100, "hard_limit": True},
        {"weekly_stake_threshold": 100, "block_bets": True},
    ):
        response = client.put(url, json=body, headers=headers)
        assert response.status_code == 422, body
        assert_envelope(response.json(), "validation_error")
    assert client.get(url, headers=headers).json()["weekly_stake_threshold"] is None


def test_staked_this_week_is_the_current_iso_week_in_utc_without_void_bets(
    client: TestClient, headers: Headers, other_headers: Headers
) -> None:
    place(client, headers, 10, placed_at=WEEK_START)  # Monday 00:00:00 is in
    place(client, headers, 20, placed_at=FROZEN_NOW)
    place(client, headers, 40, placed_at=WEEK_START + timedelta(days=7) - timedelta(seconds=1))
    place(client, headers, 500, placed_at=WEEK_START - timedelta(seconds=1))  # last week
    place(client, headers, 700, placed_at=WEEK_START + timedelta(days=7))  # next week
    # A time zone offset is converted, not taken at face value: Sunday 20:00 -05:00 is Monday UTC.
    place(client, headers, 5, placed_at=datetime.fromisoformat("2026-03-08T20:00:00-05:00"))
    voided = place(client, headers, 80)
    settled = place(client, headers, 1)
    place(client, other_headers, 999)

    def staked(who: Headers) -> float:
        return float(client.get("/v1/me/stake-reminder", headers=who).json()["staked_this_week"])

    assert staked(headers) == 10 + 20 + 40 + 5 + 80 + 1
    client.post(f"/v1/bets/{voided['id']}/settle", json={"result": "void"}, headers=headers)
    client.post(f"/v1/bets/{settled['id']}/settle", json={"result": "lost"}, headers=headers)
    assert staked(headers) == 10 + 20 + 40 + 5 + 1  # void excluded, lost still counts
    assert staked(other_headers) == 999
    body = set_reminder(client, headers, 76)
    assert body["exceeded"] is True and body["staked_this_week"] == 76
    assert set_reminder(client, headers, 76.01)["exceeded"] is False


def test_crossing_the_threshold_creates_exactly_one_reminder_per_week(
    client: TestClient, headers: Headers, world: ControlledProvider, app: FastAPI
) -> None:
    set_reminder(client, headers, 100)
    place(client, headers, 60)
    assert reminders(client, headers) == []
    place(client, headers, 39.99)
    assert reminders(client, headers) == []

    # 99.99 -> 100.00: from below to exactly at the threshold. The bet is saved as usual.
    crossing = place(client, headers, 0.01)
    assert crossing["status"] == "pending" and crossing["stake"] == 0.01
    (reminder,) = reminders(client, headers)
    assert reminder["title"] == "Weekly staking reminder"
    assert reminder["body"] == (
        "You have staked $100.00 this week, at or above the $100.00 reminder you set. "
        "This is a reminder, not a limit. Free, confidential help is available at "
        "1-800-GAMBLER."
    )
    assert reminder["href"] == "/app/tracker"
    assert reminder["data"] == {
        "week_start": "2026-03-09T00:00:00+00:00",
        "staked_this_week": 100.0,
        "weekly_stake_threshold": 100.0,
    }

    # More bets the same week: all saved, no second reminder.
    for stake in (50, 500, 5000):
        place(client, headers, stake)
    assert len(reminders(client, headers)) == 1
    assert len(client.get("/v1/bets", headers=headers).json()) == 6
    status = client.get("/v1/me/stake-reminder", headers=headers).json()
    assert status["exceeded"] is True and status["staked_this_week"] == 5650.0

    # Not even if the reminder is deleted, the threshold changes or bets are removed.
    client.delete(f"/v1/notifications/{reminder['id']}", headers=headers)
    set_reminder(client, headers, 6000)
    place(client, headers, 400)
    assert reminders(client, headers) == []

    # A new week starts from zero and can cross again, once.
    world.current = WEEK_START + timedelta(days=7, hours=9)
    assert client.get("/v1/me/stake-reminder", headers=headers).json() == {
        "weekly_stake_threshold": 6000.0,
        "staked_this_week": 0.0,
        "week_start": "2026-03-16T00:00:00Z",
        "exceeded": False,
    }
    set_reminder(client, headers, 100)
    place(client, headers, 250, placed_at=world.current)
    place(client, headers, 250, placed_at=world.current)
    (second,) = reminders(client, headers)
    assert second["body"].startswith("You have staked $250.00 this week, at or above the $100.00")
    assert second["data"]["week_start"] == "2026-03-16T00:00:00+00:00"

    with app.state.session_factory() as db:
        actions = list(
            db.scalars(
                select(AuditLog.action)
                .where(AuditLog.action.like("stake_reminder.%"))
                .order_by(AuditLog.created_at, AuditLog.id)
            )
        )
    assert actions.count("stake_reminder.reached") == 2
    assert actions.count("stake_reminder.update") == 3


def test_reminder_ignores_other_weeks_other_users_and_no_threshold(
    client: TestClient, headers: Headers, other_headers: Headers
) -> None:
    place(client, headers, 5000)  # no threshold set: nothing happens
    assert reminders(client, headers) == []
    # Setting a threshold below what is already staked does not notify by itself...
    assert set_reminder(client, headers, 100)["exceeded"] is True
    place(client, headers, 10)  # ...and neither does a bet that was already above it.
    assert reminders(client, headers) == []

    set_reminder(client, other_headers, 100)
    place(client, other_headers, 5000, placed_at=WEEK_START - timedelta(days=3))  # backdated
    assert reminders(client, other_headers) == []
    place(client, other_headers, 99)
    assert reminders(client, other_headers) == []
    place(client, other_headers, 2)
    assert len(reminders(client, other_headers)) == 1
    assert reminders(client, headers) == []

    # Switched off again: no reminder even when a later week crosses the old threshold.
    set_reminder(client, other_headers, None)
    assert client.get("/v1/me/stake-reminder", headers=other_headers).json()["exceeded"] is False


def test_disabling_the_reminder_kind_suppresses_the_notification_but_not_the_bet(
    client: TestClient, headers: Headers
) -> None:
    set_reminder(client, headers, 50)
    client.put(
        "/v1/me/notification-preferences",
        json={"in_app": {"stake_reminder": False}},
        headers=headers,
    )
    assert place(client, headers, 75)["stake"] == 75
    assert listing(client, headers)["items"] == []
    # The week's crossing is used up; re-enabling does not send it late.
    client.put(
        "/v1/me/notification-preferences",
        json={"in_app": {"stake_reminder": True}},
        headers=headers,
    )
    place(client, headers, 75)
    assert listing(client, headers)["items"] == []


# ---------------------------------------------------------------------- sync
class WeeklyProvider:
    """A sync provider whose bets were placed in the frozen clock's current week."""

    info = SyncProviderInfo(
        key="weekly",
        name="Weekly Book (test)",
        description="Two bets this week.",
        is_mock=True,
        requires_credentials=False,
    )

    def __init__(self) -> None:
        self.fail = False

    def authorize(self, options: dict[str, Any], now: datetime) -> Any:
        from oddvex_api.sync.base import Authorization

        return Authorization(label="Weekly account", state={})

    def fetch_bets(self, state: dict[str, Any], now: datetime) -> FetchResult:
        if self.fail:
            from oddvex_api.sync.base import SyncProviderError

            raise SyncProviderError("The test sportsbook is unavailable", retryable=True)
        leg = ExternalLeg(selection="Tides ML", market="moneyline", odds_decimal=Decimal("2.0"))
        bets = tuple(
            ExternalBet(
                external_bet_id=f"w-{index}",
                bet_type="straight",
                sportsbook="Weekly Book",
                stake=Decimal(stake),
                placed_at=FROZEN_NOW - timedelta(hours=index + 1),
                legs=(leg,),
            )
            for index, stake in enumerate(("60.00", "45.00"))
        )
        return FetchResult(bets=bets, state=state)


def test_sync_import_notifies_and_counts_towards_the_reminder_once(
    client: TestClient, headers: Headers, app: FastAPI
) -> None:
    provider = WeeklyProvider()
    app.state.sync_registry = SyncRegistry([provider])
    set_reminder(client, headers, 100)
    connection = client.post(
        "/v1/sync/connections", json={"provider": "weekly"}, headers=headers
    ).json()
    sync_url = f"/v1/sync/connections/{connection['id']}/sync"

    run = client.post(sync_url, headers=headers)
    assert run.status_code == 200
    assert set(run.json()) == {  # the response is what it was before notifications existed
        "id",
        "connection_id",
        "status",
        "attempts",
        "fetched_count",
        "imported_count",
        "duplicate_count",
        "retryable",
        "error_message",
        "started_at",
        "finished_at",
    }
    items = listing(client, headers)["items"]
    assert sorted(n["kind"] for n in items) == ["stake_reminder", "sync_finished"]
    finished = next(n for n in items if n["kind"] == "sync_finished")
    assert finished["title"] == "Import finished"
    assert finished["body"] == "Weekly account import finished: 2 new, 0 already imported."
    assert finished["href"] == "/app/tracker"
    assert finished["data"] == {
        "run_id": run.json()["id"],
        "connection_id": connection["id"],
        "status": "succeeded",
        "imported": 2,
        "duplicates": 0,
    }
    reminder = next(n for n in items if n["kind"] == "stake_reminder")
    assert reminder["body"].startswith("You have staked $105.00 this week, at or above the $100.00")

    # Importing again brings nothing new: another sync notification, no second reminder.
    again = client.post(sync_url, headers=headers).json()
    assert again["imported_count"] == 0 and again["duplicate_count"] == 2
    items = listing(client, headers)["items"]
    assert [n["kind"] for n in items].count("stake_reminder") == 1
    bodies = [n["body"] for n in items if n["kind"] == "sync_finished"]
    assert "Weekly account import finished: 0 new, 2 already imported." in bodies
    assert len(bodies) == 2

    # A failed run is reported too, in the same neutral way, and still returns 502.
    provider.fail = True
    failed = client.post(sync_url, headers=headers)
    assert failed.status_code == 502
    assert_envelope(failed.json(), "sync_failed")
    newest = listing(client, headers)["items"][0]
    assert newest["kind"] == "sync_finished" and newest["title"] == "Import did not finish"
    assert newest["body"] == (
        "Weekly account import did not finish after 3 attempt(s). No bets were added."
    )
    assert newest["data"]["status"] == "failed"
    assert newest["data"]["run_id"] == failed.json()["error"]["details"]["run_id"]


def test_sync_notification_respects_preferences(client: TestClient, headers: Headers) -> None:
    client.put(
        "/v1/me/notification-preferences",
        json={"in_app": {"sync_finished": False}},
        headers=headers,
    )
    connection = client.post("/v1/sync/connections", json={}, headers=headers).json()
    run = client.post(f"/v1/sync/connections/{connection['id']}/sync", headers=headers)
    assert run.status_code == 200 and run.json()["imported_count"] > 0
    assert listing(client, headers)["items"] == []


# ---------------------------------------------------------------- auto-settle
def test_auto_settle_creates_one_notification_per_settled_bet(
    client: TestClient, headers: Headers, other_headers: Headers, world: ControlledProvider
) -> None:
    finals = [
        e
        for e in world.list_events(league="nba", status="final")
        if e.score is not None and e.score.home != e.score.away
    ]
    first, second = finals[0], finals[1]

    def structured(event: Any, pick_winner: bool, stake: float) -> dict[str, Any]:
        assert event.score is not None
        home_won = event.score.home > event.score.away
        outcome = "home" if home_won == pick_winner else "away"
        return {
            "bet_type": "straight",
            "stake": stake,
            "sportsbook": "Northline",
            "legs": [
                {
                    "selection": f"moneyline {outcome}",
                    "market": "moneyline",
                    "event_id": event.id,
                    "outcome_key": outcome,
                    "odds": 150,
                }
            ],
        }

    won = client.post("/v1/bets", json=structured(first, True, 20), headers=headers).json()
    lost = client.post("/v1/bets", json=structured(second, False, 30), headers=headers).json()
    free_text = client.post("/v1/bets", json=bet_body(10), headers=headers).json()
    assert listing(client, headers)["items"] == []

    result = client.post("/v1/bets/auto-settle", headers=headers)
    assert result.status_code == 200
    body = result.json()
    assert set(body) == {"checked", "settled", "skipped"}  # unchanged response
    assert {b["id"] for b in body["settled"]} == {won["id"], lost["id"]}
    assert [s["bet_id"] for s in body["skipped"]] == [free_text["id"]]

    items = listing(client, headers)["items"]
    assert [n["kind"] for n in items] == ["bet_settled", "bet_settled"]
    by_bet = {n["data"]["bet_id"]: n for n in items}
    assert by_bet[won["id"]]["title"] == "Bet settled: won"
    assert by_bet[won["id"]]["body"] == (
        "Your $20.00 bet at Northline settled as won. Profit: +$30.00."
    )
    assert by_bet[won["id"]]["data"] == {"bet_id": won["id"], "result": "won", "profit": 30.0}
    assert by_bet[lost["id"]]["title"] == "Bet settled: lost"
    assert by_bet[lost["id"]]["body"] == (
        "Your $30.00 bet at Northline settled as lost. Profit: -$30.00."
    )
    assert all(n["href"] == "/app/tracker" for n in items)

    # Nothing new on a second call, and nothing for anyone else.
    assert client.post("/v1/bets/auto-settle", headers=headers).json()["settled"] == []
    assert len(listing(client, headers)["items"]) == 2
    assert listing(client, other_headers)["items"] == []
    # A manual settle does not notify: the user did it themselves.
    client.post(f"/v1/bets/{free_text['id']}/settle", json={"result": "won"}, headers=headers)
    assert len(listing(client, headers)["items"]) == 2


def test_auto_settle_notification_respects_preferences(
    client: TestClient, headers: Headers, world: ControlledProvider
) -> None:
    event = world.list_events(league="nba", status="final")[0]
    client.put(
        "/v1/me/notification-preferences", json={"in_app": {"bet_settled": False}}, headers=headers
    )
    leg = {
        "selection": "home",
        "market": "moneyline",
        "event_id": event.id,
        "outcome_key": "home",
        "odds": 100,
    }
    client.post(
        "/v1/bets",
        json={"bet_type": "straight", "stake": 10, "sportsbook": "Northline", "legs": [leg]},
        headers=headers,
    )
    assert len(client.post("/v1/bets/auto-settle", headers=headers).json()["settled"]) == 1
    assert listing(client, headers)["items"] == []


# ------------------------------------------------------------------ lifecycle
def _fill_account(client: TestClient, headers: Headers, world: ControlledProvider) -> str:
    alert_id = _met_price_alert(client, headers, world, 0)
    client.put(
        "/v1/me/notification-preferences", json={"in_app": {"line_move": False}}, headers=headers
    )
    set_reminder(client, headers, 50)
    place(client, headers, 75)
    assert unread(client, headers) == 2
    return alert_id


def test_export_includes_alerts_notifications_preferences_and_the_reminder(
    client: TestClient, headers: Headers, other_headers: Headers, world: ControlledProvider
) -> None:
    alert_id = _fill_account(client, headers, world)
    _fill_account(client, other_headers, world)
    mine = listing(client, headers)["items"]

    body = client.get("/v1/me/export", headers=headers).json()
    assert body["format_version"] == 1
    assert [a["id"] for a in body["alerts"]] == [alert_id]
    assert body["alerts"][0] == client.get("/v1/alerts", headers=headers).json()["items"][0]
    assert body["alerts"][0]["state"] == "triggered"
    assert body["notifications"] == mine[::-1]  # oldest first, same shape as the list route
    assert {n["kind"] for n in body["notifications"]} == {"price_alert", "stake_reminder"}
    assert body["notification_preferences"] == {"in_app": {**ALL_ON, "line_move": False}}
    assert body["stake_reminder"] == client.get("/v1/me/stake-reminder", headers=headers).json()
    assert body["stake_reminder"]["weekly_stake_threshold"] == 50.0
    actions = {entry["action"] for entry in body["audit_log"]}
    assert {
        "alert.create",
        "alert.fired",
        "notification_preferences.update",
        "stake_reminder.update",
        "stake_reminder.reached",
    } <= actions

    # Nothing of the other user's.
    theirs = client.get("/v1/me/export", headers=other_headers).json()
    assert not {n["id"] for n in theirs["notifications"]} & {n["id"] for n in mine}
    assert theirs["alerts"][0]["id"] != alert_id

    # A new account exports empty, well-formed defaults.
    fresh = auth_headers(client, "new@example.test")
    empty = client.get("/v1/me/export", headers=fresh).json()
    assert empty["alerts"] == [] and empty["notifications"] == []
    assert empty["notification_preferences"] == {"in_app": ALL_ON}
    assert empty["stake_reminder"]["weekly_stake_threshold"] is None


def test_deleting_the_account_deletes_everything_added_here(
    client: TestClient,
    headers: Headers,
    other_headers: Headers,
    world: ControlledProvider,
    app: FastAPI,
) -> None:
    owner = user_id(client, headers)
    _fill_account(client, headers, world)
    _fill_account(client, other_headers, world)

    def counts(db: Any, who: str) -> dict[str, int]:
        return {
            model.__tablename__: int(
                db.scalar(select(func.count()).select_from(model).where(model.user_id == who)) or 0
            )
            for model in (AlertRule, Notification, NotificationPreference, StakeReminder)
        }

    with app.state.session_factory() as db:
        assert counts(db, owner) == {
            "alert_rules": 1,
            "notifications": 2,
            "notification_preferences": 1,
            "stake_reminders": 1,
        }
    assert client.delete("/v1/me", headers=headers).status_code == 204
    assert client.get("/v1/notifications", headers=headers).status_code == 401

    with app.state.session_factory() as db:
        assert counts(db, owner) == {
            "alert_rules": 0,
            "notifications": 0,
            "notification_preferences": 0,
            "stake_reminders": 0,
        }
        assert db.scalar(select(func.count()).select_from(User)) == 1
        other = db.scalar(select(User.id))
        assert counts(db, other) == {
            "alert_rules": 1,
            "notifications": 2,
            "notification_preferences": 1,
            "stake_reminders": 1,
        }
        # The audit trail keeps opaque entries.
        kept = set(db.scalars(select(AuditLog.action).where(AuditLog.user_id == owner)))
        assert {"account.deleted", "alert.create"} <= kept
    assert unread(client, other_headers) == 2


# ------------------------------------------------------------------- channels
def test_delivery_goes_through_the_channel_protocol(
    client: TestClient, headers: Headers, app: FastAPI
) -> None:
    assert isinstance(InAppChannel(), NotificationChannel)

    class RecordingChannel:
        name = "recording"

        def __init__(self) -> None:
            self.sent: list[tuple[str, str]] = []

        def deliver(self, db: Any, user_id: str, draft: templates.NotificationDraft) -> bool:
            self.sent.append((user_id, draft.title))
            return True

    extra = RecordingChannel()
    assert isinstance(extra, NotificationChannel)
    owner = user_id(client, headers)
    draft = templates.bet_settled(
        bet_id="b1",
        result="won",
        stake=Decimal("10"),
        profit=Decimal("9.09"),
        sportsbook="Northline",
    )
    client.put(
        "/v1/me/notification-preferences", json={"in_app": {"bet_settled": False}}, headers=headers
    )
    with app.state.session_factory() as db:
        # In-app is switched off for this kind; the other channel still gets it.
        result = notifications_service.notify(db, owner, draft, channels=(InAppChannel(), extra))
        db.commit()
        assert result == "delivered" and extra.sent == [(owner, "Bet settled: won")]
        assert notifications_service.notify(db, owner, draft) == "disabled"
        assert db.scalar(select(func.count()).select_from(Notification)) == 0


# ------------------------------------------------------------------- the copy
def test_every_notification_the_api_creates_passes_the_copy_rules(
    client: TestClient, headers: Headers, world: ControlledProvider, app: FastAPI
) -> None:
    """End to end: each kind created through the API, then scanned like the templates."""
    nba = world.list_events(league="nba", status="upcoming")
    event, later = nba[0], nba[1]
    world.set_odds(event.id, "moneyline", [("northline", "open", 10.0, moneyline(150, -170))])
    world.set_odds(
        event.id,
        "total",
        [("northline", "open", 10.0, [("over", 224.5, -110), ("under", 224.5, -110)])],
    )
    final = next(
        e
        for e in world.list_events(league="nba", status="final")
        if e.score is not None and e.score.home != e.score.away
    )
    for body in (
        {
            "kind": "price_at_least",
            "event_id": event.id,
            "market": "moneyline",
            "outcome_key": "home",
            "threshold": 145,
        },
        {
            "kind": "line_move",
            "event_id": event.id,
            "market": "total",
            "outcome_key": "over",
            "min_move": 1,
        },
        {"kind": "game_start", "event_id": later.id, "minutes_before": 1440},
        {"kind": "game_final", "event_id": event.id},
    ):
        assert client.post("/v1/alerts", json=body, headers=headers).status_code == 201, body
    world.set_odds(
        event.id,
        "total",
        [("northline", "open", 10.0, [("over", 226.5, -110), ("under", 226.5, -110)])],
    )
    client.post("/v1/alerts/evaluate", headers=headers)
    world.finish(event.id, home=110, away=104)
    set_reminder(client, headers, 20)
    leg = {
        "selection": "home",
        "market": "moneyline",
        "event_id": final.id,
        "outcome_key": "home",
        "odds": -120,
    }
    client.post(
        "/v1/bets",
        json={
            "bet_type": "straight",
            "stake": 25,
            "sportsbook": "Northline",
            "legs": [leg],
            "placed_at": FROZEN_NOW.isoformat(),
        },
        headers=headers,
    )
    client.post("/v1/bets/auto-settle", headers=headers)
    connection = client.post("/v1/sync/connections", json={}, headers=headers).json()
    client.post(f"/v1/sync/connections/{connection['id']}/sync", headers=headers)

    items = listing(client, headers)["items"]
    assert {n["kind"] for n in items} == {
        "price_alert",
        "line_move",
        "game_start",
        "game_final",
        "bet_settled",
        "sync_finished",
        "stake_reminder",
    }
    for item in items:
        text = f"{item['title']} {item['body']}".lower()
        for phrase in BANNED_PHRASES:
            # Team and book names are fictional proper nouns; only the wording is checked.
            assert phrase not in text, (phrase, item)
        assert "!" not in text and "%" not in text
        assert item["title"][0].isupper() and item["href"].startswith("/app/")


# --------------------------------------------------------------------- script
def _load_script() -> Any:
    spec = importlib.util.spec_from_file_location(
        "evaluate_alerts_script", API_ROOT / "scripts" / "evaluate_alerts.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_evaluate_alerts_script_covers_every_user_and_is_idempotent(
    client: TestClient,
    headers: Headers,
    other_headers: Headers,
    world: ControlledProvider,
    app: FastAPI,
) -> None:
    script = _load_script()
    settings = app.state.settings
    _met_price_alert(client, headers, world, 0)
    _met_price_alert(client, other_headers, world, 1)
    auth_headers(client, "norules@example.test")

    def stored() -> int:
        with app.state.session_factory() as db:
            return int(db.scalar(select(func.count()).select_from(Notification)) or 0)

    dry = script.run(settings, provider=world, dry_run=True)
    assert dry == {"users": 2, "evaluated": 2, "fired": 2, "expired": 0, "failed": 0}
    assert stored() == 0
    with app.state.session_factory() as db:
        assert set(db.scalars(select(AlertRule.state))) == {"active"}

    real = script.run(settings, provider=world)
    assert real == {"users": 2, "evaluated": 2, "fired": 2, "expired": 0, "failed": 0}
    assert stored() == 2
    again = script.run(settings, provider=world)
    assert again == {"users": 0, "evaluated": 0, "fired": 0, "expired": 0, "failed": 0}
    assert stored() == 2
    assert unread(client, headers) == 1 and unread(client, other_headers) == 1


def test_evaluate_alerts_script_runs_from_the_command_line(tmp_path: Path) -> None:
    env = {
        "DATABASE_URL": f"sqlite:///{tmp_path / 'script.db'}",
        "ODDVEX_ENV": "development",
        "PATH": "/usr/bin:/bin",
    }
    seed = subprocess.run(
        [sys.executable, str(API_ROOT / "scripts" / "seed_demo.py")],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert seed.returncode == 0, seed.stderr
    script = [sys.executable, str(API_ROOT / "scripts" / "evaluate_alerts.py")]
    for args, prefix in ((["--dry-run"], "Dry run, nothing saved: 1 user(s)"), ([], "1 user(s)")):
        result = subprocess.run(
            [*script, *args], cwd=tmp_path, env=env, capture_output=True, text=True, check=False
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.startswith(prefix), result.stdout
        assert "0 failed" in result.stdout


def test_settings_factory_default_is_the_documented_throttle(
    make_settings: SettingsFactory,
) -> None:
    assert make_settings().alert_eval_min_seconds == 30


def test_put_is_allowed_by_cors(client: TestClient) -> None:
    response = client.options(
        "/v1/me/stake-reminder",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "PUT"},
    )
    assert response.status_code == 200
    assert "PUT" in response.headers["access-control-allow-methods"]
