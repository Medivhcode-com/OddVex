#!/usr/bin/env python
"""Create the demo account and its sample bets. Safe to run more than once.

    python scripts/seed_demo.py

Login: demo@oddvex.test / value of ODDVEX_DEMO_PASSWORD (dev default: oddvex-demo-2026).
Refuses to run when ODDVEX_ENV=production unless --allow-production is passed.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime

from oddvex_api.config import get_settings
from oddvex_api.db import Base, make_engine, make_session_factory
from oddvex_api.seed import DEMO_EMAIL, seed_demo


def main(argv: list[str]) -> int:
    settings = get_settings()
    if settings.is_production and "--allow-production" not in argv:
        print("Refusing to seed demo data when ODDVEX_ENV=production.", file=sys.stderr)
        return 2
    engine = make_engine(settings.database_url)
    if settings.should_auto_create_tables:
        Base.metadata.create_all(engine)
    with make_session_factory(engine)() as session:
        created = seed_demo(session, settings.demo_password, datetime.now(UTC))
    print(f"Demo user {DEMO_EMAIL} ready; {created} bet(s) created this run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
