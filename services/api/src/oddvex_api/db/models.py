"""ORM models.

Canonical sports entities (leagues, teams, events, odds) are served straight
from the provider and are referenced by string id only (``bet_legs.event_id`` is
deliberately not a foreign key). The snapshot archive (P0.1, at the end of this
module) keeps an append-only record of what the provider said: ``odds_snapshots``
keyed on ``(provider, event_id, market, sportsbook_id, captured_at)``, with the
same provenance columns the provider contract already carries, and its siblings
for events, prop offers and lineup or news status.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..textnorm import fold, user_search_key
from .base import Base, UTCDateTime, new_id, utcnow

MONEY = Numeric(14, 2)
ODDS = Numeric(16, 6)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(80), default="")
    role: Mapped[str] = mapped_column(String(16), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    age_confirmed_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    #: Bumped on every password change. Access tokens carry the value they were issued
    #: under (claim ``ver``); a token with another value is rejected.
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    password_changed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    #: free | premium. Only an administrator can change it; there is no purchase route.
    plan: Mapped[str] = mapped_column(String(16), default="free", server_default="free")
    #: active | suspended. A suspended user cannot log in and their tokens are rejected.
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active")
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    email_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    #: Folded email and display name (``textnorm.user_search_key``), kept in step by a
    #: mapper event below. The admin user search matches against it.
    search_key: Mapped[str | None] = mapped_column(String(1024))

    bets: Mapped[list[Bet]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    sync_connections: Mapped[list[SyncConnection]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    watchlist_items: Mapped[list[WatchlistItem]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    alert_rules: Mapped[list[AlertRule]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    notification_preferences: Mapped[NotificationPreference | None] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True, uselist=False
    )
    stake_reminder: Mapped[StakeReminder | None] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True, uselist=False
    )
    email_tokens: Mapped[list[EmailToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    outbox_emails: Mapped[list[EmailOutbox]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None


class Bet(Base):
    __tablename__ = "bets"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "external_provider", "external_bet_id", name="uq_bets_user_external"
        ),
        Index("ix_bets_user_status", "user_id", "status"),
        Index("ix_bets_user_placed_at", "user_id", "placed_at"),
        # One bet per user and client request id: a repeated ``POST /v1/bets`` finds the
        # first bet instead of storing a second. A unique index, not a table constraint,
        # so the migration can add it to an existing SQLite table without rebuilding it.
        # Rows without an id (NULL) never collide.
        Index("uq_bets_user_client_request", "user_id", "client_request_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    bet_type: Mapped[str] = mapped_column(String(16))
    #: "pending" or "settled".
    status: Mapped[str] = mapped_column(String(16), default="pending")
    #: won | lost | push | void | half_won | half_lost | cashout once settled.
    result: Mapped[str | None] = mapped_column(String(16))
    sport: Mapped[str] = mapped_column(String(32), default="unknown")
    sportsbook: Mapped[str] = mapped_column(String(80))
    #: ``textnorm.fold(sportsbook)``, kept in step by a mapper event below. The
    #: case-insensitive sportsbook filter compares against it.
    sportsbook_key: Mapped[str | None] = mapped_column(String(255))
    stake: Mapped[Decimal] = mapped_column(MONEY)
    odds_decimal: Mapped[Decimal] = mapped_column(ODDS)
    #: "legs" when the price is the product of the legs, "override" when supplied by the user.
    odds_source: Mapped[str] = mapped_column(String(16), default="legs")
    payout: Mapped[Decimal | None] = mapped_column(MONEY)
    profit: Mapped[Decimal | None] = mapped_column(MONEY)
    notes: Mapped[str | None] = mapped_column(Text)
    placed_at: Mapped[datetime] = mapped_column(UTCDateTime)
    settled_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    #: "user" (manual settle) or "auto" (graded from final scores). Null for pending bets
    #: and for bets that arrived already settled from a sync import.
    settled_by: Mapped[str | None] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(16), default="manual")
    sync_connection_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("sync_connections.id", ondelete="SET NULL"), index=True
    )
    external_provider: Mapped[str | None] = mapped_column(String(40))
    external_bet_id: Mapped[str | None] = mapped_column(String(120))
    #: Chosen by the client for one ``POST /v1/bets`` and sent again when it retries.
    #: Null for imported bets and for bets created without one. Not the sync key above.
    client_request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="bets")
    legs: Mapped[list[BetLeg]] = relationship(
        back_populates="bet",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="BetLeg.position",
        lazy="selectin",
    )


class BetLeg(Base):
    __tablename__ = "bet_legs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    bet_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("bets.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    selection: Mapped[str] = mapped_column(String(200))
    market: Mapped[str] = mapped_column(String(40))
    league: Mapped[str | None] = mapped_column(String(32))
    event_id: Mapped[str | None] = mapped_column(String(64), index=True)
    event_label: Mapped[str | None] = mapped_column(String(200))
    line: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    #: Structured selection: home | away | draw | over | under. With ``event_id``, ``market``
    #: and (for spread/total) ``line`` it makes the leg gradeable from a final score.
    outcome_key: Mapped[str | None] = mapped_column(String(16))
    odds_decimal: Mapped[Decimal] = mapped_column(ODDS)
    closing_odds_decimal: Mapped[Decimal | None] = mapped_column(ODDS)
    closing_opposite_odds_decimal: Mapped[Decimal | None] = mapped_column(ODDS)
    #: won | lost | push | void | half_won | half_lost once graded.
    result: Mapped[str | None] = mapped_column(String(16))

    bet: Mapped[Bet] = relationship(back_populates="legs")


class SyncConnection(Base):
    __tablename__ = "sync_connections"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16), default="active")
    label: Mapped[str] = mapped_column(String(120))
    #: Opaque provider state (cursor, mock failure counters). Never credentials.
    provider_state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_synced_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    disconnected_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    user: Mapped[User] = relationship(back_populates="sync_connections")
    runs: Mapped[list[SyncImportRun]] = relationship(
        back_populates="connection", cascade="all, delete-orphan", passive_deletes=True
    )


class SyncImportRun(Base):
    __tablename__ = "sync_import_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    connection_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("sync_connections.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(16), default="running")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    fetched_count: Mapped[int] = mapped_column(Integer, default=0)
    imported_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    connection: Mapped[SyncConnection] = relationship(back_populates="runs")


class WatchlistItem(Base):
    """A team, player or event a user follows. ``ref_id`` is a provider id, not a foreign key."""

    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", "ref_id", name="uq_watchlist_items_user_kind_ref"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    #: team | player | event
    kind: Mapped[str] = mapped_column(String(16))
    ref_id: Mapped[str] = mapped_column(String(64))
    #: Display name captured when the item was added, so it survives the provider dropping it.
    label: Mapped[str] = mapped_column(String(200))
    league: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    user: Mapped[User] = relationship(back_populates="watchlist_items")


class AlertRule(Base):
    """A condition a user wants to be notified about. Ids are provider ids, not foreign keys."""

    __tablename__ = "alert_rules"
    __table_args__ = (Index("ix_alert_rules_user_state", "user_id", "state"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    #: price_at_least | line_move | game_start | game_final
    kind: Mapped[str] = mapped_column(String(24))
    #: active | triggered | expired | paused
    state: Mapped[str] = mapped_column(String(16), default="active")
    event_id: Mapped[str | None] = mapped_column(String(64))
    team_id: Mapped[str | None] = mapped_column(String(64))
    market: Mapped[str | None] = mapped_column(String(16))
    outcome_key: Mapped[str | None] = mapped_column(String(16))
    line: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    #: price_at_least: the price to reach, as decimal odds.
    threshold_decimal: Mapped[Decimal | None] = mapped_column(ODDS)
    #: line_move: points the consensus line has to move, and where it started.
    min_move: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    baseline_line: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    #: game_start: how long before the start to notify.
    minutes_before: Mapped[int | None] = mapped_column(Integer)
    #: Team-scoped rules: event ids already handled (notified, or already final when the
    #: rule was created or resumed), so each game is notified at most once.
    fired_event_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    #: Bumped each time a triggered rule is re-armed; part of the notification dedupe key.
    arm_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    #: Display name of the event or team captured at creation.
    label: Mapped[str] = mapped_column(String(200))
    league: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
    triggered_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    user: Mapped[User] = relationship(back_populates="alert_rules")


class Notification(Base):
    """An in-app notification. ``dedupe_key`` makes creation idempotent per user."""

    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("user_id", "dedupe_key", name="uq_notifications_user_dedupe_key"),
        Index("ix_notifications_user_created_at", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    #: price_alert | line_move | game_start | game_final | bet_settled | sync_finished |
    #: stake_reminder | new_follower | pick_comment | pick_graded
    kind: Mapped[str] = mapped_column(String(24))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    href: Mapped[str | None] = mapped_column(String(300))
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    #: The alert rule that produced it, if any. Kept as a plain id (the rule id is also part
    #: of ``dedupe_key``) so deleting a rule never touches notifications already delivered.
    rule_id: Mapped[str | None] = mapped_column(String(32), index=True)
    dedupe_key: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    user: Mapped[User] = relationship(back_populates="notifications")


class NotificationPreference(Base):
    """Per-user notification switches. No row means every kind is enabled."""

    __tablename__ = "notification_preferences"

    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    #: Notification kinds switched off for in-app delivery.
    in_app_disabled: Mapped[list[str]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="notification_preferences")


class StakeReminder(Base):
    """A user's weekly staking reminder threshold. A reminder, never a limit."""

    __tablename__ = "stake_reminders"

    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    #: Null means the reminder is off.
    weekly_stake_threshold: Mapped[Decimal | None] = mapped_column(MONEY)
    #: Monday (UTC) of the last week a reminder was created for; one reminder per week.
    last_reminded_week: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="stake_reminder")


