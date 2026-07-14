"""real market provenance and RL models

Revision ID: 0011_real_market_rl
Revises: 0010_learning_rules
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_real_market_rl"
down_revision: str | None = "0010_learning_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("candles", sa.Column("source", sa.String(length=16), nullable=False, server_default="unknown"))
    op.create_index("ix_candles_source", "candles", ["source"])
    op.create_table(
        "rl_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("algorithm", sa.String(length=16), nullable=False, server_default="PPO"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="CANDIDATE"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("training_candles", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("validation_candles", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metrics", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("feature_schema", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("artifact", sa.LargeBinary()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_rl_models_symbol", "rl_models", ["symbol"])
    op.create_index("ix_rl_models_timeframe", "rl_models", ["timeframe"])
    op.create_index("ix_rl_models_status", "rl_models", ["status"])
    op.create_index("ix_rl_models_is_active", "rl_models", ["is_active"])


def downgrade() -> None:
    op.drop_table("rl_models")
    op.drop_index("ix_candles_source", table_name="candles")
    op.drop_column("candles", "source")
