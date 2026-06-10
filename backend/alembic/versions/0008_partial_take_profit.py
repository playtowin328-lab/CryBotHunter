"""partial take profit fields

Revision ID: 0008_partial_take_profit
Revises: 0007_dynamic_exits
Create Date: 2026-06-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_partial_take_profit"
down_revision: str | None = "0007_dynamic_exits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("settings", sa.Column("partial_take_profit_r", sa.Float(), nullable=False, server_default="1"))
    op.add_column("settings", sa.Column("partial_close_percent", sa.Float(), nullable=False, server_default="50"))
    op.add_column("positions", sa.Column("partial_take_profit_r", sa.Float(), nullable=False, server_default="1"))
    op.add_column("positions", sa.Column("partial_close_percent", sa.Float(), nullable=False, server_default="50"))
    op.add_column("positions", sa.Column("partial_taken", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("positions", "partial_taken")
    op.drop_column("positions", "partial_close_percent")
    op.drop_column("positions", "partial_take_profit_r")
    op.drop_column("settings", "partial_close_percent")
    op.drop_column("settings", "partial_take_profit_r")