class FeatureFlag(Base):
    """A stored override of a feature flag. No row means the in-code default applies."""

    __tablename__ = "feature_flags"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class EmailToken(Base):
    """A single-use, expiring token sent by email. Only its SHA-256 hash is stored."""

    __tablename__ = "email_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    #: verify_email | password_reset
    purpose: Mapped[str] = mapped_column(String(24))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    user: Mapped[User] = relationship(back_populates="email_tokens")


class EmailOutbox(Base):
    """An email the app would have sent. Nothing in this table is ever delivered.

    ``body_text`` and ``dev_link`` contain the link (and so the token) outside production
    only, so local and automated tests can finish the flow. In production the link is
    withheld from both columns.
    """

    __tablename__ = "email_outbox"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    to_email: Mapped[str] = mapped_column(String(320), index=True)
    #: verify_email | password_reset
    template: Mapped[str] = mapped_column(String(40))
    subject: Mapped[str] = mapped_column(String(200))
    body_text: Mapped[str] = mapped_column(Text)
    dev_link: Mapped[str | None] = mapped_column(String(600))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)

    user: Mapped[User] = relationship(back_populates="outbox_emails")


class AuditLog(Base):
    """Append-only audit trail.

    ``user_id`` is intentionally not a foreign key so entries survive account
    deletion. An entry holds the opaque user id, the action, the item acted on
    (``entity_type``, ``entity_id``), the request id, the client IP address and
    ``details``; never the email address.
    """

    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    user_id: Mapped[str | None] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    ip: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON)


