"""The archive's read paths, as the routes answer them.

Each is bounded to one event and market (at most one row per book), one player (one row
per market and book of each of the player's games with an offer in the look-back, 48
hours by default, at most two or three games, plus a few small queries per game of the
player near T for the prune check) or one event's status records (at most
``MAX_STATUS_ENTRIES``), so one request reads a few hundred rows at most. An odds, props
or placement read that a prune changed the rows under is made again, at most
``view.READ_ATTEMPTS`` times in all, so the bound is that many times the above.
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
from .capture import FLAG, archive_bytes, archive_disk_bytes
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
    PropsCoverageOut,
    StatusCoverageOut,
)
from .view import (
    READ_ATTEMPTS,
    ArchiveBusy,
    ArchiveView,
    Coverage,
    board_at,
    latest_odds_rows,
    props_at,
    prune_cutoffs,
)

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
    as of T when the event is covered then. Built again on a new view when a prune
    changed the archive while it was being read (``ArchiveView.settled``)."""
    for _ in range(READ_ATTEMPTS):
        view = ArchiveView(session, provider, as_of, settings)
        answer = _archived_odds(view, event_id, market)
        if view.settled():
            return answer
    raise ArchiveBusy("the prune kept changing the rows this read needs")


def _archived_odds(view: ArchiveView, event_id: str, market: str) -> ArchivedOddsOut:
    session, provider, as_of = view.session, view.base, view.as_of
    coverage = view.coverage(event_id)
    refs = _book_refs(provider)
    rows = (
        latest_odds_rows(session, provider.name, event_id, market, coverage.captured_at)
        if coverage.status == "captured" and coverage.captured_at is not None
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
    player = provider.get_player(player_id)
    read = props_at(
        session,
        provider.name,
        player_id,
        market,
        as_of,
        settings,
        team_id=player.team_id if player is not None else None,
    )
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
        for row in read.rows
    ]
    return ArchivedPropsOut(
        requested_as_of=as_of,
        data_mode=provider.data_mode,  # type: ignore[arg-type]
        coverage=PropsCoverageOut(status=read.status, captured_at=read.captured_at),
        offers=offers,
        pruned_event_ids=read.pruned_event_ids,
    )


def archived_status(
    session: Session,
    provider: SportsDataProvider,
    settings: Settings,
    event_id: str,
    as_of: datetime,
) -> ArchivedStatusOut:
    """The latest status record per (team, player, kind) of one event at or before T.

    A record is stored when it changes and kept ``snapshot_keep_days``; one that has not
    changed since before the keep horizon is gone, and the answer says from when records
    are kept (``kept_from``). With nothing found the answer is ``not_captured``, or
    ``archive_pruned`` when T is before the keep horizon."""
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
    entries = [
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
    ]
    keep_cutoff = prune_cutoffs(session)[1]
    if entries:
        coverage = StatusCoverageOut(
            status="captured",
            captured_at=max(entry.captured_at for entry in entries),
            kept_from=keep_cutoff,
        )
    else:
        removed = keep_cutoff is not None and as_of < keep_cutoff
        coverage = StatusCoverageOut(
            status="archive_pruned" if removed else "not_captured", kept_from=keep_cutoff
        )
    return ArchivedStatusOut(
        requested_as_of=as_of,
        data_mode=provider.data_mode,  # type: ignore[arg-type]
        coverage=coverage,
        entries=entries,
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
        disk_bytes=archive_disk_bytes(session),
        max_bytes=settings.snapshot_max_bytes,
        max_disk_bytes=settings.snapshot_max_disk_bytes,
        retention_days=settings.snapshot_retention_days,
        keep_days=max(settings.snapshot_keep_days, settings.snapshot_retention_days),
        rows=ArchiveRowCountsOut(
            odds=count(ArchivedOdds),
            props=count(ArchivedProp),
            events=count(ArchivedEvent),
            status=count(ArchivedStatus),
            runs=count(SnapshotRun),
        ),
        last_runs=[_run_out(run) for run in runs],
    )


def _run_out(run: SnapshotRun) -> ArchiveRunOut:
    out = ArchiveRunOut(
        kind=run.kind,
        captured_at=run.captured_at,
        status=run.status,
        rows_written=run.rows_written,
        rows_deleted=run.rows_deleted,
        finished_at=run.finished_at,
    )
    if run.kind != "reclaim":
        return out
    detail = run.detail or {}
    return out.model_copy(
        update={
            "indexes_rebuilt": len(detail.get("rebuilt") or {}),
            "indexes_dropped": len(detail.get("dropped") or {}),
            "indexes_failed": len(detail.get("failed") or {}),
            "bytes_freed": int(detail.get("freed_bytes") or 0),
        }
    )


__all__ = [
    "MAX_STATUS_ENTRIES",
    "archive_stats",
    "archived_odds",
    "archived_props",
    "archived_status",
    "coverage_out",
]
