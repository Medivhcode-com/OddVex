#!/usr/bin/env python
"""Create the demo account, its sample bets, alert rules and notifications. Safe to run
more than once.

    python scripts/seed_demo.py

Login: demo@oddvex.test / value of ODDVEX_DEMO_PASSWORD (dev default: oddvex-demo-2026).
The demo user's email counts as verified.

An administrator, admin@oddvex.test (same password), is created only when
ODDVEX_ADMIN_EMAILS lists that address. Without it no administrator is created:

    ODDVEX_ADMIN_EMAILS=admin@oddvex.test python scripts/seed_demo.py

Community demo data (fictional profiles with picks, comments, follows and likes, and a
public profile ``demo_bettor`` for the demo user) is added when the ``community`` flag is
on in the target database. ``--with-community`` turns the ``community`` and
``community_leaderboard`` flags on in that database first:

    python scripts/seed_demo.py --with-community

Refuses to run when ODDVEX_ENV=production unless --allow-production is passed.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime

from sqlalchemy import func, select

from oddvex_api.config import get_settings
from oddvex_api.db import (
    AlertRule,
    Base,
    CommunityPick,
    CommunityProfile,
    Notification,
    User,
    make_engine,
    make_session_factory,
)
from oddvex_api.flags import service as flags
from oddvex_api.providers import SyntheticProvider
from oddvex_api.seed import DEMO_ADMIN_EMAIL, DEMO_EMAIL, seed_demo


def main(argv: list[str]) -> int:
    settings = get_settings()
    if settings.is_production and "--allow-production" not in argv:
        print("Refusing to seed demo data when ODDVEX_ENV=production.", file=sys.stderr)
        return 2
    engine = make_engine(settings.database_url)
    if settings.should_auto_create_tables:
        Base.metadata.create_all(engine)
    with make_session_factory(engine)() as session:
        now = datetime.now(UTC)
        # Same seed as the app, so the gradeable demo bets point at events the API serves.
        provider = SyntheticProvider(seed=settings.synthetic_seed, clock=lambda: now)
        created = seed_demo(
            session,
            settings.demo_password,
            now,
            provider=provider,
            settings=settings,
            with_community="--with-community" in argv,
        )
        community_on = flags.is_enabled(session, "community", settings)
        profiles = session.scalar(select(func.count()).select_from(CommunityProfile))
        picks = session.scalar(select(func.count()).select_from(CommunityPick))
        graded = session.scalar(
            select(func.count()).select_from(CommunityPick).where(CommunityPick.status == "graded")
        )
        user_id = session.scalar(select(User.id).where(User.email == DEMO_EMAIL))
        alerts = session.scalar(
            select(func.count()).select_from(AlertRule).where(AlertRule.user_id == user_id)
        )
        notifications = session.scalar(
            select(func.count()).select_from(Notification).where(Notification.user_id == user_id)
        )
        admin_role = session.scalar(select(User.role).where(User.email == DEMO_ADMIN_EMAIL))
    print(f"Demo user {DEMO_EMAIL} ready; {created} bet(s) created this run.")
    print(f"The demo user has {alerts} alert rule(s) and {notifications} notification(s).")
    if community_on:
        print(
            f"Community: {profiles} fictional profile(s), {picks} pick(s), {graded} graded. "
            "The demo user's handle is demo_bettor."
        )
    else:
        print("Community flag is off: no community data (pass --with-community to add it).")
    if DEMO_ADMIN_EMAIL in settings.admin_email_set:
        print(f"Admin user {DEMO_ADMIN_EMAIL} ready (role: {admin_role}).")
    else:
        print(f"No admin user created: add {DEMO_ADMIN_EMAIL} to ODDVEX_ADMIN_EMAILS to get one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