# ------------------------------------------------------------------ community
class CommunityProfile(Base):
    """An opt-in public identity. Without a public one a user cannot post and is not listed.

    The handle is the only identifier other users ever see: never the email, the display
    name or the user id.
    """

    __tablename__ = "community_profiles"

    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    #: 3 to 20 characters of ``[a-z0-9_]``, stored lower-case, so unique means unique
    #: whatever the case typed.
    handle: Mapped[str] = mapped_column(String(20), unique=True)
    bio: Mapped[str | None] = mapped_column(Text)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    #: visible | hidden | removed. Anything but ``visible`` was set by a moderator.
    moderation_status: Mapped[str] = mapped_column(
        String(16), default="visible", server_default="visible"
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class CommunityPick(Base):
    """A structured selection posted before the event and graded from the final score.

    There is no stake, no unit size and no confidence rating. ``price_decimal`` is the
    best open, non-stale price the server saw when the pick was posted.
    """

    __tablename__ = "community_picks"
    __table_args__ = (
        UniqueConstraint("user_id", "event_id", "market", name="uq_community_picks_user_event"),
        Index("ix_community_picks_posted_at", "posted_at"),
        Index("ix_community_picks_status_start", "status", "event_start_time"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    #: Provider ids and labels captured at creation. Not foreign keys.
    event_id: Mapped[str] = mapped_column(String(64), index=True)
    league: Mapped[str] = mapped_column(String(32))
    event_label: Mapped[str] = mapped_column(String(200))
    selection: Mapped[str] = mapped_column(String(200))
    event_start_time: Mapped[datetime] = mapped_column(UTCDateTime)
    #: moneyline | spread | total
    market: Mapped[str] = mapped_column(String(16))
    #: home | away | draw | over | under
    outcome_key: Mapped[str] = mapped_column(String(16))
    line: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    price_decimal: Mapped[Decimal] = mapped_column(ODDS)
    #: The sportsbook that offered ``price_decimal`` (key and display name).
    sportsbook_key: Mapped[str] = mapped_column(String(64))
    sportsbook_name: Mapped[str] = mapped_column(String(80))
    analysis: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    #: pending | graded | void (the provider dropped the event before a final score).
    status: Mapped[str] = mapped_column(String(16), default="pending")
    #: won | lost | push once graded.
    result: Mapped[str | None] = mapped_column(String(16))
    graded_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)
    #: visible | hidden | removed. Anything but ``visible`` was set by a moderator.
    moderation_status: Mapped[str] = mapped_column(
        String(16), default="visible", server_default="visible"
    )


class CommunityComment(Base):
    __tablename__ = "community_comments"
    __table_args__ = (Index("ix_community_comments_pick_created", "pick_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    pick_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("community_picks.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    #: Plain text, stored exactly as sent. Clients escape it when they render it.
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    moderation_status: Mapped[str] = mapped_column(
        String(16), default="visible", server_default="visible"
    )


class CommunityFollow(Base):
    __tablename__ = "community_follows"

    follower_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    followed_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class CommunityLike(Base):
    __tablename__ = "community_likes"

    pick_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("community_picks.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class CommunityBlock(Base):
    __tablename__ = "community_blocks"

    blocker_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    blocked_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class CommunityReport(Base):
    """A user's report of a pick, a comment or a profile, for a moderator to resolve."""

    __tablename__ = "community_reports"
    __table_args__ = (Index("ix_community_reports_status_created", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    reporter_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    #: pick | comment | profile
    target_type: Mapped[str] = mapped_column(String(16))
    #: The pick id, the comment id, or the handle as it was when the profile was reported.
    target_id: Mapped[str] = mapped_column(String(32))
    #: Who posted the reported content. The report goes when that account is deleted,
    #: because the content goes with it.
    target_user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    #: spam | harassment | inducement_to_bet | misleading_claims | personal_information | other
    reason: Mapped[str] = mapped_column(String(32))
    details: Mapped[str | None] = mapped_column(Text)
    #: open | resolved
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    #: The administrator who resolved it. A plain id, like ``audit_log.user_id``.
    resolved_by: Mapped[str | None] = mapped_column(String(32))
    #: dismiss | hide_content | remove_content | suspend_author | restore_content
    resolution_action: Mapped[str | None] = mapped_column(String(24))
    resolution_note: Mapped[str | None] = mapped_column(Text)
    #: A copy of what was reported, taken when the report was made, so a moderator can
    #: judge it after its author deleted or edited it: the pick's analysis, the comment's
    #: body or the profile's bio, and for a pick "selection (event)", for a profile
    #: "@handle". Null on reports made before this was stored. It goes with the report,
    #: that is with the reporter's or the author's account.
    target_text_snapshot: Mapped[str | None] = mapped_column(Text)
    target_summary_snapshot: Mapped[str | None] = mapped_column(Text)


class CommunityReservedHandle(Base):
    """A community handle nobody can take: the handle of an account that was deleted while
    it was suspended. Only the handle and the date; nothing that names the account, its
    email address or the reason."""

    __tablename__ = "community_reserved_handles"

    #: Stored lower-case, like ``community_profiles.handle``.
    handle: Mapped[str] = mapped_column(String(20), primary_key=True)
    reserved_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


# ------------------------------------------------------------ snapshot archive
#: Archive primary keys: an 8-byte integer, not the 32-character uuid used elsewhere.
#: These are high-volume, append-only tables, and the integer saves about 25 bytes a
#: row plus index space. SQLite needs plain INTEGER for its auto-increment rowid.
ARCHIVE_ID = BigInteger().with_variant(Integer(), "sqlite")


class SnapshotRun(Base):
    """One capture, prune or index-reclaim pass of the snapshot archive (P0.1).

    ``captured_at`` is the provider's clock at capture, shared by every row the pass
    wrote. The stale thresholds in force are stored, because they decide which archived
    quotes count for best price and consensus: a later change of setting never rewrites
    history. Kept at least ``snapshot_keep_days``, and as long as a kept row refers to
    it; never updated.
    """

    __tablename__ = "snapshot_runs"
    __table_args__ = (
        Index("ix_snapshot_runs_kind_provider_captured", "kind", "provider", "captured_at"),
    )

    id: Mapped[int] = mapped_column(ARCHIVE_ID, primary_key=True, autoincrement=True)
    #: odds | props | status | prune | reclaim
    kind: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(40))
    #: synthetic | replay
    data_mode: Mapped[str] = mapped_column(String(16))
    captured_at: Mapped[datetime] = mapped_column(UTCDateTime)
    #: Wall clock, for operators.
    started_at: Mapped[datetime] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    #: ok | skipped_full | failed; a prune also writes ``started``, with its cutoffs,
    #: before it deletes anything (``archive/prune.py``).
    status: Mapped[str] = mapped_column(String(16))
    #: Changes when the capture rules change. 1 is the first.
    archive_version: Mapped[int] = mapped_column(Integer)
    stale_pregame_seconds: Mapped[int] = mapped_column(Integer)
    stale_live_seconds: Mapped[int] = mapped_column(Integer)
    events_in_scope: Mapped[int] = mapped_column(Integer, default=0)
    rows_written: Mapped[int] = mapped_column(Integer, default=0)
    rows_unchanged: Mapped[int] = mapped_column(Integer, default=0)
    rows_deleted: Mapped[int] = mapped_column(Integer, default=0)
    #: Prune runs: games whose last capture is before this have been reduced to their kept
    #: captures, or are being reduced by this prune (a ``started`` run). It never moves
    #: back from one prune to the next, whatever the settings.
    prune_cutoff: Mapped[datetime | None] = mapped_column(UTCDateTime)
    #: Prune runs: games whose last capture is before this, and capture runs before it
    #: that no kept row refers to, have been removed (the keep horizon). Reads answer
    #: nothing from before it. It never moves back either.
    keep_cutoff: Mapped[datetime | None] = mapped_column(UTCDateTime)
    #: A failed pass: the exception's class name only, never data or a message. A
    #: ``reclaim`` run: index names and byte counts (``archive/reclaim.py``).
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class _SnapshotColumns:
    """Columns every archive row carries.

    ``run_id`` holds ``snapshot_runs.id`` but is deliberately not a foreign key: a
    RESTRICT key with no index on this side makes every run deletion scan the archive,
    and an index would cost about 16 MB a day. A run and its rows share one
    ``captured_at``; the prune removes a run only once it is past the keep horizon and
    no row refers to it any more, rows first.
    ``provider`` is the running provider's name: every read filters on it, so replay
    and synthetic rows never mix. ``provider_id`` and ``fetched_at`` are the record's own
    provenance. Rows are never updated (``archive/guard.py``); the only deletions are
    the retention prune (``archive/prune.py``), the same append-only, age-based stance
    as the audit log.
    """

    id: Mapped[int] = mapped_column(ARCHIVE_ID, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(BigInteger)
    captured_at: Mapped[datetime] = mapped_column(UTCDateTime)
    provider: Mapped[str] = mapped_column(String(40))
    provider_id: Mapped[str] = mapped_column(String(200))
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime)


class ArchivedEvent(_SnapshotColumns, Base):
    """One row per in-scope event per odds capture: the event state staleness depends on.
    These rows are also the coverage record: an event is covered at T by its row from the
    latest successful odds capture at or before T (``archive/view.py``)."""

    __tablename__ = "event_snapshots"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", "captured_at", name="uq_event_snapshots_key"),
        Index("ix_event_snapshots_captured_at", "captured_at"),
    )

    event_id: Mapped[str] = mapped_column(String(64))
    league: Mapped[str] = mapped_column(String(32))
    home_team_id: Mapped[str] = mapped_column(String(64))
    away_team_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    start_time: Mapped[datetime] = mapped_column(UTCDateTime)
    score_home: Mapped[int | None] = mapped_column(Integer)
    score_away: Mapped[int | None] = mapped_column(Integer)
    score_updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    period_text: Mapped[str | None] = mapped_column(String(40))
    markets: Mapped[list[str]] = mapped_column(JSON)


class ArchivedOdds(_SnapshotColumns, Base):
    """One book's quote for one market of one event, written only when it changed. A
    quote that disappears gets a tombstone row (``status='unavailable'``, no outcomes)."""

    __tablename__ = "odds_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "event_id",
            "market",
            "sportsbook_id",
            "captured_at",
            name="uq_odds_snapshots_key",
        ),
        Index("ix_odds_snapshots_captured_at", "captured_at"),
    )

    event_id: Mapped[str] = mapped_column(String(64))
    market: Mapped[str] = mapped_column(String(16))
    sportsbook_id: Mapped[str] = mapped_column(String(64))
    #: The provider's status as given: open | suspended | unavailable | closed.
    status: Mapped[str] = mapped_column(String(16))
    last_updated: Mapped[datetime | None] = mapped_column(UTCDateTime)
    #: ``[[key, name, line, price_american], ...]``
    outcomes: Mapped[list[list[Any]]] = mapped_column(JSON)


class ArchivedProp(_SnapshotColumns, Base):
    """One book's offer for one player market of one game, written only when it changed.
    The game is part of the key, so a player with two games in scope (a doubleheader)
    keeps both games' offers. Once a game leaves scope its open offers get tombstones."""

    __tablename__ = "prop_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "player_id",
            "event_id",
            "market",
            "sportsbook_id",
            "captured_at",
            name="uq_prop_snapshots_key",
        ),
        Index("ix_prop_snapshots_event_captured", "event_id", "captured_at"),
        Index("ix_prop_snapshots_captured_at", "captured_at"),
    )

    player_id: Mapped[str] = mapped_column(String(64))
    event_id: Mapped[str] = mapped_column(String(64))
    sportsbook_id: Mapped[str] = mapped_column(String(64))
    market: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16))
    last_updated: Mapped[datetime | None] = mapped_column(UTCDateTime)
    line: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    over_american: Mapped[int | None] = mapped_column(Integer)
    under_american: Mapped[int | None] = mapped_column(Integer)


