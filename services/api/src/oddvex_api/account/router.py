"""Account data export. Scoped to the authenticated user."""

from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import select

from ..alerts import service as alerts_service
from ..auth.schemas import UserOut
from ..bets import service as bets_service
from ..db import (
    AlertRule,
    AuditLog,
    Bet,
    Notification,
    SyncConnection,
    SyncImportRun,
    WatchlistItem,
    utcnow,
)
from ..deps import BoardDep, CurrentUserDep, DbDep, write_audit
from ..errors import AUTH_ERROR_RESPONSES
from ..notifications import service as notifications_service
from ..sync import service as sync_service
from ..watchlist import service as watchlist_service
from .schemas import AccountExportOut, ExportAuditEntryOut

router = APIRouter(tags=["auth"])


@router.get(
    "/me/export",
    response_model=AccountExportOut,
    operation_id="export_my_data",
    summary="Download everything stored about your account",
    description=(
        "One JSON document with your profile, bets, watchlist, alert rules, notifications, "
        "notification preferences, staking reminder, sync connections, import runs and "
        "your own audit entries. It never contains the password hash. The export "
        "itself is recorded in the audit log."
    ),
    responses=AUTH_ERROR_RESPONSES,
)
def export_my_data(
    user: CurrentUserDep, db: DbDep, board: BoardDep, request: Request
) -> AccountExportOut:
    write_audit(
        db, request, "account.export", user_id=user.id, entity_type="user", entity_id=user.id
    )
    db.commit()

    bets = db.scalars(select(Bet).where(Bet.user_id == user.id).order_by(Bet.placed_at, Bet.id))
    watchlist = db.scalars(
        select(WatchlistItem)
        .where(WatchlistItem.user_id == user.id)
        .order_by(WatchlistItem.created_at, WatchlistItem.id)
    )
    connections = list(
        db.scalars(
            select(SyncConnection)
            .where(SyncConnection.user_id == user.id)
            .order_by(SyncConnection.created_at, SyncConnection.id)
        )
    )
    runs = db.scalars(
        select(SyncImportRun)
        .join(SyncConnection, SyncImportRun.connection_id == SyncConnection.id)
        .where(SyncConnection.user_id == user.id)
        .order_by(SyncImportRun.started_at, SyncImportRun.id)
    )
    audit = db.scalars(
        select(AuditLog)
        .where(AuditLog.user_id == user.id)
        .order_by(AuditLog.created_at, AuditLog.id)
    )
    alerts = db.scalars(
        select(AlertRule)
        .where(AlertRule.user_id == user.id)
        .order_by(AlertRule.created_at, AlertRule.id)
    )
    notifications = db.scalars(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at, Notification.id)
    )
    registry = request.app.state.sync_registry
    return AccountExportOut(
        exported_at=utcnow(),
        format_version=1,
        user=UserOut.model_validate(user),
        bets=[bets_service.bet_out(bet) for bet in bets],
        watchlist=[watchlist_service.item_out(board, item) for item in watchlist],
        sync_connections=[
            sync_service.connection_out(db, c, registry.get(c.provider)) for c in connections
        ],
        sync_runs=[sync_service.run_out(run) for run in runs],
        audit_log=[
            ExportAuditEntryOut(
                id=row.id,
                created_at=row.created_at,
                action=row.action,
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                ip=row.ip,
                request_id=row.request_id,
                details=row.details,
            )
            for row in audit
        ],
        alerts=[alerts_service.rule_out(board, rule) for rule in alerts],
        notifications=[notifications_service.notification_out(row) for row in notifications],
        notification_preferences=notifications_service.preferences_out(db, user.id),
        stake_reminder=notifications_service.stake_reminder_out(db, user.id, board.now),
    )
