"""Report snapshots and reserved community handles.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-21

Additive only: two new nullable columns on ``community_reports``,
``target_text_snapshot`` and ``target_summary_snapshot`` (a copy of what was reported,
taken when a report is made, so a moderator can still judge it after its author deleted or
edited it), and one new table, ``community_reserved_handles`` (the handle of an account
deleted while it was suspended, which nobody can take afterwards). Existing reports keep
NULL: what they reported was not copied at the time and is not invented now. The new
table starts empty. The downgrade drops exactly what this revision added.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | None = None
depends_on: str | None = None

_SNAPSHOTS = ("target_text_snapshot", "target_summary_snapshot")


def upgrade() -> None:
    # Plain ADD COLUMN, not batch mode: SQLite's batch mode rebuilds the table, which is
    # not needed for a nullable column on either database.
    for column in _SNAPSHOTS:
        op.add_column("community_reports", sa.Column(column, sa.Text(), nullable=True))
    op.create_table(
        "community_reserved_handles",
        sa.Column("handle", sa.String(length=20), nullable=False),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("handle", name=op.f("pk_community_reserved_handles")),
    )


def downgrade() -> None:
    op.drop_table("community_reserved_handles")
    # Plain DROP COLUMN (needs SQLite 3.35+, which Python 3.13 ships).
    for column in reversed(_SNAPSHOTS):
        op.drop_column("community_reports", column)
