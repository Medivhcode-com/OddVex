"""Account deletion: the one place an account is deleted.

``DELETE /v1/me`` (the owner) and ``POST /v1/admin/users/{user_id}/delete`` (an
administrator acting on a data request) both call :func:`delete_account`, so what is
removed and what is kept cannot differ between the two.
"""

from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from ..community.handles import reserve_handle_of
from ..db import User
from ..deps import write_audit


def delete_account(db: Session, request: Request | None, user: User) -> str:
    """Delete ``user`` and everything that belongs to the account; returns the status
    the account had (``active`` or ``suspended``). Not committed: the caller commits.

    Removed with the user row, through the model's cascades and the foreign keys: bets
    and their legs, watchlist items, alert rules, notifications and their preferences,
    the staking reminder, sync connections and import runs, email tokens, outbox emails
    and all community data (profile, picks, comments, follows in both directions, likes,
    blocks, reports made).

    Kept: the audit log. Its rows are not tied to the user row, name the account by its
    opaque id only and carry no personal data. One ``account.deleted`` entry is added
    under the deleted account's id, with ``details.account_status`` when the account was
    suspended. Who asked for the deletion is the caller's to record. When the account is
    suspended at that moment, its community handle is also kept, alone, in
    ``community_reserved_handles``, so nobody can take it again (``community/handles.py``).
    """
    user_id = user.id
    status = user.status
    if status == "suspended":
        reserve_handle_of(db, user_id)
    db.delete(user)
    write_audit(
        db,
        request,
        "account.deleted",
        user_id=user_id,
        entity_type="user",
        entity_id=user_id,
        details={"account_status": "suspended"} if status == "suspended" else None,
    )
    return status
