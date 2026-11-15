"""Initial schema: users, bets, bet_legs, sync_connections, sync_import_runs, audit_log.

Revision ID: 0001
Revises:
Create Date: 2026-11-15

Portable across SQLite and PostgreSQL: only generic SQLAlchemy types are used
(String ids, Numeric money/odds, timezone-aware DateTime, JSON).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=True),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index(op.f("ix_audit_log_action"), "audit_log", ["action"], unique=False)
    op.create_index(op.f("ix_audit_log_created_at"), "audit_log", ["created_at"], unique=False)
    op.create_index(op.f("ix_audit_log_user_id"), "audit_log", ["user_id"], unique=False)

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("age_confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "sync_connections",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("provider_state", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_sync_connections_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_connections")),
    )
    op.create_index(
        op.f("ix_sync_connections_user_id"), "sync_connections", ["user_id"], unique=False
    )

    op.create_table(
        "bets",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("bet_type", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("result", sa.String(length=16), nullable=True),
        sa.Column("sport", sa.String(length=32), nullable=False),
        sa.Column("sportsbook", sa.String(length=80), nullable=False),
        sa.Column("stake", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("odds_decimal", sa.Numeric(precision=16, scale=6), nullable=False),
        sa.Column("odds_source", sa.String(length=16), nullable=False),
        sa.Column("payout", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("profit", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("placed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("sync_connection_id", sa.String(length=32), nullable=True),
        sa.Column("external_provider", sa.String(length=40), nullable=True),
        sa.Column("external_bet_id", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["sync_connection_id"],
            ["sync_connections.id"],
            name=op.f("fk_bets_sync_connection_id_sync_connections"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_bets_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bets")),
        sa.UniqueConstraint(
            "user_id", "external_provider", "external_bet_id", name="uq_bets_user_external"
        ),
    )
    op.create_index(
        op.f("ix_bets_sync_connection_id"), "bets", ["sync_connection_id"], unique=False
    )
    op.create_index(op.f("ix_bets_user_id"), "bets", ["user_id"], unique=False)
    op.create_index("ix_bets_user_placed_at", "bets", ["user_id", "placed_at"], unique=False)
    op.create_index("ix_bets_user_status", "bets", ["user_id", "status"], unique=False)

    op.create_table(
        "sync_import_runs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("connection_id", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("fetched_count", sa.Integer(), nullable=False),
        sa.Column("imported_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("retryable", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["sync_connections.id"],
            name=op.f("fk_sync_import_runs_connection_id_sync_connections"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_import_runs")),
    )
    op.create_index(
        op.f("ix_sync_import_runs_connection_id"),
        "sync_import_runs",
        ["connection_id"],
        unique=False,
    )

    op.create_table(
        "bet_legs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("bet_id", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("selection", sa.String(length=200), nullable=False),
        sa.Column("market", sa.String(length=40), nullable=False),
        sa.Column("league", sa.String(length=32), nullable=True),
        sa.Column("event_id", sa.String(length=64), nullable=True),
        sa.Column("event_label", sa.String(length=200), nullable=True),
        sa.Column("line", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("odds_decimal", sa.Numeric(precision=16, scale=6), nullable=False),
        sa.Column("closing_odds_decimal", sa.Numeric(precision=16, scale=6), nullable=True),
        sa.Column(
            "closing_opposite_odds_decimal", sa.Numeric(precision=16, scale=6), nullable=True
        ),
        sa.Column("result", sa.String(length=16), nullable=True),
        sa.ForeignKeyConstraint(
            ["bet_id"], ["bets.id"], name=op.f("fk_bet_legs_bet_id_bets"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bet_legs")),
    )
    op.create_index(op.f("ix_bet_legs_bet_id"), "bet_legs", ["bet_id"], unique=False)
    op.create_index(op.f("ix_bet_legs_event_id"), "bet_legs", ["event_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_bet_legs_event_id"), table_name="bet_legs")
    op.drop_index(op.f("ix_bet_legs_bet_id"), table_name="bet_legs")

    op.drop_table("bet_legs")
    op.drop_index(op.f("ix_sync_import_runs_connection_id"), table_name="sync_import_runs")

    op.drop_table("sync_import_runs")
    op.drop_index("ix_bets_user_status", table_name="bets")
    op.drop_index("ix_bets_user_placed_at", table_name="bets")
    op.drop_index(op.f("ix_bets_user_id"), table_name="bets")
    op.drop_index(op.f("ix_bets_sync_connection_id"), table_name="bets")

    op.drop_table("bets")
    op.drop_index(op.f("ix_sync_connections_user_id"), table_name="sync_connections")

    op.drop_table("sync_connections")
    op.drop_index(op.f("ix_users_email"), table_name="users")

    op.drop_table("users")
    op.drop_index(op.f("ix_audit_log_user_id"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_created_at"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_action"), table_name="audit_log")

    op.drop_table("audit_log")
