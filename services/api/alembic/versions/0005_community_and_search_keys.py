"""Community tables and folded text keys for case-insensitive matching.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-16

Additive only: seven new ``community_*`` tables and two new nullable columns,
``users.search_key`` and ``bets.sportsbook_key``. The two columns hold text folded in
Python (``oddvex_api.textnorm``), because SQL ``lower()`` only folds ASCII on SQLite and
on PostgreSQL with the C locale. Existing rows are backfilled here with the same function
the application uses from then on; a row the backfill somehow missed keeps a NULL key and
simply does not match a filter until it is next saved. The community tables start empty:
nobody has a profile until they create one. The downgrade drops exactly what this
revision added.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from oddvex_api.textnorm import fold, user_search_key

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | None = None
depends_on: str | None = None

_MODERATION = {"nullable": False, "server_default": "visible"}


def _user_fk(column: str, table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["users.id"], name=op.f(f"fk_{table}_{column}_users"), ondelete="CASCADE"
    )


def _backfill_keys() -> None:
    connection = op.get_bind()
    users = sa.table(
        "users",
        sa.column("id", sa.String),
        sa.column("email", sa.String),
        sa.column("display_name", sa.String),
        sa.column("search_key", sa.String),
    )
    for user_id, email, display_name in connection.execute(
        sa.select(users.c.id, users.c.email, users.c.display_name)
    ).all():
        connection.execute(
            users.update()
            .where(users.c.id == user_id)
            .values(search_key=user_search_key(email, display_name))
        )
    bets = sa.table(
        "bets", sa.column("sportsbook", sa.String), sa.column("sportsbook_key", sa.String)
    )
    # One UPDATE per distinct sportsbook name, not per bet.
    for (sportsbook,) in connection.execute(sa.select(bets.c.sportsbook).distinct()).all():
        connection.execute(
            bets.update()
            .where(bets.c.sportsbook == sportsbook)
            .values(sportsbook_key=fold(sportsbook))
        )


def upgrade() -> None:
    # Plain ADD COLUMN, not batch mode: SQLite's batch mode rebuilds the table, and
    # dropping the old table with foreign keys on would cascade-delete its children.
    op.add_column("users", sa.Column("search_key", sa.String(length=1024), nullable=True))
    op.add_column("bets", sa.Column("sportsbook_key", sa.String(length=255), nullable=True))
    _backfill_keys()

    op.create_table(
        "community_profiles",
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("handle", sa.String(length=20), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("moderation_status", sa.String(length=16), **_MODERATION),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        _user_fk("user_id", "community_profiles"),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_community_profiles")),
        sa.UniqueConstraint("handle", name=op.f("uq_community_profiles_handle")),
    )

    op.create_table(
        "community_picks",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("league", sa.String(length=32), nullable=False),
        sa.Column("event_label", sa.String(length=200), nullable=False),
        sa.Column("selection", sa.String(length=200), nullable=False),
        sa.Column("event_start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("market", sa.String(length=16), nullable=False),
        sa.Column("outcome_key", sa.String(length=16), nullable=False),
        sa.Column("line", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("price_decimal", sa.Numeric(precision=16, scale=6), nullable=False),
        sa.Column("sportsbook_key", sa.String(length=64), nullable=False),
        sa.Column("sportsbook_name", sa.String(length=80), nullable=False),
        sa.Column("analysis", sa.Text(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("result", sa.String(length=16), nullable=True),
        sa.Column("graded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("home_score", sa.Integer(), nullable=True),
        sa.Column("away_score", sa.Integer(), nullable=True),
        sa.Column("moderation_status", sa.String(length=16), **_MODERATION),
        _user_fk("user_id", "community_picks"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_community_picks")),
        sa.UniqueConstraint("user_id", "event_id", "market", name="uq_community_picks_user_event"),
    )
    op.create_index(op.f("ix_community_picks_user_id"), "community_picks", ["user_id"])
    op.create_index(op.f("ix_community_picks_event_id"), "community_picks", ["event_id"])
    op.create_index("ix_community_picks_posted_at", "community_picks", ["posted_at"])
    op.create_index(
        "ix_community_picks_status_start", "community_picks", ["status", "event_start_time"]
    )

    op.create_table(
        "community_comments",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("pick_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("moderation_status", sa.String(length=16), **_MODERATION),
        sa.ForeignKeyConstraint(
            ["pick_id"],
            ["community_picks.id"],
            name=op.f("fk_community_comments_pick_id_community_picks"),
            ondelete="CASCADE",
        ),
        _user_fk("user_id", "community_comments"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_community_comments")),
    )
    op.create_index(op.f("ix_community_comments_pick_id"), "community_comments", ["pick_id"])
    op.create_index(op.f("ix_community_comments_user_id"), "community_comments", ["user_id"])
    op.create_index(
        "ix_community_comments_pick_created", "community_comments", ["pick_id", "created_at"]
    )

    op.create_table(
        "community_follows",
        sa.Column("follower_id", sa.String(length=32), nullable=False),
        sa.Column("followed_id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        _user_fk("follower_id", "community_follows"),
        _user_fk("followed_id", "community_follows"),
        sa.PrimaryKeyConstraint("follower_id", "followed_id", name=op.f("pk_community_follows")),
    )
    op.create_index(op.f("ix_community_follows_followed_id"), "community_follows", ["followed_id"])

    op.create_table(
        "community_likes",
        sa.Column("pick_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["pick_id"],
            ["community_picks.id"],
            name=op.f("fk_community_likes_pick_id_community_picks"),
            ondelete="CASCADE",
        ),
        _user_fk("user_id", "community_likes"),
        sa.PrimaryKeyConstraint("pick_id", "user_id", name=op.f("pk_community_likes")),
    )
    op.create_index(op.f("ix_community_likes_user_id"), "community_likes", ["user_id"])

    op.create_table(
        "community_blocks",
        sa.Column("blocker_id", sa.String(length=32), nullable=False),
        sa.Column("blocked_id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        _user_fk("blocker_id", "community_blocks"),
        _user_fk("blocked_id", "community_blocks"),
        sa.PrimaryKeyConstraint("blocker_id", "blocked_id", name=op.f("pk_community_blocks")),
    )
    op.create_index(op.f("ix_community_blocks_blocked_id"), "community_blocks", ["blocked_id"])

    op.create_table(
        "community_reports",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("reporter_id", sa.String(length=32), nullable=False),
        sa.Column("target_type", sa.String(length=16), nullable=False),
        sa.Column("target_id", sa.String(length=32), nullable=False),
        sa.Column("target_user_id", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=32), nullable=True),
        sa.Column("resolution_action", sa.String(length=24), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        _user_fk("reporter_id", "community_reports"),
        _user_fk("target_user_id", "community_reports"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_community_reports")),
    )
    op.create_index(op.f("ix_community_reports_reporter_id"), "community_reports", ["reporter_id"])
    op.create_index(
        op.f("ix_community_reports_target_user_id"), "community_reports", ["target_user_id"]
    )
    op.create_index(
        "ix_community_reports_status_created", "community_reports", ["status", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_community_reports_status_created", table_name="community_reports")
    op.drop_index(op.f("ix_community_reports_target_user_id"), table_name="community_reports")
    op.drop_index(op.f("ix_community_reports_reporter_id"), table_name="community_reports")
    op.drop_table("community_reports")
    op.drop_index(op.f("ix_community_blocks_blocked_id"), table_name="community_blocks")
    op.drop_table("community_blocks")
    op.drop_index(op.f("ix_community_likes_user_id"), table_name="community_likes")
    op.drop_table("community_likes")
    op.drop_index(op.f("ix_community_follows_followed_id"), table_name="community_follows")
    op.drop_table("community_follows")
    op.drop_index("ix_community_comments_pick_created", table_name="community_comments")
    op.drop_index(op.f("ix_community_comments_user_id"), table_name="community_comments")
    op.drop_index(op.f("ix_community_comments_pick_id"), table_name="community_comments")
    op.drop_table("community_comments")
    op.drop_index("ix_community_picks_status_start", table_name="community_picks")
    op.drop_index("ix_community_picks_posted_at", table_name="community_picks")
    op.drop_index(op.f("ix_community_picks_event_id"), table_name="community_picks")
    op.drop_index(op.f("ix_community_picks_user_id"), table_name="community_picks")
    op.drop_table("community_picks")
    op.drop_table("community_profiles")
    # Plain DROP COLUMN (needs SQLite 3.35+, which Python 3.13 ships).
    op.drop_column("bets", "sportsbook_key")
    op.drop_column("users", "search_key")
