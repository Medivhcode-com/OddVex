"""Sportsbook account sync routes (mock provider only)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import Bet, SyncConnection, SyncImportRun, utcnow
from ..deps import CurrentUserDep, DbDep, SettingsDep, write_audit
from ..errors import (
    AUTH_ERROR_RESPONSES,
    NOT_FOUND_RESPONSE,
    ApiError,
    ErrorResponse,
    not_found,
)
from . import service
from .base import SyncProvider
from .registry import SyncRegistry
from .schemas import (
    SyncConnectionCreate,
    SyncConnectionDeleteOut,
    SyncConnectionOut,
    SyncProviderOut,
    SyncRunOut,
)

router = APIRouter(prefix="/sync", tags=["sync"], responses=AUTH_ERROR_RESPONSES)


def _registry(request: Request) -> SyncRegistry:
    return request.app.state.sync_registry  # type: ignore[no-any-return]


def _owned_connection(db: Session, user_id: str, connection_id: str) -> SyncConnection:
    connection = db.scalar(
        select(SyncConnection).where(
            SyncConnection.id == connection_id, SyncConnection.user_id == user_id
        )
    )
    if connection is None:
        raise not_found("Sync connection", connection_id)
    return connection


def _provider(request: Request, key: str) -> SyncProvider:
    provider = _registry(request).get(key)
    if provider is None:
        raise ApiError(422, "unknown_sync_provider", f"Sync provider '{key}' is not supported")
    return provider


@router.get(
    "/providers",
    response_model=list[SyncProviderOut],
    operation_id="list_sync_providers",
    summary="Available sync providers",
)
def list_sync_providers(user: CurrentUserDep, request: Request) -> list[SyncProviderOut]:
    return [
        SyncProviderOut(
            key=p.info.key,
            name=p.info.name,
            description=p.info.description,
            is_mock=p.info.is_mock,
            requires_credentials=p.info.requires_credentials,
        )
        for p in _registry(request).list()
    ]


@router.get(
    "/connections",
    response_model=list[SyncConnectionOut],
    operation_id="list_sync_connections",
    summary="Your sync connections",
)
def list_sync_connections(
    user: CurrentUserDep, db: DbDep, request: Request
) -> list[SyncConnectionOut]:
    connections = db.scalars(
        select(SyncConnection)
        .where(SyncConnection.user_id == user.id)
        .order_by(SyncConnection.created_at, SyncConnection.id)
    )
    registry = _registry(request)
    return [service.connection_out(db, c, registry.get(c.provider)) for c in connections]


@router.post(
    "/connections",
    response_model=SyncConnectionOut,
    status_code=201,
    operation_id="create_sync_connection",
    summary="Connect an account (mock authorization, no credentials)",
    responses={409: {"model": ErrorResponse, "description": "Already connected"}},
)
def create_sync_connection(
    body: SyncConnectionCreate, user: CurrentUserDep, db: DbDep, request: Request
) -> SyncConnectionOut:
    provider = _provider(request, body.provider)
    already = db.scalar(
        select(SyncConnection.id).where(
            SyncConnection.user_id == user.id, SyncConnection.provider == provider.info.key
        )
    )
    if already is not None:
        raise ApiError(
            409, "already_connected", "This provider is already connected to your account"
        )
    authorization = provider.authorize(
        {"label": body.label, "fail_next": body.simulate_failures}, utcnow()
    )
    connection = SyncConnection(
        user_id=user.id,
        provider=provider.info.key,
        status="active",
        label=authorization.label,
        provider_state=authorization.state,
    )
    db.add(connection)
    db.flush()
    write_audit(
        db,
        request,
        "sync.connect",
        user_id=user.id,
        entity_type="sync_connection",
        entity_id=connection.id,
        details={"provider": provider.info.key},
    )
    db.commit()
    return service.connection_out(db, connection, provider)


@router.post(
    "/connections/{connection_id}/sync",
    response_model=SyncRunOut,
    operation_id="run_sync",
    summary="Import bets from a connection",
    description=(
        "Idempotent: bets are de-duplicated on provider + external bet id, so running this "
        "again never creates duplicates. Retryable provider errors are retried up to "
        "`ODDVEX_SYNC_MAX_ATTEMPTS` times. If the import still fails the run is recorded "
        "with status `failed` and this returns 502 with `details.run_id` and "
        "`details.retryable`."
    ),
    responses={
        **NOT_FOUND_RESPONSE,
        409: {"model": ErrorResponse, "description": "A concurrent import collided; try again"},
        502: {"model": ErrorResponse, "description": "The provider failed; the run is recorded"},
    },
)
def run_sync(
    connection_id: str, user: CurrentUserDep, db: DbDep, settings: SettingsDep, request: Request
) -> SyncRunOut:
    connection = _owned_connection(db, user.id, connection_id)
    provider = _provider(request, connection.provider)
    run = service.run_import(db, connection, provider, settings.sync_max_attempts)
    try:
        db.flush()
    except IntegrityError as exc:
        # Another import of the same account committed between the duplicate check and
        # this insert. Nothing from this run is kept; the other run has the bets.
        db.rollback()
        raise ApiError(
            409,
            "sync_conflict",
            "Another import of this account was running at the same time. Try again.",
            details={"retryable": True},
        ) from exc
    write_audit(
        db,
        request,
        "sync.import" if run.status == "succeeded" else "sync.import_failed",
        user_id=user.id,
        entity_type="sync_connection",
        entity_id=connection.id,
        details={
            "run_id": run.id,
            "attempts": run.attempts,
            "imported": run.imported_count,
            "duplicates": run.duplicate_count,
        },
    )
    db.commit()
    if run.status != "succeeded":
        raise ApiError(
            502,
            "sync_failed",
            run.error_message or "The import failed",
            details={"run_id": run.id, "retryable": run.retryable, "attempts": run.attempts},
        )
    return service.run_out(run)


@router.get(
    "/connections/{connection_id}/runs",
    response_model=list[SyncRunOut],
    operation_id="list_sync_runs",
    summary="Import history for a connection, newest first",
    responses=NOT_FOUND_RESPONSE,
)
def list_sync_runs(connection_id: str, user: CurrentUserDep, db: DbDep) -> list[SyncRunOut]:
    connection = _owned_connection(db, user.id, connection_id)
    runs = db.scalars(
        select(SyncImportRun)
        .where(SyncImportRun.connection_id == connection.id)
        .order_by(SyncImportRun.started_at.desc(), SyncImportRun.id)
        .limit(100)
    )
    return [service.run_out(run) for run in runs]


@router.delete(
    "/connections/{connection_id}",
    response_model=SyncConnectionDeleteOut,
    operation_id="delete_sync_connection",
    summary="Disconnect an account",
    description=(
        "Removes the connection and its import history. With `delete_data=true` the bets "
        "imported through it are deleted too; otherwise they are kept as tracked bets."
    ),
    responses=NOT_FOUND_RESPONSE,
)
def delete_sync_connection(
    connection_id: str,
    user: CurrentUserDep,
    db: DbDep,
    request: Request,
    delete_data: Annotated[bool, Query()] = False,
) -> SyncConnectionDeleteOut:
    connection = _owned_connection(db, user.id, connection_id)
    linked = int(
        db.scalar(
            select(func.count())
            .select_from(Bet)
            .where(Bet.sync_connection_id == connection.id, Bet.user_id == user.id)
        )
        or 0
    )
    if delete_data:
        for bet in db.scalars(
            select(Bet).where(Bet.sync_connection_id == connection.id, Bet.user_id == user.id)
        ):
            db.delete(bet)
    else:
        db.execute(
            update(Bet)
            .where(Bet.sync_connection_id == connection.id)
            .values(sync_connection_id=None)
        )
    db.flush()
    db.execute(delete(SyncImportRun).where(SyncImportRun.connection_id == connection.id))
    db.delete(connection)
    write_audit(
        db,
        request,
        "sync.disconnect",
        user_id=user.id,
        entity_type="sync_connection",
        entity_id=connection_id,
        details={"delete_data": delete_data, "bets": linked},
    )
    db.commit()
    return SyncConnectionDeleteOut(
        deleted=True,
        bets_deleted=linked if delete_data else 0,
        bets_kept=0 if delete_data else linked,
    )
