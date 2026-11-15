from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ..auth.schemas import UserOut
from ..bets.schemas import BetOut
from ..sync.schemas import SyncConnectionOut, SyncRunOut
from ..watchlist.schemas import WatchlistItemOut


class ExportAuditEntryOut(BaseModel):
    id: str
    created_at: datetime
    action: str
    entity_type: str | None = None
    entity_id: str | None = None
    ip: str | None = None
    request_id: str | None = None
    details: dict[str, Any] | None = None


class AccountExportOut(BaseModel):
    """Everything OddVex stores about one account. Never contains the password hash."""

    exported_at: datetime
    format_version: int = Field(default=1, description="Version of this document's layout.")
    user: UserOut
    bets: list[BetOut]
    watchlist: list[WatchlistItemOut]
    sync_connections: list[SyncConnectionOut]
    sync_runs: list[SyncRunOut]
    audit_log: list[ExportAuditEntryOut] = Field(
        description="Your own audit entries, oldest first, including this export."
    )
