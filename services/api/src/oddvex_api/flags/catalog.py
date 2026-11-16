"""The known feature flags and their safe defaults.

A flag is a global on/off switch. The default lives here, in code; an administrator can
override it with a row in ``feature_flags`` (``PUT /v1/admin/flags/{key}``). A key that
is not listed here does not exist, whatever the table holds.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FlagSpec:
    key: str
    default: bool
    description: str


_SPECS = (
    FlagSpec(
        "community",
        False,
        "Community features. Not built yet; off until they are reviewed and approved.",
    ),
    FlagSpec(
        "value_screen",
        True,
        "Market discrepancies screen: best price against the no-vig consensus of other books.",
    ),
    FlagSpec(
        "tracker_analytics",
        True,
        "Tracker analytics: odds bands, weekdays, months, streaks, CLV and stake sizes.",
    ),
    FlagSpec(
        "email_flows",
        True,
        "Email verification and password reset. Emails go to the outbox table; none is sent.",
    ),
    FlagSpec(
        "premium_gating",
        False,
        "Enforce plan entitlements. While off, every feature is available to every plan. "
        "Turning it on is a pricing decision and needs Founder approval.",
    ),
)

KNOWN_FLAGS: dict[str, FlagSpec] = {spec.key: spec for spec in _SPECS}
