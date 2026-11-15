"""ORM models.

Canonical sports entities (leagues, teams, events, odds) are served straight
from the provider in this milestone and are referenced by string id only
(``bet_legs.event_id`` is deliberately not a foreign key). Persisting odds
later means adding ``odds_snapshots`` keyed on
``(provider, event_id, market, sportsbook_id, captured_at)`` with the same
provenance columns the provider contract already carries.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

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


class Bet(Base):
    __tablename__ = "bets"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "external_provider", "external_bet_id", name="uq_bets_user_external"
        ),
        Index("ix_bets_user_status", "user_id", "status"),
        Index("ix_bets_user_placed_at", "user_id", "placed_at"),
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
    #: stake_reminder
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


class AuditLog(Base):
    """Append-only audit trail.

    ``user_id`` is intentionally not a foreign key so entries survive account
    deletion (the id is opaque and no personal data is stored in ``details``).
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
