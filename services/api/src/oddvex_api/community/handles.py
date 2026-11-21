"""Reserved community handles: the handle of an account deleted while it was suspended.

A suspended member who deletes the account, or whose account an administrator deletes,
cannot come back under the same handle. Only the handle is kept, lower-case like
``community_profiles.handle``; nothing about the account, its email address or the
suspension. This does not stop the person from registering again with another email
address and choosing another handle.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..db.models import CommunityProfile, CommunityReservedHandle


def reserve_handle_of(db: Session, user_id: str) -> str | None:
    """Reserve the handle of ``user_id``'s profile, if it has one. Returns the handle.
    Call it before the account is deleted. Not committed."""
    profile = db.get(CommunityProfile, user_id)
    if profile is None:
        return None
    handle = profile.handle.lower()
    if db.get(CommunityReservedHandle, handle) is None:
        db.add(CommunityReservedHandle(handle=handle))
    return handle


def is_reserved(db: Session, handle: str) -> bool:
    """Whether ``handle`` (already lowered by ``validate_handle``) is reserved."""
    return db.get(CommunityReservedHandle, handle.lower()) is not None
