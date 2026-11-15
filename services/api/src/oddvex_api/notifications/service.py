"""Notification domain logic: delivery, preferences, retention and the staking reminder."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

from fastapi import Request
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from ..db import Bet, Notification, NotificationPreference, StakeReminder, utcnow
from ..deps import write_audit
from ..errors import ApiError
from . import templates
from .channels import DEFAULT_CHANNELS, NotificationChannel
from .schemas import (
    MAX_NOTIFICATIONS,
    NOTIFICATION_KINDS,
    InAppPreferencesOut,
    NotificationOut,
    NotificationPreferencesOut,
    NotificationPreferencesUpdate,
    StakeReminderOut,
)
from .templates import NotificationDraft

Delivery = Literal["delivered", "duplicate", "disabled"]


# ----------------------------------------------------------------- preferences
def disabled_kinds(db: Session, user_id: str, channel: str = "in_app") -> set[str]:
    """Kinds the user switched off for ``channel``. Only ``in_app`` has preferences today."""
    if channel != "in_app":
        return set()
    row = db.get(NotificationPreference, user_id)
    return set(row.in_app_disabled or []) if row else set()


def preferences_out(db: Session, user_id: str) -> NotificationPreferencesOut:
    disabled = disabled_kinds(db, user_id)
    return NotificationPreferencesOut(
        in_app=InAppPreferencesOut(**{kind: kind not in disabled for kind in NOTIFICATION_KINDS})
    )


def update_preferences(
    db: Session, user_id: str, body: NotificationPreferencesUpdate
) -> dict[str, bool]:
    """Apply the switches that were sent. Returns the ones that changed."""
    row = db.get(NotificationPreference, user_id)
    if row is None:
        row = NotificationPreference(user_id=user_id, in_app_disabled=[])
        db.add(row)
    disabled = set(row.in_app_disabled or [])
    changed: dict[str, bool] = {}
    for kind, enabled in body.in_app.model_dump(exclude_none=True).items():
        if enabled == (kind in disabled):
            changed[kind] = enabled
            disabled.discard(kind) if enabled else disabled.add(kind)
    # A new list object, so the JSON column is seen as changed.
    row.in_app_disabled = sorted(disabled)
    row.updated_at = utcnow()
    return changed


# -------------------------------------------------------------------- delivery
def notify(
    db: Session,
    user_id: str,
    draft: NotificationDraft,
    channels: Sequence[NotificationChannel] = DEFAULT_CHANNELS,
) -> Delivery:
    """Deliver ``draft`` on every channel the user has not disabled for its kind.

    ``delivered``: at least one channel created something new. ``disabled``: the user
    switched this kind off everywhere. ``duplicate``: it had been delivered before
    (same ``dedupe_key``). Idempotent; nothing is committed here.
    """
    result: Delivery = "disabled"
    for channel in channels:
        if draft.kind in disabled_kinds(db, user_id, channel.name):
            continue
        if channel.deliver(db, user_id, draft):
            result = "delivered"
        elif result == "disabled":
            result = "duplicate"
    return result


def trim(db: Session, user_id: str, keep: int = MAX_NOTIFICATIONS) -> int:
    """Keep at most ``keep`` notifications: the oldest read ones go first, then the oldest."""
    count = int(
        db.scalar(
            select(func.count()).select_from(Notification).where(Notification.user_id == user_id)
        )
        or 0
    )
    if count <= keep:
        return 0
    doomed = list(
        db.scalars(
            select(Notification.id)
            .where(Notification.user_id == user_id)
            .order_by(Notification.read_at.is_(None), Notification.created_at, Notification.id)
            .limit(count - keep)
        )
    )
    db.execute(delete(Notification).where(Notification.id.in_(doomed)))
    return len(doomed)


# --------------------------------------------------------------------- reading
def notification_out(row: Notification) -> NotificationOut:
    return NotificationOut(
        id=row.id,
        kind=row.kind,  # type: ignore[arg-type]
        title=row.title,
        body=row.body,
        href=row.href,
        data=row.data or {},
        created_at=row.created_at,
        read_at=row.read_at,
    )


def unread_count(db: Session, user_id: str) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        )
        or 0
    )


def encode_cursor(row: Notification) -> str:
    micros = int(row.created_at.timestamp()) * 1_000_000 + row.created_at.microsecond
    return f"{micros}-{row.id}"


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    micros, _, row_id = cursor.partition("-")
    if not micros.isdigit() or not row_id or len(micros) > 18:
        raise ApiError(422, "invalid_cursor", "The 'before' value is not a cursor from this API")
    seconds, remainder = divmod(int(micros), 1_000_000)
    try:
        moment = datetime.fromtimestamp(seconds, UTC).replace(microsecond=remainder)
    except (OverflowError, OSError, ValueError) as exc:
        raise ApiError(
            422, "invalid_cursor", "The 'before' value is not a cursor from this API"
        ) from exc
    return moment, row_id


def list_page(
    db: Session, user_id: str, unread: bool | None, limit: int, before: str | None
) -> tuple[list[Notification], str | None]:
    """Newest first. Returns the page and the cursor of the next (older) page, if any."""
    query = select(Notification).where(Notification.user_id == user_id)
    if unread is True:
        query = query.where(Notification.read_at.is_(None))
    elif unread is False:
        query = query.where(Notification.read_at.is_not(None))
    if before is not None:
        moment, row_id = decode_cursor(before)
        query = query.where(
            (Notification.created_at < moment)
            | ((Notification.created_at == moment) & (Notification.id < row_id))
        )
    rows = list(
        db.scalars(
            query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit + 1)
        )
    )
    page = rows[:limit]
    return page, encode_cursor(page[-1]) if len(rows) > limit and page else None


def mark_all_read(db: Session, user_id: str) -> int:
    result = db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=utcnow())
    )
    return int(result.rowcount)  # type: ignore[attr-defined]


# ------------------------------------------------------------ staking reminder
def week_start(now: datetime) -> datetime:
    """Monday 00:00 UTC of the ISO week ``now`` falls in."""
    now = now.astimezone(UTC)
    monday = now.date() - timedelta(days=now.weekday())
    return datetime(monday.year, monday.month, monday.day, tzinfo=UTC)


def staked_this_week(db: Session, user_id: str, now: datetime) -> Decimal:
    """Total stake of the user's bets placed in the current ISO week (UTC), void bets excluded."""
    start = week_start(now)
    total = db.scalar(
        select(func.coalesce(func.sum(Bet.stake), 0)).where(
            Bet.user_id == user_id,
            Bet.placed_at >= start,
            Bet.placed_at < start + timedelta(days=7),
            Bet.result.is_(None) | (Bet.result != "void"),
        )
    )
    return Decimal(str(total or 0)).quantize(Decimal("0.01"))


