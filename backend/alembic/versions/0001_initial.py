"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("exchange", sa.String(length=32), nullable=False, server_default="binance"),
        sa.Column("api_key_encrypted", sa.Text()),
        sa.Column("secret_key_encrypted", sa.Text()),
        sa.Column("passphrase_encrypted", sa.Text()),
        sa.Column("risk_percent", sa.Float(), nullable=False, server_default="1"),
        sa.Column("daily_risk_percent", sa.Float(), nullable=False, server_default="3"),
        sa.Column("max_positions", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("min_rating", sa.Integer(), nullable=False, server_default="80"),
        sa.Column("scan_interval", sa.String(length=16), nullable=False, server_default="5m"),
        sa.Column("stop_loss_percent", sa.Float(), nullable=False, server_default="1.5"),
        sa.Column("take_profit_percent", sa.Float(), nullable=False, server_default="3"),
    )
    op.create_table(
        "positions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("current_price", sa.Float(), nullable=False),
        sa.Column("volume", sa.Float(), nullable=False),
        sa.Column("stop", sa.Float(), nullable=False),
        sa.Column("take", sa.Float(), nullable=False),
        sa.Column("pnl", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="OPEN"),
        sa.Column("entered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_positions_symbol", "positions", ["symbol"])
    op.create_table(
        "trades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("exit_price", sa.Float()),
        sa.Column("profit", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_trades_symbol", "trades", ["symbol"])
    op.create_table(
        "signals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("signal", sa.String(length=8), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_signals_symbol", "signals", ["symbol"])
    op.create_table(
        "logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_logs_level", "logs", ["level"])


def downgrade() -> None:
    op.drop_table("logs")
    op.drop_table("signals")
    op.drop_table("trades")
    op.drop_table("positions")
    op.drop_table("settings")
    op.drop_table("users")
