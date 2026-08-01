"""normalize the dormant property inactive lifecycle

Revision ID: 20260801_0019
Revises: 20260724_0018
Create Date: 2026-08-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260801_0019"
down_revision: str | None = "20260724_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE properties
        SET status = 'archived',
            archived_at = COALESCE(archived_at, updated_at)
        WHERE status = 'inactive'
        """
    )


def downgrade() -> None:
    # The original inactive/archived intent cannot be reconstructed safely.
    pass
