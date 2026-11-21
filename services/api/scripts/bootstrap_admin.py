#!/usr/bin/env python
"""Make the account of a listed address an administrator, with a new random password.

    python scripts/bootstrap_admin.py --email owner@example.com

This is how the first administrator of a deployment comes to exist. The API gives the
admin role only to an account whose address is in ODDVEX_ADMIN_EMAILS and verified, and
in production nothing can be verified through the API: no email is sent there. Whoever
can run this command on the server is taken to be the operator.

The address must be in ODDVEX_ADMIN_EMAILS (the same setting the API reads); any other
address is refused and nothing is changed. Then:

- if no account has the address, one is created;
- if an account has it, that account is taken over, whoever registered it. It keeps its
  id and its data.

In both cases the account gets a new random password, its address is marked verified,
every access token issued before this moment stops working, every outstanding
verification or password-reset link of the account is deleted, a suspension is lifted
and the admin role is given. Whoever held the address before can no longer sign in. The
audit log gets an `admin.bootstrap` entry (and `role.granted` when the role is new),
with the account's opaque id and neither the address nor the password.

The password is printed once, to standard output, and is stored nowhere else. Sign in
with it and change it at once. Running the command again sets another password and ends
the first.

Exit status: 0 when the account is ready, 1 when it was refused or failed (the reason is
on standard error), 2 for a wrong command line. Safe to run while the API is serving
requests; the API needs no restart.
"""

from __future__ import annotations

import argparse
import secrets
import sys

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError

from oddvex_api.auth.schemas import normalize_email
from oddvex_api.auth.security import hash_password
from oddvex_api.config import Settings, get_settings
from oddvex_api.db import EmailToken, User, make_engine, make_session_factory, utcnow
from oddvex_api.deps import sync_admin_role, write_audit

#: Bytes of randomness in the password; the URL-safe text is 32 characters long.
PASSWORD_BYTES = 24
DISPLAY_NAME = "Administrator"


class Refused(Exception):
    """The command cannot do what was asked. The message is for the operator."""


def run(settings: Settings, email: str) -> tuple[str, str]:
    """Create or take over the account of ``email``. Returns ``("created" | "taken_over",
    the new password)``. One transaction: on any error nothing is changed.

    Raises :class:`Refused` when the address is not in ``ODDVEX_ADMIN_EMAILS``.
    """
    if email not in settings.admin_email_set:
        raise Refused(
            f"{email} is not in ODDVEX_ADMIN_EMAILS. Only a listed address can be made an "
            "administrator. Nothing was changed."
        )
    password = secrets.token_urlsafe(PASSWORD_BYTES)
    engine = make_engine(settings.database_url)
    try:
        with make_session_factory(engine)() as db:
            now = utcnow()
            user = db.scalar(select(User).where(User.email == email).with_for_update())
            if user is None:
                outcome = "created"
                user = User(
                    email=email,
                    password_hash=hash_password(password),
                    display_name=DISPLAY_NAME,
                    role="user",
                    age_confirmed_at=now,
                )
                db.add(user)
                db.flush()
            else:
                outcome = "taken_over"
                user.password_hash = hash_password(password)
                # Tokens carry the version they were issued under: every earlier one is
                # rejected from now on.
                user.token_version += 1
                user.status = "active"
                user.is_active = True
                db.execute(delete(EmailToken).where(EmailToken.user_id == user.id))
            user.password_changed_at = now
            user.email_verified_at = now
            write_audit(
                db,
                None,
                "admin.bootstrap",
                user_id=user.id,
                entity_type="user",
                entity_id=user.id,
                details={"account": outcome, "source": "scripts/bootstrap_admin.py"},
            )
            # Listed and verified: the rule the API applies on every request now holds.
            sync_admin_role(db, None, user, settings, source="bootstrap_admin")
            if user.role != "admin":  # pragma: no cover - listed and verified just above
                raise Refused("The account did not get the admin role. Nothing was changed.")
            db.commit()
    finally:
        engine.dispose()
    return outcome, password


def main(argv: list[str], settings: Settings | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bootstrap_admin.py",
        description=(
            "Create the account of an address listed in ODDVEX_ADMIN_EMAILS, or take it "
            "over, set a new random password and make it an administrator."
        ),
        allow_abbrev=False,
    )
    parser.add_argument("--email", required=True, help="an address in ODDVEX_ADMIN_EMAILS")
    try:
        arguments = parser.parse_args(argv)
    except SystemExit as stop:  # argparse has printed the help, or the reason on standard error
        return stop.code if isinstance(stop.code, int) else 2
    try:
        email = normalize_email(arguments.email)
    except ValueError:
        print("--email is not a valid email address. Nothing was changed.", file=sys.stderr)
        return 2
    try:
        outcome, password = run(settings or get_settings(), email)
    except Refused as refused:
        print(str(refused), file=sys.stderr)
        return 1
    except SQLAlchemyError as error:
        # The class only: the driver's message can carry values from the database.
        print(
            f"The database could not be read or written ({type(error).__name__}). Check that "
            "it is reachable and that the migrations have been applied. Nothing was changed.",
            file=sys.stderr,
        )
        return 1
    if outcome == "created":
        print(f"Administrator: created the account {email}.")
    else:
        print(
            f"Administrator: took over the existing account {email}. Its earlier password "
            "and every earlier sign-in no longer work."
        )
    print(f"New password: {password}")
    print("Sign in with this password and change it at once. It is not shown again.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
