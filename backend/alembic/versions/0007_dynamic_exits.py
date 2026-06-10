"""dynamic exits and breakeven fields

Revision ID: 0007_dynamic_exits
Revises: 0006_strategy_optimizations
Create Date: 2026-06-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_dynamic_exits"
down_revision: str | None = "0006_strategy_optimizations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("settings", sa.Column("atr_stop_multiplier", sa.Float(), nullable=False, server_default="1.5"))
    op.add_column("settings", sa.Column("risk_reward_ratio", sa.Float(), nullable=False, server_default="2"))
    op.add_column("settings", sa.Column("breakeven_trigger_r", sa.Float(), nullable=False, server_default="1"))
    op.add_column("settings", sa.Column("breakeven_offset_percent", sa.Float(), nullable=False, server_default="0.05"))
    op.add_column("positions", sa.Column("initial_risk", sa.Float(), nullable=False, server_default="0"))
    op.add_column("positions", sa.Column("breakeven_applied", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("positions", sa.Column("breakeven_trigger_r", sa.Float(), nullable=False, server_default="1"))
    op.add_column("positions", sa.Column("breakeven_offset_percent", sa.Float(), nullable=False, server_default="0.05"))


def downgrade() -> None:
    op.drop_column("positions", "breakeven_offset_percent")
    op.drop_column("positions", "breakeven_trigger_r")
    op.drop_column("positions", "breakeven_applied")
    op.drop_column("positions", "initial_risk")
    op.drop_column("settings", "breakeven_offset_percent")
    op.drop_column("settings", "breakeven_trigger_r")
    op.drop_column("settings", "risk_reward_ratio")
    op.drop_column("settings", "atr_stop_multiplier")
