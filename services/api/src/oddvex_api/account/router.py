"""Account data export. Scoped to the authenticated user."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ..deps import DataRightsUserDep, DbDep, write_audit
from ..errors import AUTH_ERROR_RESPONSES, RATE_LIMIT_RESPONSE
from ..ratelimit import enforce_user_limit, take_user_stream_slot
from . import export
from .schemas import AccountExportOut

router = APIRouter(tags=["auth"])


@router.get(
    "/me/export",
    response_model=AccountExportOut,
    operation_id="export_my_data",
    summary="Download everything stored about your account",
    description=(
        "One JSON document with your profile, bets, watchlist, alert rules, notifications, "
        "notification preferences, staking reminder, sync connections, import runs and "
        "your own audit entries, plus your community data (profile, picks, comments, who "
        "you follow, likes, blocks and reports you made). It never contains the password "
        "hash. The export itself is recorded in the audit log. A suspended account can "
        "still call this route.\n\n"
        "The document is streamed: bets, import runs, audit entries and your community "
        "picks, comments and reports are read in batches and sent as they are read, so "
        "the response has no `Content-Length`. It is still one JSON "
        "document of this schema; read it to the end and parse it once. Limited per user "
        "(`ODDVEX_RATE_LIMIT_EXPORT_PER_HOUR`, default 10 an hour), and it counts as one "
        "of the streamed responses an account can have in progress at the same moment "
        "(`ODDVEX_RATE_LIMIT_USER_STREAMS_AT_ONCE`, default 8, shared with the bet list): "
        "over either limit this answers 429 `rate_limited` with `Retry-After`."
    ),
    responses={**AUTH_ERROR_RESPONSES, **RATE_LIMIT_RESPONSE},
)
def export_my_data(user: DataRightsUserDep, db: DbDep, request: Request) -> StreamingResponse:
    user_id = user.id
    # Called directly, not as dependencies: this route takes the user that may be
    # suspended, and a refused export must not be audited as an export. The slot is
    # taken first, so a request refused for want of one does not count as an export.
    release = take_user_stream_slot(request, user_id)
    try:
        enforce_user_limit(request, "export", user_id)
        write_audit(
            db,
            request,
            "account.export",
            user_id=user_id,
            entity_type="user",
            entity_id=user_id,
            details={"account_status": "suspended"} if user.status == "suspended" else None,
        )
        db.commit()
        return export.export_response(request.app, user_id, release)
    except BaseException:
        release()
        raise
