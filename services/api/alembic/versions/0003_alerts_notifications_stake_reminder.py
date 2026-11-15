"""Alert rules, in-app notifications, notification preferences, staking reminder.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-15

Additive only: four new tables, no change to an existing table. Users without rows in
``notification_preferences`` or ``stake_reminders`` get the defaults (every kind
enabled, reminder off). The downgrade drops the four tables and nothing else.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "alert_rules",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=True),
        sa.Column("team_id", sa.String(length=64), nullable=True),
        sa.Column("market", sa.String(length=16), nullable=True),
        sa.Column("outcome_key", sa.String(length=16), nullable=True),
        sa.Column("line", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("threshold_decimal", sa.Numeric(precision=16, scale=6), nullable=True),
        sa.Column("min_move", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("baseline_line", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("minutes_before", sa.Integer(), nullable=True),
        sa.Column("fired_event_ids", sa.JSON(), nullable=False),
        sa.Column("arm_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("league", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_alert_rules_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alert_rules")),
    )
    op.create_index(op.f("ix_alert_rules_user_id"), "alert_rules", ["user_id"], unique=False)
    op.create_index("ix_alert_rules_user_state", "alert_rules", ["user_id", "state"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("href", sa.String(length=300), nullable=True),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("rule_id", sa.String(length=32), nullable=True),
        sa.Column("dedupe_key", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notifications_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
        sa.UniqueConstraint("user_id", "dedupe_key", name="uq_notifications_user_dedupe_key"),
    )
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False)
    op.create_index(op.f("ix_notifications_rule_id"), "notifications", ["rule_id"], unique=False)
    op.create_index(
        "ix_notifications_user_created_at", "notifications", ["user_id", "created_at"], unique=False
    )

    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("in_app_disabled", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notification_preferences_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_notification_preferences")),
    )

    op.create_table(
        "stake_reminders",
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("weekly_stake_threshold", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("last_reminded_week", sa.Date(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_stake_reminders_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_stake_reminders")),
    )


def downgrade() -> None:
    op.drop_table("stake_reminders")
    op.drop_table("notification_preferences")
    op.drop_index("ix_notifications_user_created_at", table_name="notifications")
    op.drop_index(op.f("ix_notifications_rule_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_alert_rules_user_state", table_name="alert_rules")
    op.drop_index(op.f("ix_alert_rules_user_id"), table_name="alert_rules")
    op.drop_table("alert_rules")
