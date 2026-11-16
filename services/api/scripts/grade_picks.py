#!/usr/bin/env python
"""Grade pending community picks whose events are final.

    python scripts/grade_picks.py            # grade and save
    python scripts/grade_picks.py --dry-run  # report what would happen, save nothing

There is no background worker in this build: picks are otherwise graded when someone
reads the community (at most once per ODDVEX_COMMUNITY_GRADE_MIN_SECONDS). This script is
what a future cron job or worker would run. It grades with the same function as the API
and the bet tracker's auto-settlement (quant.grade_leg), is idempotent, and is safe to
run while the API is serving requests. It runs whether or not the `community` flag is on.

A graded pick creates one in-app `pick_graded` notification for its author. Nothing here
sends push, email or SMS.
"""

from __future__ import annotations

import sys

from oddvex_api.community.service import grade_due_picks
from oddvex_api.config import Settings, get_settings
from oddvex_api.db import make_engine, make_session_factory
from oddvex_api.providers import SportsDataProvider, SyntheticProvider

#: Stops a run that keeps finding work, which would mean grading is not making progress.
MAX_PASSES = 200


def run(
    settings: Settings, provider: SportsDataProvider | None = None, dry_run: bool = False
) -> dict[str, int]:
    """Grade until a pass grades nothing new. Each pass is one transaction."""
    provider = provider or SyntheticProvider(seed=settings.synthetic_seed)
    engine = make_engine(settings.database_url)
    totals = {"passes": 0, "checked": 0, "graded": 0, "voided": 0}
    try:
        with make_session_factory(engine)() as session:
            for _ in range(MAX_PASSES):
                result = grade_due_picks(session, provider, provider.now())
                totals["passes"] += 1
                totals["checked"] = max(totals["checked"], result.checked)
                totals["graded"] += result.graded
                totals["voided"] += result.voided
                if dry_run:
                    session.rollback()
                    break
                session.commit()
                if not (result.graded or result.voided):
                    break
    finally:
        engine.dispose()
    return totals


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    totals = run(get_settings(), dry_run=dry_run)
    prefix = "Dry run, nothing saved: " if dry_run else ""
    print(
        f"{prefix}{totals['checked']} pending pick(s) past their start time checked, "
        f"{totals['graded']} graded, {totals['voided']} voided."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
