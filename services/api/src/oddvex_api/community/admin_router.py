"""Community moderation (role ``admin`` only), behind the ``community`` flag.

Every action is written to the audit log with the acting administrator, the report, the
target, the author of the reported content and the moderator's note. Reading the report
queue is audited as ``admin.read``.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select

from ..api.admin import audit_admin_read, suspend_user
from ..db import CommunityReport, User
from ..deps import AdminDep, DbDep, NowDep, write_audit
from ..errors import AUTH_ERROR_RESPONSES, ApiError, ErrorResponse, not_found
from ..flags.service import require_flag
from . import service
from .schemas import (
    AdminCommunityOverviewOut,
    AdminReportListOut,
    AdminReportOut,
    ReportStatus,
    ResolveReportRequest,
)

_RESPONSES: dict[int | str, dict[str, Any]] = {
    **AUTH_ERROR_RESPONSES,
    403: {"model": ErrorResponse, "description": "Administrator role required"},
    404: {"model": ErrorResponse, "description": "Not found, or the `community` flag is off"},
}

router = APIRouter(
    prefix="/admin/community",
    tags=["admin"],
    dependencies=[Depends(require_flag("community"))],
    responses=_RESPONSES,
)


@router.get(
    "/overview",
    response_model=AdminCommunityOverviewOut,
    operation_id="admin_community_overview",
    summary="Counts of profiles, picks, comments and open reports",
)
def admin_community_overview(admin: AdminDep, db: DbDep) -> AdminCommunityOverviewOut:
    return service.admin_overview(db)


@router.get(
    "/reports",
    response_model=AdminReportListOut,
    operation_id="admin_list_reports",
    summary="The report queue, oldest open report first",
    description=(
        "`status=open` (the default) lists what is waiting, oldest first; "
        "`status=resolved` lists what was decided, most recent first. Each row carries "
        "the reported text as stored, its author and the reporter, by user id and "
        "handle. Each call is recorded in the audit log as `admin.read`."
    ),
)
def admin_list_reports(
    admin: AdminDep,
    db: DbDep,
    request: Request,
    status: Annotated[ReportStatus, Query()] = "open",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminReportListOut:
    total = int(
        db.scalar(
            select(func.count())
            .select_from(CommunityReport)
            .where(CommunityReport.status == status)
        )
        or 0
    )
    order = (
        (CommunityReport.created_at, CommunityReport.id)
        if status == "open"
        else (CommunityReport.resolved_at.desc(), CommunityReport.id)
    )
    rows = list(
        db.scalars(
            select(CommunityReport)
            .where(CommunityReport.status == status)
            .order_by(*order)
            .limit(limit)
            .offset(offset)
        )
    )
    items = [service.admin_report_out(db, row) for row in rows]
    audit_admin_read(db, request, admin.id, "admin_community_reports")
    return AdminReportListOut(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/reports/{report_id}/resolve",
    response_model=AdminReportOut,
    operation_id="admin_resolve_report",
    summary="Decide a report",
    description=(
        "`dismiss`: nothing happens to the content. `hide_content` and `remove_content`: "
        "the pick, comment or profile disappears from every public read (its author "
        "sees a 'removed by moderators' placeholder on their own item); a hidden pick "
        "still counts in its author's record. `suspend_author`: the author's account is "
        "suspended through the same code as `POST /v1/admin/users/{id}/suspend`, so an "
        "administrator cannot be suspended (`409`). Every other open report on the same "
        "content is resolved with the same decision, except after `dismiss`. A report "
        "that was already resolved is `409 report_already_resolved`. `note` is required "
        "and is stored on the report and in the audit log."
    ),
    responses={409: {"model": ErrorResponse, "description": "Already resolved, or an admin"}},
)
def admin_resolve_report(
    report_id: str,
    body: ResolveReportRequest,
    admin: AdminDep,
    db: DbDep,
    request: Request,
    now: NowDep,
) -> AdminReportOut:
    report = db.get(CommunityReport, report_id)
    if report is None:
        raise not_found("Report", report_id[:32])
    if report.status != "open":
        raise ApiError(409, "report_already_resolved", "This report was already resolved")
    note = body.note.strip()
    if len(note) < 3:
        raise ApiError(422, "validation_error", "A note of at least 3 characters is required")
    details: dict[str, Any] = {
        "action": body.action,
        "reason": note,
        "report_reason": report.reason,
        "target_type": report.target_type,
        "target_id": report.target_id,
        "target_user_id": report.target_user_id,
    }
    if body.action in ("hide_content", "remove_content"):
        before, after = service.apply_moderation(db, report, body.action)
        details["before"] = {"moderation_status": before}
        details["after"] = {"moderation_status": after}
    elif body.action == "suspend_author":
        author = db.get(User, report.target_user_id)
        if author is None:
            raise not_found("User", report.target_user_id)
        details["suspended"] = suspend_user(
            db, request, admin, author, note, {"report_id": report.id}
        )
    if body.action == "dismiss":
        report.status = "resolved"
        report.resolved_at = now
        report.resolved_by = admin.id
        report.resolution_action = body.action
        report.resolution_note = note
        details["reports_closed"] = 1
    else:
        details["reports_closed"] = service.close_reports_on_target(
            db, report, admin.id, body.action, note, now
        )
    write_audit(
        db,
        request,
        "community.report_resolved",
        user_id=admin.id,
        entity_type="community_report",
        entity_id=report.id,
        details=details,
    )
    db.commit()
    return service.admin_report_out(db, report)
