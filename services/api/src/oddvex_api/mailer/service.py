"""Email verification and password reset: tokens and the messages that carry them."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from urllib.parse import quote

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..db import EmailToken, User, utcnow
from ..errors import ApiError
from . import templates
from .sender import EmailSender, OutgoingEmail

VERIFY_EMAIL = "verify_email"
PASSWORD_RESET = "password_reset"
#: Bytes of randomness in a token (the URL-safe text is longer).
TOKEN_BYTES = 32


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def invalid_token() -> ApiError:
    return ApiError(
        400, "invalid_or_expired_token", "This link is not valid or has expired. Request a new one."
    )


def issue_token(db: Session, user: User, purpose: str, ttl: timedelta, now: datetime) -> str:
    """Store the hash of a fresh token and return the token itself.

    Earlier unused tokens of the same purpose stop working: only the newest link is live.
    """
    db.execute(
        delete(EmailToken).where(
            EmailToken.user_id == user.id,
            EmailToken.purpose == purpose,
            EmailToken.used_at.is_(None),
        )
    )
    token = new_token()
    db.add(
        EmailToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=hash_token(token),
            created_at=now,
            expires_at=now + ttl,
        )
    )
    return token


def consume_token(db: Session, token: str, purpose: str, now: datetime | None = None) -> User:
    """Mark a token used and return its user, or raise ``400 invalid_or_expired_token``.

    Unknown, used, expired and wrong-purpose tokens are indistinguishable to the caller.
    """
    moment = now or utcnow()
    row = db.scalar(
        select(EmailToken)
        .where(EmailToken.token_hash == hash_token(token), EmailToken.purpose == purpose)
        .with_for_update()
    )
    if row is None or row.used_at is not None or row.expires_at <= moment:
        raise invalid_token()
    user = db.get(User, row.user_id)
    if user is None:
        raise invalid_token()
    row.used_at = moment
    return user


def _link(settings: Settings, path: str, token: str) -> str:
    return f"{settings.web_base_url.rstrip('/')}{path}?token={quote(token, safe='')}"


def queue_verification_email(
    db: Session, sender: EmailSender, settings: Settings, user: User, now: datetime | None = None
) -> None:
    minutes = settings.email_verification_ttl_hours * 60
    token = issue_token(db, user, VERIFY_EMAIL, timedelta(minutes=minutes), now or utcnow())
    link = _link(settings, "/verify-email", token)
    rendered = templates.verify_email(link, minutes)
    sender.send(
        db,
        OutgoingEmail(
            user_id=user.id,
            to=user.email,
            template=rendered.template,
            subject=rendered.subject,
            body_text=rendered.body_text,
            link=link,
        ),
    )


def queue_password_reset_email(
    db: Session, sender: EmailSender, settings: Settings, user: User, now: datetime | None = None
) -> None:
    minutes = settings.password_reset_ttl_minutes
    token = issue_token(db, user, PASSWORD_RESET, timedelta(minutes=minutes), now or utcnow())
    link = _link(settings, "/reset-password", token)
    rendered = templates.password_reset(link, minutes)
    sender.send(
        db,
        OutgoingEmail(
            user_id=user.id,
            to=user.email,
            template=rendered.template,
            subject=rendered.subject,
            body_text=rendered.body_text,
            link=link,
        ),
    )
