#!/usr/bin/env python
"""Evaluate the alert rules of every user who has active ones.

    python scripts/evaluate_alerts.py            # evaluate and save
    python scripts/evaluate_alerts.py --dry-run  # report what would happen, save nothing

There is no background worker in this build: alerts are otherwise evaluated only when a
user reads their notifications. This script is what a future cron job or worker would
run. It is idempotent: running it twice in a row creates nothing new the second time,
and it is safe to run while the API is serving requests.

Delivery is in-app only. Nothing here sends push, email or SMS.
"""

from __future__ import annotations

import sys

from sqlalchemy import select

from oddvex_api.alerts.service import evaluate_user_alerts
from oddvex_api.board import Board
from oddvex_api.cache import InMemoryTTLCache
from oddvex_api.config import Settings, get_settings
from oddvex_api.db import AlertRule, User, make_engine, make_session_factory
from oddvex_api.providers import SportsDataProvider, SyntheticProvider


def run(
    settings: Settings, provider: SportsDataProvider | None = None, dry_run: bool = False
) -> dict[str, int]:
    """Evaluate every user with active rules. Each user is one transaction."""
    provider = provider or SyntheticProvider(seed=settings.synthetic_seed)
    engine = make_engine(settings.database_url)
    totals = {"users": 0, "evaluated": 0, "fired": 0, "expired": 0, "failed": 0}
    try:
        with make_session_factory(engine)() as session:
            user_ids = list(
                session.scalars(
                    select(AlertRule.user_id)
                    .where(AlertRule.state == "active")
                    .distinct()
                    .order_by(AlertRule.user_id)
                )
            )
            session.rollback()
            for user_id in user_ids:
                user = session.get(User, user_id)
                if user is None or not user.is_active:
                    continue
                # A fresh board per user: one consistent "now" and no stale summaries.
                board = Board(provider, settings, InMemoryTTLCache())
                try:
                    result = evaluate_user_alerts(session, user, board.now, board)
                except Exception as exc:
                    session.rollback()
                    totals["failed"] += 1
                    print(f"user {user_id}: failed ({type(exc).__name__})", file=sys.stderr)
                    continue
                if dry_run:
                    session.rollback()
                else:
                    session.commit()
                totals["users"] += 1
                totals["evaluated"] += result.evaluated
                totals["fired"] += result.fired
                totals["expired"] += result.expired
    finally:
        engine.dispose()
    return totals


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    totals = run(get_settings(), dry_run=dry_run)
    prefix = "Dry run, nothing saved: " if dry_run else ""
    print(
        f"{prefix}{totals['users']} user(s), {totals['evaluated']} rule(s) evaluated, "
        f"{totals['fired']} fired, {totals['expired']} expired, {totals['failed']} failed."
    )
    return 1 if totals["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
