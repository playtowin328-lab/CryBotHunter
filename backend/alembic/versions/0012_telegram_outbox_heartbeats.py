"""telegram outbox and worker heartbeats

Revision ID: 0012_telegram_outbox_heartbeats
Revises: 0011_real_market_rl
Create Date: 2026-07-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0012_telegram_outbox_heartbeats"
down_revision: str | None = "0011_real_market_rl"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telegram_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("parse_mode", sa.String(length=16)),
        sa.Column("photo", sa.LargeBinary()),
        sa.Column("photo_filename", sa.String(length=255)),
        sa.Column("photo_caption", sa.Text()),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("text_sent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("photo_sent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("dedupe_key", sa.String(length=255)),
        sa.Column("last_error", sa.String(length=128)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("chat_id", "dedupe_key", name="uq_telegram_outbox_chat_dedupe"),
    )
    op.create_index("ix_telegram_outbox_chat_id", "telegram_outbox", ["chat_id"])
    op.create_index("ix_telegram_outbox_status", "telegram_outbox", ["status"])
    op.create_index("ix_telegram_outbox_next_attempt_at", "telegram_outbox", ["next_attempt_at"])

    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_name", sa.String(length=64), primary_key=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="STARTING"),
        sa.Column("detail", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("stale_alerted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_worker_heartbeats_status", "worker_heartbeats", ["status"])
    op.create_index("ix_worker_heartbeats_last_seen_at", "worker_heartbeats", ["last_seen_at"])


def downgrade() -> None:
    op.drop_index("ix_worker_heartbeats_last_seen_at", table_name="worker_heartbeats")
    op.drop_index("ix_worker_heartbeats_status", table_name="worker_heartbeats")
    op.drop_table("worker_heartbeats")
    op.drop_index("ix_telegram_outbox_next_attempt_at", table_name="telegram_outbox")
    op.drop_index("ix_telegram_outbox_status", table_name="telegram_outbox")
    op.drop_index("ix_telegram_outbox_chat_id", table_name="telegram_outbox")
    op.drop_table("telegram_outbox")
