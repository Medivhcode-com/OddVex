"""Admin routes (role ``admin`` only).

Every route here depends on :data:`AdminDep`, so anyone else gets 401 or 403. Every
change is written to the audit log with the acting administrator, the target and the
values before and after. Reading the overview, the user list or the email outbox is
audited too, coarsely: one ``admin.read`` row per request naming what was read, with no
payload. Responses never carry password hashes, tokens or email bodies.

Two routes act on a user's data rights for an owner who cannot sign in: the export
(the owner's own export document, produced by the same code) and the deletion (the
owner's own deletion, the same function). Both need a reason, which is audited.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from .. import __version__
from ..account import export as account_export
from ..account import service as account_service
from ..account.schemas import AccountExportOut
from ..config import Settings
from ..db import AuditLog, Bet, EmailOutbox, FeatureFlag, SyncConnection, User
from ..deps import AdminDep, DbDep, ProviderDep, SettingsDep, write_audit
from ..errors import (
    AUTH_ERROR_RESPONSES,
    NOT_FOUND_RESPONSE,
    RATE_LIMIT_RESPONSE,
    ApiError,
    ErrorResponse,
    not_found,
)
from ..flags import service as flags
from ..flags.catalog import KNOWN_FLAGS
from ..ratelimit import take_user_stream_slot
from ..textnorm import fold

_ADMIN_RESPONSES: dict[int | str, dict[str, Any]] = {
    **AUTH_ERROR_RESPONSES,
    403: {"model": ErrorResponse, "description": "Administrator role required"},
}

router = APIRouter(prefix="/admin", tags=["admin"])


def audit_admin_read(db: Session, request: Request, admin_id: str, resource: str) -> None:
    """One coarse ``admin.read`` row per request: who read which admin resource. The
    filters and the rows returned are deliberately not recorded. Commits."""
    write_audit(db, request, "admin.read", user_id=admin_id, entity_type=resource)
    db.commit()


Plan = Literal["free", "premium"]
UserStatus = Literal["active", "suspended"]


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
    admin: AdminDep, db: DbDep, provider: ProviderDep, settings: SettingsDep, request: Request
) -> AdminOverviewOut:
    def count(model: type) -> int:
        return int(db.scalar(select(func.count()).select_from(model)) or 0)

    audit = list(
        db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id).limit(25))
    )
    # Written after the rows above were read, so this request is not in its own answer.
    audit_admin_read(db, request, admin.id, "admin_overview")
    return AdminOverviewOut(
        version=__version__,
        environment=settings.env,
        user_count=count(User),
        bet_count=count(Bet),
        sync_connection_count=count(SyncConnection),
        provider_health=ProviderHealthOut(**provider.health().model_dump()),
        recent_audit=[_audit_entry(row) for row in audit],
    )


def _audit_entry(row: AuditLog) -> AuditEntryOut:
    return AuditEntryOut(
        id=row.id,
        created_at=row.created_at,
        action=row.action,
        user_id=row.user_id,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        request_id=row.request_id,
        details=row.details,
    )


# ---------------------------------------------------------------------- users
class AdminUserOut(BaseModel):
    id: str
    email: str
    display_name: str
    role: Literal["user", "admin"]
    plan: Plan
    status: UserStatus
    email_verified: bool
    created_at: datetime
    last_login_at: datetime | None = None
    bet_count: int


class AdminUserListOut(BaseModel):
    items: list[AdminUserOut]
    total: int = Field(description="Users matching the filters, before `limit` and `offset`.")
    limit: int
    offset: int


def _clean_reason(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) < 3:
        raise ValueError("a reason of at least 3 characters is required")
    return cleaned


class SuspendUserRequest(BaseModel):
    reason: str = Field(
        min_length=3,
        max_length=500,
        description="Why the account is suspended. Stored in the audit log only.",
    )

    @field_validator("reason")
    @classmethod
    def _strip(cls, value: str) -> str:
        return _clean_reason(value)


class ExportUserRequest(BaseModel):
    reason: str = Field(
        min_length=3,
        max_length=500,
        description=(
            "Why the account's data is exported, for example the reference of the "
            "owner's request. Stored in the audit log only, and kept there after the "
            "account is deleted: it must not contain the account's email address."
        ),
    )

    @field_validator("reason")
    @classmethod
    def _strip(cls, value: str) -> str:
        return _clean_reason(value)


class DeleteUserRequest(BaseModel):
    reason: str = Field(
        min_length=3,
        max_length=500,
        description=(
            "Why the account is deleted, for example the reference of the owner's "
            "request. Stored in the audit log only, and kept there after the account is "
            "gone: it must not contain the account's email address."
        ),
    )
    confirm_email: str = Field(
        min_length=1,
        max_length=320,
        description=(
            "The email address of the account to delete, typed again. Compared the way "
            "login compares addresses: surrounding spaces and letter case do not matter."
        ),
    )

    @field_validator("reason")
    @classmethod
    def _strip(cls, value: str) -> str:
        return _clean_reason(value)

    @field_validator("confirm_email")
    @classmethod
    def _as_login_does(cls, value: str) -> str:
        return value.strip().lower()


class SetUserPlanRequest(BaseModel):
    plan: Plan


def _bet_count(db: Session, user_id: str) -> int:
    return int(db.scalar(select(func.count()).select_from(Bet).where(Bet.user_id == user_id)) or 0)


def _user_out(user: User, bet_count: int) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,  # type: ignore[arg-type]
        plan=user.plan,  # type: ignore[arg-type]
        status=user.status,  # type: ignore[arg-type]
        email_verified=user.email_verified,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        bet_count=bet_count,
    )


def _user_or_404(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise not_found("User", user_id)
    return user


def _like(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@router.get(
    "/users",
    response_model=AdminUserListOut,
    operation_id="admin_list_users",
    summary="Users, newest first",
    description=(
        "`q` matches part of the email or display name, case-insensitively for any "
        "script, not only ASCII. Never returns password hashes or tokens. Each call is "
        "recorded in the audit log as `admin.read`."
    ),
    responses=_ADMIN_RESPONSES,
)
def admin_list_users(
    admin: AdminDep,
    db: DbDep,
    request: Request,
    q: Annotated[str | None, Query(max_length=120)] = None,
    status: Annotated[UserStatus | None, Query()] = None,
    plan: Annotated[Plan | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminUserListOut:
    filters: list[ColumnElement[bool]] = []
    if q and fold(q):
        # ``search_key`` is folded in Python (``textnorm``), so matching does not depend on
        # what the database's ``lower()`` can do. ``fold`` leaves no line break in the
        # term, so it cannot match across the email and the display name.
        filters.append(User.search_key.like(_like(fold(q)), escape="\\"))
    if status is not None:
        filters.append(User.status == status)
    if plan is not None:
        filters.append(User.plan == plan)
    total = int(db.scalar(select(func.count()).select_from(User).where(*filters)) or 0)
    bet_counts = (
        select(Bet.user_id, func.count().label("bet_count")).group_by(Bet.user_id).subquery()
    )
    rows = db.execute(
        select(User, func.coalesce(bet_counts.c.bet_count, 0))
        .outerjoin(bet_counts, bet_counts.c.user_id == User.id)
        .where(*filters)
        .order_by(User.created_at.desc(), User.id)
        .limit(limit)
        .offset(offset)
    )
    items = [_user_out(user, int(count)) for user, count in rows]
    audit_admin_read(db, request, admin.id, "admin_users")
    return AdminUserListOut(items=items, total=total, limit=limit, offset=offset)


def suspend_user(
    db: Session,
    request: Request,
    admin: User,
    user: User,
    reason: str,
    extra_details: dict[str, Any] | None = None,
) -> bool:
    """Suspend ``user`` and audit it. Returns False when they already were suspended.

    The one place an account is suspended: the admin route above and community
    moderation (``suspend_author``) both go through here. Not committed.
    """
    if user.id == admin.id:
        raise ApiError(409, "cannot_suspend_self", "You cannot suspend your own account")
    if user.role == "admin":
        raise ApiError(409, "cannot_suspend_admin", "An administrator cannot be suspended")
    if user.status == "suspended":
        return False
    before = user.status
    user.status = "suspended"
    write_audit(
        db,
        request,
        "admin.user_suspended",
        user_id=admin.id,
        entity_type="user",
        entity_id=user.id,
        details={
            "before": {"status": before},
            "after": {"status": user.status},
            "reason": reason,
            **(extra_details or {}),
        },
    )
    return True


_SUSPEND_CONFLICT: dict[int | str, dict[str, Any]] = {
    409: {"model": ErrorResponse, "description": "An administrator cannot be suspended"}
}


@router.post(
    "/users/{user_id}/suspend",
    response_model=AdminUserOut,
    operation_id="admin_suspend_user",
    summary="Suspend a user",
    description=(
        "From then on the user's access tokens are rejected with `401 account_suspended` "
        "and login answers `403 account_suspended`. Their data is kept. An administrator "
        "cannot suspend themselves or another administrator (`409`). Suspending a "
        "suspended user changes nothing."
    ),
    responses={**_ADMIN_RESPONSES, **NOT_FOUND_RESPONSE, **_SUSPEND_CONFLICT},
)
def admin_suspend_user(
    user_id: str, body: SuspendUserRequest, admin: AdminDep, db: DbDep, request: Request
) -> AdminUserOut:
    user = _user_or_404(db, user_id)
    if suspend_user(db, request, admin, user, body.reason):
        db.commit()
    return _user_out(user, _bet_count(db, user.id))


@router.post(
    "/users/{user_id}/unsuspend",
    response_model=AdminUserOut,
    operation_id="admin_unsuspend_user",
    summary="Lift a suspension",
    description="The user can log in again and tokens that have not expired work again.",
    responses={**_ADMIN_RESPONSES, **NOT_FOUND_RESPONSE},
)
def admin_unsuspend_user(
    user_id: str, admin: AdminDep, db: DbDep, request: Request
) -> AdminUserOut:
    user = _user_or_404(db, user_id)
    if user.status != "active":
        before = user.status
        user.status = "active"
        write_audit(
            db,
            request,
            "admin.user_unsuspended",
            user_id=admin.id,
            entity_type="user",
            entity_id=user.id,
            details={"before": {"status": before}, "after": {"status": user.status}},
        )
        db.commit()
    return _user_out(user, _bet_count(db, user.id))


@router.put(
    "/users/{user_id}/plan",
    response_model=AdminUserOut,
    operation_id="admin_set_user_plan",
    summary="Set a user's plan",
    description=(
        "The only way a plan changes: there is no purchase route and no billing. While the "
        "`premium_gating` flag is off the plan gates nothing."
    ),
    responses={**_ADMIN_RESPONSES, **NOT_FOUND_RESPONSE},
)
def admin_set_user_plan(
    user_id: str, body: SetUserPlanRequest, admin: AdminDep, db: DbDep, request: Request
) -> AdminUserOut:
    user = _user_or_404(db, user_id)
    if user.plan != body.plan:
        before = user.plan
        user.plan = body.plan
        write_audit(
            db,
            request,
            "admin.user_plan_set",
            user_id=admin.id,
            entity_type="user",
            entity_id=user.id,
            details={"before": {"plan": before}, "after": {"plan": user.plan}},
        )
        db.commit()
    return _user_out(user, _bet_count(db, user.id))


# ------------------------------------------- data rights on behalf of the owner
def _data_rights_target(
    db: Session, admin: User, user_id: str, action: Literal["export", "delete"], reason: str
) -> User:
    """The user an administrator may ``action`` (``export`` or ``delete``) for a data
    request: not themselves (they have the routes under ``/v1/me``) and not another
    administrator, as for a suspension. The reason must not name the account by its
    email address: the audit entry outlives the account."""
    user = _user_or_404(db, user_id)
    if user.id == admin.id:
        raise ApiError(
            409,
            f"cannot_{action}_self",
            f"You cannot {action} your own account here. Use your account settings.",
        )
    if user.role == "admin":
        done = {"export": "exported", "delete": "deleted"}[action]
        raise ApiError(
            409,
            f"cannot_{action}_admin",
            f"An administrator's account cannot be {done} by another administrator",
        )
    if user.email.lower() in reason.lower():
        raise ApiError(
            422,
            "reason_contains_email",
            "The reason must not contain the account's email address: it stays in the "
            "audit log after the account is gone. Use the reference of the request.",
        )
    return user


_DATA_RIGHTS_CONFLICT: dict[int | str, dict[str, Any]] = {
    409: {
        "model": ErrorResponse,
        "description": "The target is an administrator or the caller's own account",
    }
}


@router.post(
    "/users/{user_id}/export",
    response_model=AccountExportOut,
    operation_id="admin_export_user",
    summary="Export a user's data on their behalf",
    description=(
        "For a data request from an owner who cannot sign in: a suspended account, an "
        "account closed because its owner is under 21, a lost password. Returns the same "
        "document as `GET /v1/me/export` for that user, produced by the same code and "
        "streamed the same way: one JSON document without a `Content-Length`, to be read "
        "to the end and parsed once. It is the owner's data: pass it on to the owner "
        "only, and only once you know the request is theirs. Works for an active and "
        "for a suspended account and changes nothing in it.\n\n"
        "`reason` is required and is recorded in the audit log as `admin.user_exported` "
        "with the acting administrator, the user's id and the account's status; the "
        "entry holds none of the exported data. The reason must not contain the "
        "account's email address (`422 reason_contains_email`). An administrator cannot "
        "export another administrator's account or their own (`409`); their own is at "
        "`GET /v1/me/export`. The response counts as one of the streamed responses the "
        "administrator can have in progress at the same moment "
        "(`ODDVEX_RATE_LIMIT_USER_STREAMS_AT_ONCE`): over it this answers "
        "`429 rate_limited`."
    ),
    responses={
        **_ADMIN_RESPONSES,
        **NOT_FOUND_RESPONSE,
        **_DATA_RIGHTS_CONFLICT,
        **RATE_LIMIT_RESPONSE,
    },
)
def admin_export_user(
    user_id: str, body: ExportUserRequest, admin: AdminDep, db: DbDep, request: Request
) -> StreamingResponse:
    user = _data_rights_target(db, admin, user_id, "export", body.reason)
    # The stream is the administrator's: it counts against the streams they have in
    # progress. Taken before the audit entry, so a refused request is not recorded as
    # an export; given back here if no response comes of it.
    release = take_user_stream_slot(request, admin.id)
    try:
        write_audit(
            db,
            request,
            "admin.user_exported",
            user_id=admin.id,
            entity_type="user",
            entity_id=user.id,
            details={"reason": body.reason, "account_status": user.status},
        )
        db.commit()
        return account_export.export_response(request.app, user.id, release)
    except BaseException:
        release()
        raise


@router.post(
    "/users/{user_id}/delete",
    status_code=204,
    operation_id="admin_delete_user",
    summary="Delete a user's account on their behalf",
    description=(
        "For a data request from an owner who cannot sign in, and for closing an account "
        "that must not exist. Permanently deletes the user and everything "
        "`DELETE /v1/me` deletes, through the same code: bets, watchlist, alert rules, "
        "notifications and their preferences, the staking reminder, sync connections, "
        "import runs, email tokens, outbox emails and all community data. It cannot be "
        "undone. Works for an active and for a suspended account.\n\n"
        "`confirm_email` must be the account's email address (compared as login compares "
        "addresses), otherwise `422 confirm_email_mismatch` and nothing is deleted. "
        "`reason` is required and must not contain that address "
        "(`422 reason_contains_email`). The audit log keeps the entry the owner's own "
        "deletion leaves (`account.deleted`, the opaque user id only) and an "
        "`admin.user_deleted` entry with the acting administrator, the user's id, the "
        "account's status and the reason; neither holds the email address. An "
        "administrator cannot delete another administrator's account or their own "
        "(`409`). Answers `204` with no body."
    ),
    responses={**_ADMIN_RESPONSES, **NOT_FOUND_RESPONSE, **_DATA_RIGHTS_CONFLICT},
)
def admin_delete_user(
    user_id: str, body: DeleteUserRequest, admin: AdminDep, db: DbDep, request: Request
) -> Response:
    user = _data_rights_target(db, admin, user_id, "delete", body.reason)
    if body.confirm_email != user.email:
        raise ApiError(
            422,
            "confirm_email_mismatch",
            "confirm_email is not this account's email address. Nothing was deleted.",
        )
    # The owner's own deletion, the same function; then who did it and why.
    status = account_service.delete_account(db, request, user)
    write_audit(
        db,
        request,
        "admin.user_deleted",
        user_id=admin.id,
        entity_type="user",
        entity_id=user_id,
        details={"reason": body.reason, "account_status": status},
    )
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------- flags
class AdminFlagOut(BaseModel):
    key: str
    description: str
    enabled: bool
    default: bool = Field(
        description=(
            "The in-code default for this environment, used while there is no override. "
            "`email_flows` defaults to off in production and on elsewhere."
        )
    )
    overridden: bool = Field(description="True when a stored value replaces the default.")
    updated_at: datetime | None = Field(
        default=None, description="When the stored value last changed. Null without one."
    )


class AdminFlagListOut(BaseModel):
    items: list[AdminFlagOut]


class SetFlagRequest(BaseModel):
    enabled: bool


def _flag_out(key: str, row: FeatureFlag | None, settings: Settings) -> AdminFlagOut:
    spec = KNOWN_FLAGS[key]
    default = flags.default_of(key, settings)
    return AdminFlagOut(
        key=key,
        description=spec.description,
        enabled=default if row is None else row.enabled,
        default=default,
        overridden=row is not None,
        updated_at=row.updated_at if row is not None else None,
    )


@router.get(
    "/flags",
    response_model=AdminFlagListOut,
    operation_id="admin_list_flags",
    summary="Feature flags with their descriptions and defaults",
    responses=_ADMIN_RESPONSES,
)
def admin_list_flags(admin: AdminDep, db: DbDep, settings: SettingsDep) -> AdminFlagListOut:
    stored = {row.key: row for row in db.scalars(select(FeatureFlag))}
    return AdminFlagListOut(
        items=[_flag_out(key, stored.get(key), settings) for key in KNOWN_FLAGS]
    )


@router.put(
    "/flags/{key}",
    response_model=AdminFlagOut,
    operation_id="admin_set_flag",
    summary="Turn a feature flag on or off",
    description=(
        "Stores an override of the in-code default; it applies to everyone at once. Only "
        "known keys exist (`404` otherwise). Turning `premium_gating` on is a pricing "
        "decision and needs Founder approval first. `community` and "
        "`community_leaderboard` are off by default: turning them on needs the content "
        "and responsible-gambling reviews described in the README."
    ),
    responses={**_ADMIN_RESPONSES, **NOT_FOUND_RESPONSE},
)
def admin_set_flag(
    key: str,
    body: SetFlagRequest,
    admin: AdminDep,
    db: DbDep,
    request: Request,
    settings: SettingsDep,
) -> AdminFlagOut:
    if key not in KNOWN_FLAGS:
        raise not_found("Feature flag", key)
    before, row = flags.set_flag(db, key, body.enabled, settings)
    write_audit(
        db,
        request,
        "admin.flag_set",
        user_id=admin.id,
        entity_type="feature_flag",
        entity_id=key,
        details={"before": {"enabled": before}, "after": {"enabled": body.enabled}},
    )
    db.commit()
    return _flag_out(key, row, settings)


# ---------------------------------------------------------------------- audit
class AdminAuditPageOut(BaseModel):
    items: list[AuditEntryOut]
    next_before: str | None = Field(
        default=None, description="Pass as `before` to get the next (older) page."
    )


def _encode_cursor(row: AuditLog) -> str:
    micros = int(row.created_at.timestamp()) * 1_000_000 + row.created_at.microsecond
    return f"{micros}-{row.id}"


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    error = ApiError(422, "invalid_cursor", "The 'before' value is not a cursor from this API")
    micros, _, row_id = cursor.partition("-")
    if not micros.isdigit() or not row_id or len(micros) > 18:
        raise error
    seconds, remainder = divmod(int(micros), 1_000_000)
    try:
        return datetime.fromtimestamp(seconds, UTC).replace(microsecond=remainder), row_id
    except (OverflowError, OSError, ValueError) as exc:
        raise error from exc


@router.get(
    "/audit",
    response_model=AdminAuditPageOut,
    operation_id="admin_list_audit",
    summary="Audit log, newest first",
    description=(
        "`action` is an exact action name such as `admin.user_suspended`. `user_id` "
        "matches entries the user caused and entries about that user. Page with `limit` "
        "and the `next_before` cursor."
    ),
    responses=_ADMIN_RESPONSES,
)
def admin_list_audit(
    admin: AdminDep,
    db: DbDep,
    action: Annotated[str | None, Query(max_length=64)] = None,
    user_id: Annotated[str | None, Query(max_length=64)] = None,
    before: Annotated[
        str | None, Query(max_length=80, description="`next_before` from the previous page.")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AdminAuditPageOut:
    query = select(AuditLog)
    if action:
        query = query.where(AuditLog.action == action)
    if user_id:
        query = query.where(
            or_(
                AuditLog.user_id == user_id,
                (AuditLog.entity_type == "user") & (AuditLog.entity_id == user_id),
            )
        )
    if before is not None:
        moment, row_id = _decode_cursor(before)
        query = query.where(
            (AuditLog.created_at < moment)
            | ((AuditLog.created_at == moment) & (AuditLog.id < row_id))
        )
    rows = list(
        db.scalars(query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit + 1))
    )
    page = rows[:limit]
    return AdminAuditPageOut(
        items=[_audit_entry(row) for row in page],
        next_before=_encode_cursor(page[-1]) if len(rows) > limit and page else None,
    )


# --------------------------------------------------------------- email outbox
class AdminOutboxEmailOut(BaseModel):
    id: str
    user_id: str
    to: str
    template: str
    subject: str
    created_at: datetime


class AdminOutboxListOut(BaseModel):
    items: list[AdminOutboxEmailOut]
    delivery: str = Field(description="How email leaves the system. `outbox`: it does not.")


@router.get(
    "/email-outbox",
    response_model=AdminOutboxListOut,
    operation_id="admin_list_email_outbox",
    summary="Emails written to the outbox, newest first",
    description=(
        "What would have been sent: recipient, template and subject. Bodies, links and "
        "tokens are never returned here. No email is delivered in this build."
    ),
    responses=_ADMIN_RESPONSES,
)
def admin_list_email_outbox(
    admin: AdminDep,
    db: DbDep,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AdminOutboxListOut:
    rows = list(
        db.scalars(
            select(EmailOutbox).order_by(EmailOutbox.created_at.desc(), EmailOutbox.id).limit(limit)
        )
    )
    audit_admin_read(db, request, admin.id, "admin_email_outbox")
    return AdminOutboxListOut(
        items=[
            AdminOutboxEmailOut(
                id=row.id,
                user_id=row.user_id,
                to=row.to_email,
                template=row.template,
                subject=row.subject,
                created_at=row.created_at,
            )
            for row in rows
        ],
        delivery=request.app.state.email_sender.name,
    )
