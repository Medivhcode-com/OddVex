"""Feature flag state: in-code defaults overridden by rows in ``feature_flags``."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import FeatureFlag, utcnow
from ..deps import DbDep
from ..errors import ApiError
from .catalog import KNOWN_FLAGS


def flag_states(db: Session) -> dict[str, bool]:
    """Every known flag and whether it is on, in catalog order."""
    stored = {
        row.key: row.enabled
        for row in db.scalars(select(FeatureFlag).where(FeatureFlag.key.in_(KNOWN_FLAGS)))
    }
    return {key: stored.get(key, spec.default) for key, spec in KNOWN_FLAGS.items()}


def is_enabled(db: Session, key: str) -> bool:
    spec = KNOWN_FLAGS[key]
    stored = db.scalar(select(FeatureFlag.enabled).where(FeatureFlag.key == key))
    return spec.default if stored is None else bool(stored)


def set_flag(db: Session, key: str, enabled: bool) -> tuple[bool, FeatureFlag]:
    """Store an override. Returns ``(previous effective state, row)``. Not committed."""
    spec = KNOWN_FLAGS[key]
    row = db.get(FeatureFlag, key)
    previous = spec.default if row is None else row.enabled
    if row is None:
        row = FeatureFlag(key=key, description=spec.description, enabled=enabled)
        db.add(row)
    else:
        row.enabled = enabled
        row.description = spec.description
        row.updated_at = utcnow()
    return previous, row


def feature_disabled(key: str) -> ApiError:
    return ApiError(
        404, "feature_disabled", "This feature is not available", details={"flag": key}
    )


def require_flag(key: str) -> Callable[[Session], None]:
    """FastAPI dependency: 404 ``feature_disabled`` while the flag is off."""
    if key not in KNOWN_FLAGS:
        raise KeyError(f"unknown feature flag {key!r}")

    def dependency(db: DbDep) -> None:
        if not is_enabled(db, key):
            raise feature_disabled(key)

    return dependency
