"""Notification, notification-preference and staking-reminder routes. Owner-scoped."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..alerts.throttle import evaluate_if_due
from ..db import Notification, utcnow
from ..deps import BoardDep, CurrentUserDep, DbDep, NowDep, write_audit
from ..errors import AUTH_ERROR_RESPONSES, NOT_FOUND_RESPONSE, not_found
from . import service
from .schemas import (
    MAX_NOTIFICATIONS,
    MarkAllReadOut,
    NotificationListOut,
    NotificationOut,
    NotificationPreferencesOut,
    NotificationPreferencesUpdate,
    StakeReminderOut,
    StakeReminderUpdate,
    UnreadCountOut,
)

router = APIRouter(tags=["notifications"], responses=AUTH_ERROR_RESPONSES)

_LAZY_NOTE = (
    "Your active alert rules are evaluated first, at most once every "
    "`ODDVEX_ALERT_EVAL_MIN_SECONDS` seconds per user."
)


def _owned_notification(db: Session, user_id: str, notification_id: str) -> Notification:
    row = db.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user_id
        )
    )
    if row is None:
        raise not_found("Notification", notification_id)
    return row


@router.get(
    "/notifications",
    response_model=NotificationListOut,
    operation_id="list_notifications",
    summary="Your notifications, newest first",
    description=(
        f"In-app notifications only; at most {MAX_NOTIFICATIONS} are kept per user. Page "
        "with `limit` and the `next_before` cursor. " + _LAZY_NOTE
    ),
)
def list_notifications(
    user: CurrentUserDep,
    db: DbDep,
    board: BoardDep,
    request: Request,
    unread: Annotated[
        bool | None, Query(description="true: unread only. false: read only. Omit for all.")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    before: Annotated[
        str | None, Query(max_length=80, description="`next_before` from the previous page.")
    ] = None,
) -> NotificationListOut:
    evaluate_if_due(request, db, user, board)
    page, next_before = service.list_page(db, user.id, unread, limit, before)
    return NotificationListOut(
        items=[service.notification_out(row) for row in page],
        unread_count=service.unread_count(db, user.id),
        next_before=next_before,
    )


@router.get(
    "/notifications/unread-count",
    response_model=UnreadCountOut,
    operation_id="get_unread_count",
    summary="How many notifications you have not read",
    description=_LAZY_NOTE,
)
def get_unread_count(
    user: CurrentUserDep, db: DbDep, board: BoardDep, request: Request
) -> UnreadCountOut:
    evaluate_if_due(request, db, user, board)
    return UnreadCountOut(unread_count=service.unread_count(db, user.id))


@router.post(
    "/notifications/read-all",
    response_model=MarkAllReadOut,
    operation_id="mark_all_notifications_read",
    summary="Mark every notification as read",
)
def mark_all_notifications_read(user: CurrentUserDep, db: DbDep) -> MarkAllReadOut:
    updated = service.mark_all_read(db, user.id)
    db.commit()
    return MarkAllReadOut(updated=updated)


@router.post(
    "/notifications/{notification_id}/read",
    response_model=NotificationOut,
    operation_id="mark_notification_read",
    summary="Mark one notification as read",
    description="Idempotent: a notification that is already read keeps its `read_at`.",
    responses=NOT_FOUND_RESPONSE,
)
def mark_notification_read(
    notification_id: str, user: CurrentUserDep, db: DbDep
) -> NotificationOut:
    row = _owned_notification(db, user.id, notification_id)
    if row.read_at is None:
        row.read_at = utcnow()
        db.commit()
    return service.notification_out(row)


@router.delete(
    "/notifications/{notification_id}",
    status_code=204,
    operation_id="delete_notification",
    summary="Delete a notification",
    responses=NOT_FOUND_RESPONSE,
)
def delete_notification(
    notification_id: str, user: CurrentUserDep, db: DbDep, request: Request
) -> Response:
    row = _owned_notification(db, user.id, notification_id)
    kind = row.kind
    db.delete(row)
    write_audit(
        db,
        request,
        "notification.delete",
        user_id=user.id,
        entity_type="notification",
        entity_id=notification_id,
        details={"kind": kind},
    )
    db.commit()
    return Response(status_code=204)


# ----------------------------------------------------------------- preferences
@router.get(
    "/me/notification-preferences",
    response_model=NotificationPreferencesOut,
    operation_id="get_notification_preferences",
    summary="Which kinds of notification you receive",
    description="Every kind is enabled until you switch it off. Delivery is in-app only.",
)
def get_notification_preferences(user: CurrentUserDep, db: DbDep) -> NotificationPreferencesOut:
    return service.preferences_out(db, user.id)


@router.put(
    "/me/notification-preferences",
    response_model=NotificationPreferencesOut,
    operation_id="update_notification_preferences",
    summary="Switch notification kinds on or off",
    description=(
        "Kinds left out of `in_app` keep their current value. A disabled kind creates no "
        "notification; alert rules still fire and change state."
    ),
)
def update_notification_preferences(
    body: NotificationPreferencesUpdate, user: CurrentUserDep, db: DbDep, request: Request
) -> NotificationPreferencesOut:
    changed = service.update_preferences(db, user.id, body)
    if changed:
        write_audit(
            db,
            request,
            "notification_preferences.update",
            user_id=user.id,
            entity_type="notification_preferences",
            entity_id=user.id,
            details={"in_app": changed},
        )
    db.commit()
    return service.preferences_out(db, user.id)


# ------------------------------------------------------------ staking reminder
_REMINDER_NOTE = (
    "A responsible-gambling tool. It is a reminder, not a limit: OddVex never blocks or "
    "rejects a bet you record. When your weekly total goes from below the threshold to at "
    "or above it you get one `stake_reminder` notification for that week."
)


@router.get(
    "/me/stake-reminder",
    response_model=StakeReminderOut,
    operation_id="get_stake_reminder",
    summary="Your weekly staking reminder and this week's total",
    description=_REMINDER_NOTE,
)
def get_stake_reminder(user: CurrentUserDep, db: DbDep, now: NowDep) -> StakeReminderOut:
    return service.stake_reminder_out(db, user.id, now)


@router.put(
    "/me/stake-reminder",
    response_model=StakeReminderOut,
    operation_id="update_stake_reminder",
    summary="Set or turn off your weekly staking reminder",
    description=_REMINDER_NOTE + " `weekly_stake_threshold: null` turns it off.",
)
def update_stake_reminder(
    body: StakeReminderUpdate, user: CurrentUserDep, db: DbDep, now: NowDep, request: Request
) -> StakeReminderOut:
    service.set_stake_threshold(db, user.id, body.weekly_stake_threshold)
    write_audit(
        db,
        request,
        "stake_reminder.update",
        user_id=user.id,
        entity_type="stake_reminder",
        entity_id=user.id,
        details={"enabled": body.weekly_stake_threshold is not None},
    )
    db.commit()
    return service.stake_reminder_out(db, user.id, now)
