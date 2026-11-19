"""A client request id on bets, so a repeated create returns the first bet.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-19

Additive only: one new nullable column, ``bets.client_request_id``, and a unique index on
``(user_id, client_request_id)``. A client sends the id with ``POST /v1/bets`` and sends
the same id when it retries; the index is what makes the second request find the first
bet instead of storing another. Existing rows keep NULL, and NULLs never collide, so no
existing data is touched. The downgrade drops exactly what this revision added.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | None = None
depends_on: str | None = None

_INDEX = "uq_bets_user_client_request"


def upgrade() -> None:
    # Plain ADD COLUMN and CREATE UNIQUE INDEX, not batch mode: SQLite's batch mode
    # rebuilds the table, and dropping the old table with foreign keys on would
    # cascade-delete its legs. A unique index needs no rebuild on either database.
    op.add_column("bets", sa.Column("client_request_id", sa.String(length=64), nullable=True))
    op.create_index(_INDEX, "bets", ["user_id", "client_request_id"], unique=True)


def downgrade() -> None:
    op.drop_index(_INDEX, table_name="bets")
    # Plain DROP COLUMN (needs SQLite 3.35+, which Python 3.13 ships).
    op.drop_column("bets", "client_request_id")
