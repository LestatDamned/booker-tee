"""Add persistent Telegram webhook update deduplication.

Revision ID: 20260818_0031
Revises: 20260812_0030
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260818_0031"
down_revision: str | None = "20260812_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telegram_webhook_updates",
        sa.Column("update_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("update_id", name=op.f("pk_telegram_webhook_updates")),
    )


def downgrade() -> None:
    op.drop_table("telegram_webhook_updates")
