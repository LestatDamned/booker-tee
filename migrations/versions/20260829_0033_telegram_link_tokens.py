"""Add one-time Telegram account link tokens.

Revision ID: 20260829_0033
Revises: 20260819_0032
Create Date: 2026-08-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260829_0033"
down_revision: str | None = "20260819_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE user_token_purpose ADD VALUE IF NOT EXISTS 'link_telegram'")


def downgrade() -> None:
    op.execute("DELETE FROM user_tokens WHERE purpose = 'link_telegram'")
