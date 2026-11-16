"""The one place that says what each plan includes.

**No pricing or packaging decision has been made.** Every feature below is included in
both plans with the same limits, so turning the ``premium_gating`` flag on changes
nothing until this catalog is edited. Deciding that a feature is premium-only, setting a
price or activating billing are Founder approval gates (PROJECT_CONSTITUTION.md,
section 3). There is no purchase route: a plan can only be set by an administrator
(``PUT /v1/admin/users/{id}/plan``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..alerts.schemas import MAX_ACTIVE_ALERTS

Plan = Literal["free", "premium"]
PLANS: tuple[Plan, ...] = ("free", "premium")


@dataclass(frozen=True, slots=True)
class Entitlement:
    enabled: bool
    #: A numeric allowance where the feature has one (alerts, hours of history).
    limit: int | None = None


#: feature key -> plan -> entitlement.
CATALOG: dict[str, dict[str, Entitlement]] = {
    "alerts.max_active": {
        "free": Entitlement(True, MAX_ACTIVE_ALERTS),
        "premium": Entitlement(True, MAX_ACTIVE_ALERTS),
    },
    "value_screen": {"free": Entitlement(True), "premium": Entitlement(True)},
    "tracker_analytics": {"free": Entitlement(True), "premium": Entitlement(True)},
    "odds_history_hours": {"free": Entitlement(True, 48), "premium": Entitlement(True, 48)},
}
