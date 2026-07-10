"""link trades to positions

Revision ID: 0009_trade_position_link
Revises: 0008_partial_take_profit
Create Date: 2026-07-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_trade_position_link"
down_revision: str | None = "0008_partial_take_profit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("trades", sa.Column("position_id", sa.Integer(), nullable=True))
    op.create_index("ix_trades_position_id", "trades", ["position_id"])
    op.create_foreign_key("fk_trades_position_id_positions", "trades", "positions", ["position_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_trades_position_id_positions", "trades", type_="foreignkey")
    op.drop_index("ix_trades_position_id", table_name="trades")
    op.drop_column("trades", "position_id")
