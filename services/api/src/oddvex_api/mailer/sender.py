"""Email delivery behind a protocol. **Nothing in this build sends an email.**

``OutboxEmailSender`` is the default and the only working implementation: it writes the
message to the ``email_outbox`` table and stops there. ``ResendEmailSender`` is a stub
that refuses to be constructed. Sending real customer email needs a paid provider and
Founder approval (PROJECT_CONSTITUTION.md, section 3); no SDK is installed and no HTTP
call is made.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from ..config import Settings
from ..db import EmailOutbox

LINK_WITHHELD = "[link withheld: email delivery is not connected]"


@dataclass(frozen=True, slots=True)
class OutgoingEmail:
    user_id: str
    to: str
    template: str
    subject: str
    body_text: str
    #: The link inside ``body_text``. It carries a single-use token.
    link: str


class EmailSender(Protocol):
    name: str

    def send(self, db: Session, message: OutgoingEmail) -> None:
        """Hand over one message. Uses the caller's transaction; does not commit."""
        ...


class OutboxEmailSender:
    """Writes messages to ``email_outbox``. Never sends anything.

    Outside production the row keeps the link so a developer or an end-to-end test can
    finish the flow. In production the link is replaced in the body and ``dev_link`` is
    left empty, so the table never holds a usable token there (only the token's hash is
    stored, in ``email_tokens``).
    """

    name = "outbox"

    def __init__(self, keep_links: bool) -> None:
        self.keep_links = keep_links

    def send(self, db: Session, message: OutgoingEmail) -> None:
        body = message.body_text
        if not self.keep_links:
            body = body.replace(message.link, LINK_WITHHELD)
        db.add(
            EmailOutbox(
                user_id=message.user_id,
                to_email=message.to,
                template=message.template,
                subject=message.subject,
                body_text=body,
                dev_link=message.link if self.keep_links else None,
            )
        )


class ResendEmailSender:
    """Placeholder for a real provider. Not implemented on purpose."""

    name = "resend"

    def __init__(self) -> None:
        raise NotImplementedError("Requires Founder approval and a Resend account")

    def send(self, db: Session, message: OutgoingEmail) -> None:  # pragma: no cover
        raise NotImplementedError("Requires Founder approval and a Resend account")


def make_sender(settings: Settings) -> EmailSender:
    """The outbox unless ``ODDVEX_EMAIL_PROVIDER=resend``, which fails at startup."""
    if settings.email_provider == "resend":
        return ResendEmailSender()
    return OutboxEmailSender(keep_links=not settings.is_production)
