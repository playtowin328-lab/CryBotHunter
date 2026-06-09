"""orders table

Revision ID: 0005_orders
Revises: 0004_agent_decisions
Create Date: 2026-06-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_orders"
down_revision: str | None = "0004_agent_decisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exchange_order_id", sa.String(length=128)),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("order_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="NEW"),
        sa.Column("requested_amount", sa.Float(), nullable=False),
        sa.Column("filled_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("requested_price", sa.Float()),
        sa.Column("average_price", sa.Float()),
        sa.Column("fee", sa.Float(), nullable=False, server_default="0"),
        sa.Column("slippage", sa.Float(), nullable=False, server_default="0"),
        sa.Column("raw", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_orders_exchange_order_id", "orders", ["exchange_order_id"])
    op.create_index("ix_orders_symbol", "orders", ["symbol"])


def downgrade() -> None:
    op.drop_table("orders")
