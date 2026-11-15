"""Delivery channels.

Only in-app delivery exists. Push, email and SMS need third-party services (a Founder
approval gate) and would be added here as further :class:`NotificationChannel`
implementations; the alert engine and the callers of ``service.notify`` do not change.
"""

from __future__ import annotations

from typing import Any, Protocol, cast, runtime_checkable

from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ..db import Notification, new_id, utcnow
from .templates import NotificationDraft


@runtime_checkable
class NotificationChannel(Protocol):
    """One way of delivering a notification to a user."""

    #: Channel key; preferences are stored per channel and kind.
    name: str

    def deliver(self, db: Session, user_id: str, draft: NotificationDraft) -> bool:
        """Deliver ``draft``. Returns False when it was already delivered (same dedupe key).

        Must be idempotent: delivering the same draft twice, even from two concurrent
        transactions, results in one notification.
        """
        ...


class InAppChannel:
    """Stores the notification in the ``notifications`` table for the app to list."""

    name = "in_app"

    def deliver(self, db: Session, user_id: str, draft: NotificationDraft) -> bool:
        values: dict[str, Any] = {
            "id": new_id(),
            "user_id": user_id,
            "kind": draft.kind,
            "title": draft.title[:200],
            "body": draft.body,
            "href": draft.href[:300],
            "data": draft.data,
            "rule_id": draft.rule_id,
            "dedupe_key": draft.dedupe_key[:160],
            "created_at": utcnow(),
        }
        # INSERT ... ON CONFLICT DO NOTHING on the (user_id, dedupe_key) unique constraint:
        # of two concurrent deliveries of the same draft exactly one inserts a row. RETURNING
        # tells which, on every driver (rowcount is not reliable for this statement).
        table = cast(Table, Notification.__table__)
        insert = postgresql_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
        statement = (
            insert(table)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["user_id", "dedupe_key"])
            .returning(table.c.id)
        )
        return db.execute(statement).first() is not None


DEFAULT_CHANNELS: tuple[NotificationChannel, ...] = (InAppChannel(),)
