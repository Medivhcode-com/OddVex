"""ORM models.

Canonical sports entities (leagues, teams, events, odds) are served straight
from the provider in this milestone and are referenced by string id only
(``bet_legs.event_id`` is deliberately not a foreign key). Persisting odds
later means adding ``odds_snapshots`` keyed on
``(provider, event_id, market, sportsbook_id, captured_at)`` with the same
provenance columns the provider contract already carries.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
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
    display_name: Mapped[str | None] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(16), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    age_confirmed_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    bets: Mapped[list[Bet]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    sync_connections: Mapped[list[SyncConnection]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
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
    status: Mapped[str] = mapped_column(String(16), default="pending")
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
    line: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    odds_decimal: Mapped[Decimal] = mapped_column(ODDS)
    closing_odds_decimal: Mapped[Decimal | None] = mapped_column(ODDS)
    closing_opposite_odds_decimal: Mapped[Decimal | None] = mapped_column(ODDS)
    status: Mapped[str] = mapped_column(String(16), default="pending")

    bet: Mapped[Bet] = relationship(back_populates="legs")


class SyncConnection(Base):
    __tablename__ = "sync_connections"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16), default="active")
    account_label: Mapped[str] = mapped_column(String(120))
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