class ArchivedStatus(_SnapshotColumns, Base):
    """A lineup, injury, news or weather status record: a status, a source name and times
    only. No article or headline text is stored, which keeps licensed editorial content
    out of the archive. Filled once a provider exists (P0.5)."""

    __tablename__ = "status_snapshots"
    __table_args__ = (
        Index("ix_status_snapshots_event", "provider", "event_id", "captured_at"),
        Index("ix_status_snapshots_player", "provider", "player_id", "captured_at"),
        Index("ix_status_snapshots_captured_at", "captured_at"),
    )

    event_id: Mapped[str | None] = mapped_column(String(64))
    team_id: Mapped[str | None] = mapped_column(String(64))
    player_id: Mapped[str | None] = mapped_column(String(64))
    #: lineup | injury | news | weather
    kind: Mapped[str] = mapped_column(String(16))
    #: expected | confirmed | out | doubtful | questionable | probable | active | reported
    #: | unknown
    status: Mapped[str] = mapped_column(String(24))
    source: Mapped[str] = mapped_column(String(120))
    reported_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


#: Every archive table; the guard, the prune and the size check use this list.
ARCHIVE_MODELS: tuple[type[Base], ...] = (
    SnapshotRun,
    ArchivedEvent,
    ArchivedOdds,
    ArchivedProp,
    ArchivedStatus,
)


# ---------------------------------------------------------- folded text keys
@event.listens_for(User, "before_insert")
@event.listens_for(User, "before_update")
def _set_user_search_key(_mapper: Any, _connection: Any, target: User) -> None:
    target.search_key = user_search_key(target.email, target.display_name)


@event.listens_for(Bet, "before_insert")
@event.listens_for(Bet, "before_update")
def _set_bet_sportsbook_key(_mapper: Any, _connection: Any, target: Bet) -> None:
    target.sportsbook_key = fold(target.sportsbook)
