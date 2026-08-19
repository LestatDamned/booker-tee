"""Track deletion of temporary uploaded source files.

Revision ID: 20260819_0032
Revises: 20260818_0031
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_0032"
down_revision: str | None = "20260818_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "uploaded_documents",
        "storage_key",
        existing_type=sa.String(length=1024),
        nullable=True,
    )
    op.add_column(
        "uploaded_documents",
        sa.Column("source_file_deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.execute(
        "UPDATE uploaded_documents "
        "SET storage_key = 'retention-deleted/' || id::text "
        "WHERE storage_key IS NULL"
    )
    op.drop_column("uploaded_documents", "source_file_deleted_at")
    op.alter_column(
        "uploaded_documents",
        "storage_key",
        existing_type=sa.String(length=1024),
        nullable=False,
    )