def stake_reminder_out(db: Session, user_id: str, now: datetime) -> StakeReminderOut:
    setting = db.get(StakeReminder, user_id)
    threshold = setting.weekly_stake_threshold if setting else None
    staked = staked_this_week(db, user_id, now)
    return StakeReminderOut(
        weekly_stake_threshold=float(threshold) if threshold is not None else None,
        staked_this_week=float(staked),
        week_start=week_start(now),
        exceeded=threshold is not None and staked >= threshold,
    )


def set_stake_threshold(db: Session, user_id: str, threshold: float | None) -> None:
    setting = db.get(StakeReminder, user_id)
    if setting is None:
        setting = StakeReminder(user_id=user_id)
        db.add(setting)
    setting.weekly_stake_threshold = (
        Decimal(str(threshold)).quantize(Decimal("0.01")) if threshold is not None else None
    )
    setting.updated_at = utcnow()


def check_stake_reminder(
    db: Session,
    user_id: str,
    staked_before: Decimal,
    now: datetime,
    request: Request | None = None,
) -> bool:
    """Create this week's reminder if the weekly total just went from below the user's
    threshold to at or above it.

    Call after the new bets are flushed, with the weekly total read before they were
    added. At most one reminder per user and week. It never blocks anything: the bets
    are already saved. Returns True when a notification was created.
    """
    setting = db.get(StakeReminder, user_id)
    if setting is None or setting.weekly_stake_threshold is None:
        return False
    threshold = setting.weekly_stake_threshold
    start = week_start(now)
    if setting.last_reminded_week == start.date():
        return False
    staked = staked_this_week(db, user_id, now)
    if not staked_before < threshold <= staked:
        return False
    setting.last_reminded_week = start.date()
    draft = templates.stake_reminder(week_start=start, staked=staked, threshold=threshold)
    created = notify(db, user_id, draft) == "delivered"
    write_audit(
        db,
        request,
        "stake_reminder.reached",
        user_id=user_id,
        entity_type="stake_reminder",
        entity_id=user_id,
        details={"week_start": start.date().isoformat(), "notified": created},
    )
    if created:
        trim(db, user_id)
    return created
