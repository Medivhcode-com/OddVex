"""Lazy alert evaluation: run a user's rules when they read their notifications.

There is no background worker. Rules are evaluated when the app asks for
notifications (at most once per ``ODDVEX_ALERT_EVAL_MIN_SECONDS`` per user), when the
client calls ``POST /v1/alerts/evaluate``, or when ``scripts/evaluate_alerts.py`` runs.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..board import Board
from ..db import AlertRule, User
from . import service

logger = logging.getLogger("oddvex.alerts")

_MAX_TRACKED_USERS = 50_000


class EvaluationThrottle:
    """Remembers, in process memory, when each user's rules were last evaluated."""

    def __init__(self) -> None:
        self._last: dict[str, datetime] = {}
        self._lock = threading.Lock()

    def should_run(self, user_id: str, now: datetime, min_seconds: int) -> bool:
        """True (and the run is recorded) unless the last run was under ``min_seconds`` ago."""
        if min_seconds <= 0:
            return True
        with self._lock:
            last = self._last.get(user_id)
            if last is not None and 0 <= (now - last).total_seconds() < min_seconds:
                return False
            if len(self._last) >= _MAX_TRACKED_USERS:
                self._last.clear()
            self._last[user_id] = now
            return True

    def mark(self, user_id: str, now: datetime) -> None:
        with self._lock:
            self._last[user_id] = now

    def forget(self, user_id: str) -> None:
        with self._lock:
            self._last.pop(user_id, None)


def evaluate_if_due(request: Request, db: Session, user: User, board: Board) -> None:
    """Evaluate ``user``'s rules unless that happened recently. Never raises.

    A failure here must not stop the user from reading the notifications they already
    have, so errors are logged and the transaction is rolled back.
    """
    throttle: EvaluationThrottle = request.app.state.alert_throttle
    min_seconds: int = request.app.state.settings.alert_eval_min_seconds
    if not throttle.should_run(user.id, board.now, min_seconds):
        return
    try:
        has_active = db.scalar(
            select(AlertRule.id)
            .where(AlertRule.user_id == user.id, AlertRule.state == "active")
            .limit(1)
        )
        if has_active is None:
            return
        service.evaluate_user_alerts(db, user, board.now, board, request)
        db.commit()
    except Exception:
        db.rollback()
        throttle.forget(user.id)
        logger.exception("alert_evaluation_failed", extra={"user_id": user.id})
