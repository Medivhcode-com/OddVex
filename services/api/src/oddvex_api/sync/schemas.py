from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SyncProviderOut(BaseModel):
    key: str
    name: str
    description: str
    is_mock: bool
    requires_credentials: bool


class SyncConnectionCreate(BaseModel):
    provider: str = Field(default="mock", max_length=40)
    label: str | None = Field(default=None, min_length=1, max_length=120)
    simulate_failures: int = Field(
        default=0,
        ge=0,
        le=20,
        description=(
            "Mock provider only: how many upcoming fetch attempts fail with a retryable "
            "error. Lets clients and tests exercise the failure path."
        ),
    )


class SyncRunOut(BaseModel):
    id: str
    connection_id: str
    status: Literal["running", "succeeded", "failed"]
    attempts: int
    fetched_count: int
    imported_count: int
    duplicate_count: int = Field(description="Bets skipped because they were already imported.")
    retryable: bool = Field(description="For failed runs: whether trying again may succeed.")
    error_message: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class SyncConnectionOut(BaseModel):
    id: str
    provider: str
    provider_name: str
    is_mock: bool
    status: Literal["active"]
    label: str
    created_at: datetime
    last_synced_at: datetime | None = None
    bet_count: int = Field(description="Bets currently linked to this connection.")
    last_run: SyncRunOut | None = None


class SyncConnectionDeleteOut(BaseModel):
    deleted: Literal[True]
    bets_deleted: int
    bets_kept: int
