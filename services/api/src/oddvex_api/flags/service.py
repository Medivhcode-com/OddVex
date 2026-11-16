"""Feature flag state: in-code defaults overridden by rows in ``feature_flags``."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import FeatureFlag, utcnow
from ..deps import DbDep, SettingsDep
from ..errors import ApiError
from .catalog import KNOWN_FLAGS


def default_of(key: str, settings: Settings | None = None) -> bool:
    """The in-code default of a flag for the running environment.

    ``settings`` is the app's settings; without it the process environment is read, and
    only for the flags whose default depends on ``ODDVEX_ENV``.
    """
    spec = KNOWN_FLAGS[key]
    if spec.default_in_production is None:
        return spec.default
    return spec.default_for((settings or get_settings()).is_production)


def flag_states(db: Session, settings: Settings | None = None) -> dict[str, bool]:
    """Every known flag and whether it is on, in catalog order."""
    stored = {
        row.key: row.enabled
        for row in db.scalars(select(FeatureFlag).where(FeatureFlag.key.in_(KNOWN_FLAGS)))
    }
    return {key: stored.get(key, default_of(key, settings)) for key in KNOWN_FLAGS}


def is_enabled(db: Session, key: str, settings: Settings | None = None) -> bool:
    """Whether a flag is on: the stored override if there is one, else the default."""
    stored = db.scalar(select(FeatureFlag.enabled).where(FeatureFlag.key == key))
    return default_of(key, settings) if stored is None else bool(stored)


def set_flag(
    db: Session, key: str, enabled: bool, settings: Settings | None = None
) -> tuple[bool, FeatureFlag]:
    """Store an override. Returns ``(previous effective state, row)``. Not committed."""
    spec = KNOWN_FLAGS[key]
    row = db.get(FeatureFlag, key)
    previous = default_of(key, settings) if row is None else row.enabled
    if row is None:
        row = FeatureFlag(key=key, description=spec.description, enabled=enabled)
        db.add(row)
    else:
        row.enabled = enabled
        row.description = spec.description
        row.updated_at = utcnow()
    return previous, row


def feature_disabled(key: str) -> ApiError:
    return ApiError(404, "feature_disabled", "This feature is not available", details={"flag": key})


def require_flag(key: str) -> Callable[[Session, Settings], None]:
    """FastAPI dependency: 404 ``feature_disabled`` while the flag is off."""
    if key not in KNOWN_FLAGS:
        raise KeyError(f"unknown feature flag {key!r}")

    def dependency(db: DbDep, settings: SettingsDep) -> None:
        if not is_enabled(db, key, settings):
            raise feature_disabled(key)

    return dependency
