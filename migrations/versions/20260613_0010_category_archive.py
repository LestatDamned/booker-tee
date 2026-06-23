"""category archive

Revision ID: 20260613_0010
Revises: 20260613_0009
Create Date: 2026-06-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260613_0010"
down_revision: str | None = "20260613_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "categories",
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.create_index(
        "ix_categories_workspace_active",
        "categories",
        ["workspace_id", "is_active"],
    )
    op.alter_column("categories", "is_active", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_categories_workspace_active", table_name="categories")
    op.drop_column("categories", "is_active")
