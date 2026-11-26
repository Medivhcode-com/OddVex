"""The known feature flags and their safe defaults.

A flag is a global on/off switch. The default lives here, in code (one flag,
``email_flows``, has a different default in production); an administrator can
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
    #: The default when ``ODDVEX_ENV=production``, where it differs from ``default``.
    default_in_production: bool | None = None

    def default_for(self, production: bool) -> bool:
        if production and self.default_in_production is not None:
            return self.default_in_production
        return self.default


_SPECS = (
    FlagSpec(
        "community",
        False,
        "Community: profiles, structured picks, comments, follows, likes, reports and "
        "moderation. Off until user content and moderation are reviewed and approved.",
    ),
    FlagSpec(
        "community_leaderboard",
        False,
        "Community leaderboard (needs `community` too). Off until a responsible-gambling "
        "review approves leaderboards.",
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
        "Email verification and password reset. Emails go to the outbox table; none is "
        "sent. On by default outside production and off in production, where no email "
        "provider is connected and a reset request would go nowhere.",
        default_in_production=False,
    ),
    FlagSpec(
        "premium_gating",
        False,
        "Enforce plan entitlements. While off, every feature is available to every plan. "
        "Turning it on is a pricing decision and needs Founder approval.",
    ),
    FlagSpec(
        "snapshot_archive",
        False,
        "Snapshot archive: capture book prices, event state and status records every few "
        "minutes and serve them as of a past time. Off by default; it uses disk on the "
        "shared server.",
    ),
)

KNOWN_FLAGS: dict[str, FlagSpec] = {spec.key: spec for spec in _SPECS}
