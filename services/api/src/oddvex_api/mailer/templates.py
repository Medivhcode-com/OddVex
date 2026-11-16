"""Every word of every email. Plain text, sentence case, no urgency.

Each email says what it is for, gives the link and when it expires, tells the reader
they can ignore it and ends with the 21+ / information-only footer.
``tests/test_email_flows.py`` scans every template for banned phrases.
"""

from __future__ import annotations

from dataclasses import dataclass

IGNORE_LINE = "If you didn't ask for this, you can ignore this email."
FOOTER = (
    "OddVex is for information only and does not accept or place wagers. 21+. "
    "Gambling problem? Call 1-800-GAMBLER."
)


@dataclass(frozen=True, slots=True)
class RenderedEmail:
    template: str
    subject: str
    body_text: str


def _duration(minutes: int) -> str:
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} hour" if hours == 1 else f"{hours} hours"
    return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"


def _body(purpose: str, action: str, link: str, expires_minutes: int, after: str) -> str:
    return "\n\n".join(
        (
            purpose,
            f"{action}\n{link}",
            f"This link expires in {_duration(expires_minutes)} and works once.",
            f"{IGNORE_LINE} {after}",
            FOOTER,
        )
    )


def verify_email(link: str, expires_minutes: int) -> RenderedEmail:
    return RenderedEmail(
        template="verify_email",
        subject="Confirm your email address for OddVex",
        body_text=_body(
            "This email is to confirm the address on your OddVex account.",
            "Open this link to confirm it:",
            link,
            expires_minutes,
            "Your account works the same either way.",
        ),
    )


def password_reset(link: str, expires_minutes: int) -> RenderedEmail:
    return RenderedEmail(
        template="password_reset",
        subject="Reset your OddVex password",
        body_text=_body(
            "This email is to reset the password on your OddVex account.",
            "Open this link to choose a new password:",
            link,
            expires_minutes,
            "Your password stays as it is.",
        ),
    )
