"""position lifecycle fields

Revision ID: 0002_position_lifecycle
Revises: 0001_initial
Create Date: 2026-06-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_position_lifecycle"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("settings", sa.Column("trailing_stop_percent", sa.Float(), nullable=False, server_default="0.8"))
    op.add_column("positions", sa.Column("trailing_stop_percent", sa.Float(), nullable=False, server_default="0.8"))
    op.add_column("positions", sa.Column("highest_price", sa.Float(), nullable=False, server_default="0"))
    op.add_column("positions", sa.Column("lowest_price", sa.Float(), nullable=False, server_default="0"))
    op.add_column("positions", sa.Column("exit_reason", sa.String(length=32)))
    op.add_column("positions", sa.Column("closed_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("positions", "closed_at")
    op.drop_column("positions", "exit_reason")
    op.drop_column("positions", "lowest_price")
    op.drop_column("positions", "highest_price")
    op.drop_column("positions", "trailing_stop_percent")
    op.drop_column("settings", "trailing_stop_percent")
