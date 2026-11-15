"""Watchlist, structured bet legs, auto-settlement marker, password change tracking.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-15

Additive only: one new table and four new columns. Existing rows keep working:
``users.token_version`` gets a server default of 0 (which is what tokens issued
before this migration are treated as), every other new column is nullable.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("ref_id", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("league", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_watchlist_items_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_watchlist_items")),
        sa.UniqueConstraint("user_id", "kind", "ref_id", name="uq_watchlist_items_user_kind_ref"),
    )
    op.create_index(
        op.f("ix_watchlist_items_user_id"), "watchlist_items", ["user_id"], unique=False
    )

    # Plain ADD COLUMN, not batch mode: SQLite's batch mode rebuilds the table, and
    # dropping the old ``users`` table with foreign keys on would cascade-delete bets.
    op.add_column(
        "users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True)))
    op.add_column("bets", sa.Column("settled_by", sa.String(length=16), nullable=True))
    op.add_column("bet_legs", sa.Column("outcome_key", sa.String(length=16), nullable=True))
    # Bets settled by hand before this column existed were settled by the user.
    op.execute("UPDATE bets SET settled_by = 'user' WHERE status = 'settled' AND source = 'manual'")


def downgrade() -> None:
    # Plain DROP COLUMN for the same reason (needs SQLite 3.35+, which Python 3.13 ships).
    op.drop_column("bet_legs", "outcome_key")
    op.drop_column("bets", "settled_by")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "token_version")
    op.drop_index(op.f("ix_watchlist_items_user_id"), table_name="watchlist_items")
    op.drop_table("watchlist_items")
