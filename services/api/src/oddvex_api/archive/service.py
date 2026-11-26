"""The archive's read paths, as the routes answer them.

Each is bounded to one event and market (at most one row per book), one player (one row
per market and book of each of the player's games with an offer in the last 48 hours,
at most two or three games) or one event's status records (at most
``MAX_STATUS_ENTRIES``), so one request reads a few hundred rows at most.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..db import (
    ArchivedEvent,
    ArchivedOdds,
    ArchivedProp,
    ArchivedStatus,
    SnapshotRun,
)
from ..flags import service as flags
from ..providers import SportsDataProvider
from ..schemas import SportsbookRef, price_from_american
from .capture import FLAG, archive_bytes
from .schemas import (
    ArchivedOddsOut,
    ArchivedOutcomeOut,
    ArchivedPropOut,
    ArchivedPropsOut,
    ArchivedQuoteOut,
    ArchivedStatusEntryOut,
    ArchivedStatusOut,
    ArchiveRowCountsOut,
    ArchiveRunOut,
    ArchiveStatsOut,
    CoverageOut,
)
from .view import ArchiveView, Coverage, board_at, latest_odds_rows, latest_prop_rows

#: Most status entries one request returns.
MAX_STATUS_ENTRIES = 500


def coverage_out(coverage: Coverage) -> CoverageOut:
    return CoverageOut(
        status=coverage.status, captured_at=coverage.captured_at, run_id=coverage.run_id
    )


def _book_refs(provider: SportsDataProvider) -> dict[str, SportsbookRef]:
    return {b.id: SportsbookRef(key=b.key, name=b.name) for b in provider.list_sportsbooks()}


def _ref(refs: dict[str, SportsbookRef], sportsbook_id: str) -> SportsbookRef:
    return refs.get(sportsbook_id) or SportsbookRef(key=sportsbook_id, name=sportsbook_id)


def archived_odds(
    session: Session,
    provider: SportsDataProvider,
    settings: Settings,
    event_id: str,
    market: str,
    as_of: datetime,
) -> ArchivedOddsOut:
    """Every book's stored quote for one event and market as of T, and the odds comparison
    as of T when the event is covered then."""
    view = ArchiveView(session, provider, as_of, settings)
    coverage = view.coverage(event_id)
    refs = _book_refs(provider)
    rows = (
        latest_odds_rows(session, provider.name, event_id, market, coverage.captured_at)
        if coverage.captured_at is not None
        else []
    )
    order = {key: i for i, key in enumerate(refs)}
    rows.sort(key=lambda r: (order.get(r.sportsbook_id, len(order)), r.sportsbook_id))
    quotes = [
        ArchivedQuoteOut(
            sportsbook=_ref(refs, row.sportsbook_id),
            status=row.status,  # type: ignore[arg-type]
            last_updated=row.last_updated,
            captured_at=row.captured_at,
            fetched_at=row.fetched_at,
            provider=row.provider,
            provider_id=row.provider_id,
            outcomes=[
                ArchivedOutcomeOut(key=key, name=name, line=line, price=price_from_american(price))
                for key, name, line, price in row.outcomes
            ],
        )
        for row in rows
    ]
    odds = None
    event = view.get_event(event_id)
    if coverage.status == "captured" and event is not None and market in event.markets:
        odds = board_at(view, coverage).event_odds(event, market)
    return ArchivedOddsOut(
        requested_as_of=as_of,
        coverage=coverage_out(coverage),
        data_mode=provider.data_mode,  # type: ignore[arg-type]
        quotes=quotes,
        odds=odds,
    )


def archived_props(
    session: Session,
    provider: SportsDataProvider,
    settings: Settings,
    player_id: str,
    market: str | None,
    as_of: datetime,
) -> ArchivedPropsOut:
    refs = _book_refs(provider)
    offers = [
        ArchivedPropOut(
            sportsbook=_ref(refs, row.sportsbook_id),
            event_id=row.event_id,
            market=row.market,
            status=row.status,  # type: ignore[arg-type]
            last_updated=row.last_updated,
            line=None if row.line is None else float(row.line),
            over=None if row.over_american is None else price_from_american(row.over_american),
            under=None if row.under_american is None else price_from_american(row.under_american),
            captured_at=row.captured_at,
            fetched_at=row.fetched_at,
            provider=row.provider,
            provider_id=row.provider_id,
        )
        for row in latest_prop_rows(session, provider.name, player_id, market, as_of, settings)
    ]
    return ArchivedPropsOut(
        requested_as_of=as_of,
        data_mode=provider.data_mode,  # type: ignore[arg-type]
        offers=offers,
    )


def archived_status(
    session: Session,
    provider: SportsDataProvider,
    settings: Settings,
    event_id: str,
    as_of: datetime,
) -> ArchivedStatusOut:
    """The latest status record per (team, player, kind) of one event at or before T."""
    s = ArchivedStatus
    newest = (
        select(s.team_id, s.player_id, s.kind, func.max(s.captured_at).label("at"))
        .where(s.provider == provider.name, s.event_id == event_id, s.captured_at <= as_of)
        .group_by(s.team_id, s.player_id, s.kind)
        .subquery()
    )
    rows = session.scalars(
        select(s)
        .join(
            newest,
            and_(
                s.provider == provider.name,
                s.event_id == event_id,
                s.team_id.is_not_distinct_from(newest.c.team_id),
                s.player_id.is_not_distinct_from(newest.c.player_id),
                s.kind == newest.c.kind,
                s.captured_at == newest.c.at,
            ),
        )
        .order_by(s.kind, s.team_id, s.player_id, s.id)
        .limit(MAX_STATUS_ENTRIES)
    )
    return ArchivedStatusOut(
        requested_as_of=as_of,
        data_mode=provider.data_mode,  # type: ignore[arg-type]
        entries=[
            ArchivedStatusEntryOut(
                kind=row.kind,  # type: ignore[arg-type]
                status=row.status,
                source=row.source,
                reported_at=row.reported_at,
                captured_at=row.captured_at,
                event_id=row.event_id,
                team_id=row.team_id,
                player_id=row.player_id,
                provider=row.provider,
                provider_id=row.provider_id,
            )
            for row in rows
        ],
    )


def archive_stats(session: Session, settings: Settings) -> ArchiveStatsOut:
    """Size, row counts and the latest run of each kind, for administrators."""

    def count(model: type[object]) -> int:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)  # type: ignore[arg-type]

    newest = (
        select(SnapshotRun.kind, func.max(SnapshotRun.id).label("id"))
        .group_by(SnapshotRun.kind)
        .subquery()
    )
    runs = session.scalars(
        select(SnapshotRun).join(newest, SnapshotRun.id == newest.c.id).order_by(SnapshotRun.kind)
    )
    return ArchiveStatsOut(
        enabled=flags.is_enabled(session, FLAG, settings),
        approx_bytes=archive_bytes(session),
        max_bytes=settings.snapshot_max_bytes,
        retention_days=settings.snapshot_retention_days,
        keep_days=max(settings.snapshot_keep_days, settings.snapshot_retention_days),
        rows=ArchiveRowCountsOut(
            odds=count(ArchivedOdds),
            props=count(ArchivedProp),
            events=count(ArchivedEvent),
            status=count(ArchivedStatus),
            runs=count(SnapshotRun),
        ),
        last_runs=[
            ArchiveRunOut(
                kind=run.kind,
                captured_at=run.captured_at,
                status=run.status,
                rows_written=run.rows_written,
                rows_deleted=run.rows_deleted,
            )
            for run in runs
        ],
    )


__all__ = [
    "MAX_STATUS_ENTRIES",
    "archive_stats",
    "archived_odds",
    "archived_props",
    "archived_status",
    "coverage_out",
]
