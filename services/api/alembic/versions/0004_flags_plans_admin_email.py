"""Feature flags, plans, account status, email verification and the email outbox.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-16

Additive only: three new tables and four new columns on ``users``. Existing rows keep
working: ``users.plan`` gets a server default of ``free`` and ``users.status`` of
``active``; ``last_login_at`` and ``email_verified_at`` are nullable (existing accounts
are unverified, which blocks nothing). ``feature_flags`` starts empty: a flag without a
row uses its in-code default. The downgrade drops exactly what this revision added.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Plain ADD COLUMN, not batch mode: SQLite's batch mode rebuilds the table, and
    # dropping the old ``users`` table with foreign keys on would cascade-delete bets.
    op.add_column(
        "users",
        sa.Column("plan", sa.String(length=16), nullable=False, server_default="free"),
    )
    op.add_column(
        "users",
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
    )
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True)))

    op.create_table(
        "feature_flags",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_feature_flags")),
    )

    op.create_table(
        "email_tokens",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("purpose", sa.String(length=24), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_email_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_email_tokens_token_hash")),
    )
    op.create_index(op.f("ix_email_tokens_user_id"), "email_tokens", ["user_id"], unique=False)

    op.create_table(
        "email_outbox",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("to_email", sa.String(length=320), nullable=False),
        sa.Column("template", sa.String(length=40), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("dev_link", sa.String(length=600), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_email_outbox_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_outbox")),
    )
    op.create_index(op.f("ix_email_outbox_user_id"), "email_outbox", ["user_id"], unique=False)
    op.create_index(op.f("ix_email_outbox_to_email"), "email_outbox", ["to_email"], unique=False)
    op.create_index(
        op.f("ix_email_outbox_created_at"), "email_outbox", ["created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_email_outbox_created_at"), table_name="email_outbox")
    op.drop_index(op.f("ix_email_outbox_to_email"), table_name="email_outbox")
    op.drop_index(op.f("ix_email_outbox_user_id"), table_name="email_outbox")
    op.drop_table("email_outbox")
    op.drop_index(op.f("ix_email_tokens_user_id"), table_name="email_tokens")
    op.drop_table("email_tokens")
    op.drop_table("feature_flags")
    # Plain DROP COLUMN for the same reason (needs SQLite 3.35+, which Python 3.13 ships).
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "status")
    op.drop_column("users", "plan")
