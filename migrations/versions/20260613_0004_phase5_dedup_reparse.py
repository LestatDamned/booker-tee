"""phase5 dedup reparse

Revision ID: 20260613_0004
Revises: 20260613_0003
Create Date: 2026-06-13
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260613_0004"
down_revision: str | None = "20260613_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE raw_transaction_status ADD VALUE IF NOT EXISTS 'possible_duplicate'")


def downgrade() -> None:
    # PostgreSQL cannot drop enum values without recreating the type. Keep this
    # migration non-destructive; rows can be migrated away before a manual type rebuild.
    pass
