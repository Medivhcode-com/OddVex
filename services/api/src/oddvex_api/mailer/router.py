"""Development-only window onto the email outbox.

So a developer or an end-to-end test can read the link from an email that was never
sent. The route answers 404 in production, where the outbox holds no links anyway.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from urllib.parse import parse_qs, urlsplit

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..db import EmailOutbox
from ..deps import DbDep, SettingsDep
from ..errors import ERROR_RESPONSES, NOT_FOUND_RESPONSE, ApiError

router = APIRouter(prefix="/dev", tags=["dev"])


class DevEmailOut(BaseModel):
    id: str
    to: str
    template: str
    subject: str
    body_text: str
    dev_link: str | None = Field(default=None, description="The link in the email.")
    token: str | None = Field(default=None, description="The `token` parameter of that link.")
    created_at: datetime


@router.get(
    "/email-outbox/latest",
    response_model=DevEmailOut,
    operation_id="dev_latest_email",
    summary="Development only: the latest outbox email for an address, with its link",
    description=(
        "Only when `ODDVEX_ENV` is not `production`; in production this is `404`. It needs "
        "no sign-in, so never expose a non-production API to the internet with real "
        "accounts in it. `template` narrows the search to `verify_email` or "
        "`password_reset`."
    ),
    responses={**NOT_FOUND_RESPONSE, **ERROR_RESPONSES},
)
def dev_latest_email(
    db: DbDep,
    settings: SettingsDep,
    to: Annotated[str, Query(min_length=3, max_length=320)],
    template: Annotated[str | None, Query(max_length=40)] = None,
) -> DevEmailOut:
    if settings.is_production:
        raise ApiError(404, "not_found", "Not Found")
    query = select(EmailOutbox).where(EmailOutbox.to_email == to.strip().lower())
    if template:
        query = query.where(EmailOutbox.template == template)
    row = db.scalar(query.order_by(EmailOutbox.created_at.desc(), EmailOutbox.id.desc()).limit(1))
    if row is None:
        raise ApiError(404, "not_found", "No email in the outbox for that address")
    token: str | None = None
    if row.dev_link:
        token = next(iter(parse_qs(urlsplit(row.dev_link).query).get("token", [])), None)
    return DevEmailOut(
        id=row.id,
        to=row.to_email,
        template=row.template,
        subject=row.subject,
        body_text=row.body_text,
        dev_link=row.dev_link,
        token=token,
        created_at=row.created_at,
    )
