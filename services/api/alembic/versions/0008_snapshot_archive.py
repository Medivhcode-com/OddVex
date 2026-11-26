"""Snapshot archive (P0.1).

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-26

Additive only: five new tables, ``snapshot_runs``, ``event_snapshots``,
``odds_snapshots``, ``prop_snapshots`` and ``status_snapshots``, with their indexes. No
existing table is touched. They start empty and stay empty while the
``snapshot_archive`` flag is off.

The downgrade drops the five tables, which deletes archive data and nothing else. Never
run it on the preview without a dump (``infrastructure/hostinger/ops.sh`` takes one before
every deploy).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | None = None
depends_on: str | None = None

_ID = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
_TABLES = (
    "status_snapshots",
    "prop_snapshots",
    "odds_snapshots",
    "event_snapshots",
    "snapshot_runs",
)


def _common() -> list[sa.Column[object]]:
    return [
        sa.Column("id", _ID, autoincrement=True, nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_id", sa.String(length=200), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "snapshot_runs",
        sa.Column("id", _ID, autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("data_mode", sa.String(length=16), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("archive_version", sa.Integer(), nullable=False),
        sa.Column("stale_pregame_seconds", sa.Integer(), nullable=False),
        sa.Column("stale_live_seconds", sa.Integer(), nullable=False),
        sa.Column("events_in_scope", sa.Integer(), nullable=False),
        sa.Column("rows_written", sa.Integer(), nullable=False),
        sa.Column("rows_unchanged", sa.Integer(), nullable=False),
        sa.Column("rows_deleted", sa.Integer(), nullable=False),
        sa.Column("prune_cutoff", sa.DateTime(timezone=True), nullable=True),
        sa.Column("keep_cutoff", sa.DateTime(timezone=True), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_snapshot_runs")),
    )
    op.create_index(
        "ix_snapshot_runs_kind_provider_captured",
        "snapshot_runs",
        ["kind", "provider", "captured_at"],
    )

    op.create_table(
        "event_snapshots",
        *_common(),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("league", sa.String(length=32), nullable=False),
        sa.Column("home_team_id", sa.String(length=64), nullable=False),
        sa.Column("away_team_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("score_home", sa.Integer(), nullable=True),
        sa.Column("score_away", sa.Integer(), nullable=True),
        sa.Column("score_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_text", sa.String(length=40), nullable=True),
        sa.Column("markets", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event_snapshots")),
        sa.UniqueConstraint("provider", "event_id", "captured_at", name="uq_event_snapshots_key"),
    )
    op.create_index("ix_event_snapshots_captured_at", "event_snapshots", ["captured_at"])

    op.create_table(
        "odds_snapshots",
        *_common(),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("market", sa.String(length=16), nullable=False),
        sa.Column("sportsbook_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcomes", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_odds_snapshots")),
        sa.UniqueConstraint(
            "provider",
            "event_id",
            "market",
            "sportsbook_id",
            "captured_at",
            name="uq_odds_snapshots_key",
        ),
    )
    op.create_index("ix_odds_snapshots_captured_at", "odds_snapshots", ["captured_at"])

    op.create_table(
        "prop_snapshots",
        *_common(),
        sa.Column("player_id", sa.String(length=64), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("sportsbook_id", sa.String(length=64), nullable=False),
        sa.Column("market", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=True),
        sa.Column("line", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("over_american", sa.Integer(), nullable=True),
        sa.Column("under_american", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prop_snapshots")),
        sa.UniqueConstraint(
            "provider",
            "player_id",
            "event_id",
            "market",
            "sportsbook_id",
            "captured_at",
            name="uq_prop_snapshots_key",
        ),
    )
    op.create_index(
        "ix_prop_snapshots_event_captured", "prop_snapshots", ["event_id", "captured_at"]
    )
    op.create_index("ix_prop_snapshots_captured_at", "prop_snapshots", ["captured_at"])

    op.create_table(
        "status_snapshots",
        *_common(),
        sa.Column("event_id", sa.String(length=64), nullable=True),
        sa.Column("team_id", sa.String(length=64), nullable=True),
        sa.Column("player_id", sa.String(length=64), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_status_snapshots")),
    )
    op.create_index(
        "ix_status_snapshots_event", "status_snapshots", ["provider", "event_id", "captured_at"]
    )
    op.create_index(
        "ix_status_snapshots_player", "status_snapshots", ["provider", "player_id", "captured_at"]
    )
    op.create_index("ix_status_snapshots_captured_at", "status_snapshots", ["captured_at"])


def downgrade() -> None:
    # Dropping a table drops its indexes with it.
    for table in _TABLES:
        op.drop_table(table)
