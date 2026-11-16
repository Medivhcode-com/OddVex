"""Plan entitlements, computed from :mod:`.catalog` and the ``premium_gating`` flag."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from ..db import User
from ..deps import CurrentUserDep, DbDep
from ..errors import ApiError
from ..flags import service as flags
from . import catalog
from .catalog import Entitlement


def entitlement(plan: str, feature: str, gating: bool) -> Entitlement:
    """What ``plan`` gets for ``feature``. While gating is off, the most generous plan's
    entitlement applies to everyone."""
    plans = catalog.CATALOG[feature]
    if not gating:
        return plans["premium"]
    return plans.get(plan, plans["free"])


def entitlements_for(db: Session, user: User) -> tuple[bool, dict[str, Entitlement]]:
    """``(gating enforced, feature -> entitlement)`` for one user."""
    gating = flags.is_enabled(db, "premium_gating")
    return gating, {feature: entitlement(user.plan, feature, gating) for feature in catalog.CATALOG}


def required_plan(feature: str) -> str | None:
    """The first plan that includes ``feature``."""
    return next((p for p in catalog.PLANS if catalog.CATALOG[feature][p].enabled), None)


def check_entitlement(db: Session, user: User, feature: str) -> Entitlement:
    """Return the user's entitlement or raise ``403 plan_required``."""
    if feature not in catalog.CATALOG:
        raise KeyError(f"unknown entitlement feature {feature!r}")
    granted = entitlement(user.plan, feature, flags.is_enabled(db, "premium_gating"))
    if not granted.enabled:
        raise ApiError(
            403,
            "plan_required",
            "Your plan does not include this feature",
            details={
                "feature": feature,
                "plan": user.plan,
                "required_plan": required_plan(feature),
            },
        )
    return granted


def require_entitlement(feature: str) -> Callable[[User, Session], Entitlement]:
    """FastAPI dependency: ``403 plan_required`` when the caller's plan lacks ``feature``
    and the ``premium_gating`` flag is on. Nothing uses it on a route yet."""

    def dependency(user: CurrentUserDep, db: DbDep) -> Entitlement:
        return check_entitlement(db, user, feature)

    return dependency
