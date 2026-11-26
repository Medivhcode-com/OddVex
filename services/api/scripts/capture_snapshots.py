#!/usr/bin/env python
"""Capture the snapshot archive (P0.1) and prune it.

    python scripts/capture_snapshots.py               # capture what is due, prune when due
    python scripts/capture_snapshots.py --force       # capture now, whatever the intervals
    python scripts/capture_snapshots.py --prune-only  # prune when due (with --force: now)
    python scripts/capture_snapshots.py --dry-run     # say what a pass would capture; write nothing
    python scripts/capture_snapshots.py --stats       # print the archive's size and row counts

The worker container runs this every 120 s (``infrastructure/hostinger/compose.yaml``).
While the ``snapshot_archive`` flag is off it writes nothing and exits at once, so turning
the flag off stops all storage growth. On PostgreSQL an advisory lock stops two passes
from overlapping. It reads only the configured provider (synthetic unless set), never a
sportsbook. Exit status 1 when a capture or prune failed; the failure is recorded as a
``failed`` run with the exception's class name only.
"""

from __future__ import annotations

import sys

from sqlalchemy.orm import Session

from oddvex_api.archive.capture import FLAG, capture_pass, in_scope, is_due
from oddvex_api.archive.guard import install_archive_guard
from oddvex_api.archive.service import archive_stats
from oddvex_api.config import Settings, get_settings
from oddvex_api.db import make_engine
from oddvex_api.flags import service as flags
from oddvex_api.main import build_provider
from oddvex_api.providers import SportsDataProvider

OFF_MESSAGE = "Snapshot archive is off; nothing captured."


def _stats(settings: Settings) -> int:
    engine = make_engine(settings.database_url)
    try:
        with Session(engine) as session:
            stats = archive_stats(session, settings)
    finally:
        engine.dispose()
    rows = stats.rows
    print(
        f"Snapshot archive {'on' if stats.enabled else 'off'}: about {stats.approx_bytes:,} bytes "
        f"of {stats.max_bytes:,}; rows: {rows.odds:,} odds, {rows.props:,} props, "
        f"{rows.events:,} events, {rows.status:,} status, {rows.runs:,} runs."
    )
    for run in stats.last_runs:
        print(
            f"  last {run.kind}: {run.status} at {run.captured_at.isoformat()}, "
            f"{run.rows_written:,} written, {run.rows_deleted:,} deleted"
        )
    return 0


def _dry_run(settings: Settings, provider: SportsDataProvider) -> int:
    engine = make_engine(settings.database_url)
    try:
        with Session(engine) as session:
            if not flags.is_enabled(session, FLAG, settings):
                print(OFF_MESSAGE)
                return 0
            now = provider.now()
            odds_due = is_due(
                session, provider.name, "odds", now, settings.snapshot_odds_interval_seconds
            )
            props_due = is_due(
                session, provider.name, "props", now, settings.snapshot_props_interval_seconds
            )
    finally:
        engine.dispose()
    events = in_scope(provider, now, settings)
    quotes = sum(len(provider.get_odds(e.id, m)) for e in events for m in e.markets)
    print(
        f"Dry run, nothing saved: {len(events)} event(s) in scope with {quotes} quote(s); "
        f"odds {'due' if odds_due else 'not due'}, props {'due' if props_due else 'not due'}."
    )
    return 0


def main(argv: list[str]) -> int:
    settings = get_settings()
    if "--stats" in argv:
        return _stats(settings)
    provider = build_provider(settings)
    if "--dry-run" in argv:
        return _dry_run(settings, provider)
    install_archive_guard()
    prune_only = "--prune-only" in argv
    force = "--force" in argv
    engine = make_engine(settings.database_url)
    try:
        report = capture_pass(
            engine,
            provider,
            settings,
            force=force and not prune_only,
            capture=not prune_only,
            force_prune=force and prune_only,
        )
    finally:
        engine.dispose()
    if not report.enabled:
        print(OFF_MESSAGE)
        return 0
    if report.locked:
        print("Another capture is running; nothing done.")
        return 0
    parts = []
    for name, run in (("odds", report.odds), ("props", report.props), ("prune", report.prune)):
        if run is None:
            parts.append(f"{name} not due")
        elif name == "prune":
            parts.append(f"prune {run.status}, {run.rows_deleted} row(s) deleted")
        else:
            parts.append(
                f"{name} {run.status}, {run.rows_written} row(s) written, "
                f"{run.rows_unchanged} unchanged"
            )
    print("Snapshot archive: " + "; ".join(parts) + ".")
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
