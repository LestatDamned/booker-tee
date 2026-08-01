"""Add indexes for category delete dependency checks.

Revision ID: 20260801_0020
Revises: 20260801_0019
Create Date: 2026-08-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260801_0020"
down_revision: str | None = "20260801_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_categories_workspace_parent",
        "categories",
        ["workspace_id", "parent_id"],
        unique=False,
    )
    op.create_index(
        "ix_raw_transactions_workspace_suggested_category",
        "raw_transactions",
        ["workspace_id", "suggested_category_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_raw_transactions_workspace_suggested_category",
        table_name="raw_transactions",
    )
    op.drop_index("ix_categories_workspace_parent", table_name="categories")
