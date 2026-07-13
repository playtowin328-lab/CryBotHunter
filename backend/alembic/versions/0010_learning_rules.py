"""learning rules

Revision ID: 0010_learning_rules
Revises: 0009_trade_position_link
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_learning_rules"
down_revision: str | None = "0009_trade_position_link"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("positions", sa.Column("entry_context", sa.JSON(), nullable=False, server_default="{}"))
    op.create_table(
        "learning_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope", sa.String(length=32), nullable=False, server_default="GLOBAL"),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("feature_key", sa.String(length=64), nullable=False),
        sa.Column("feature_value", sa.String(length=128), nullable=False),
        sa.Column("penalty", sa.Float(), nullable=False, server_default="0"),
        sa.Column("observations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_profit", sa.Float(), nullable=False, server_default="0"),
        sa.Column("last_reason", sa.String(length=128)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("scope", "side", "feature_key", "feature_value", name="uq_learning_rule"),
    )
    op.create_index("ix_learning_rules_scope", "learning_rules", ["scope"])
    op.create_index("ix_learning_rules_side", "learning_rules", ["side"])
    op.create_index("ix_learning_rules_feature_key", "learning_rules", ["feature_key"])
    op.create_index("ix_learning_rules_feature_value", "learning_rules", ["feature_value"])


def downgrade() -> None:
    op.drop_table("learning_rules")
    op.drop_column("positions", "entry_context")
