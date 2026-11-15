"""Admin overview (role ``admin`` only)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from .. import __version__
from ..db import AuditLog, Bet, SyncConnection, User
from ..deps import AdminDep, DbDep, ProviderDep, SettingsDep
from ..errors import AUTH_ERROR_RESPONSES, ErrorResponse

router = APIRouter(prefix="/admin", tags=["admin"])


class ProviderHealthOut(BaseModel):
    provider: str
    data_mode: str
    status: Literal["ok", "degraded", "down"]
    checked_at: datetime
    detail: str


class AuditEntryOut(BaseModel):
    id: str
    created_at: datetime
    action: str
    user_id: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    request_id: str | None = None
    details: dict[str, Any] | None = None


class AdminOverviewOut(BaseModel):
    version: str
    environment: str
    user_count: int
    bet_count: int
    sync_connection_count: int
    provider_health: ProviderHealthOut
    recent_audit: list[AuditEntryOut]


@router.get(
    "/overview",
    response_model=AdminOverviewOut,
    operation_id="get_admin_overview",
    summary="Counts, provider health and recent audit entries",
    responses={
        **AUTH_ERROR_RESPONSES,
        403: {"model": ErrorResponse, "description": "Administrator role required"},
    },
)
def get_admin_overview(
    admin: AdminDep, db: DbDep, provider: ProviderDep, settings: SettingsDep
) -> AdminOverviewOut:
    def count(model: type) -> int:
        return int(db.scalar(select(func.count()).select_from(model)) or 0)

    audit = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id).limit(25))
    return AdminOverviewOut(
        version=__version__,
        environment=settings.env,
        user_count=count(User),
        bet_count=count(Bet),
        sync_connection_count=count(SyncConnection),
        provider_health=ProviderHealthOut(**provider.health().model_dump()),
        recent_audit=[
            AuditEntryOut(
                id=row.id,
                created_at=row.created_at,
                action=row.action,
                user_id=row.user_id,
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                request_id=row.request_id,
                details=row.details,
            )
            for row in audit
        ],
    )
