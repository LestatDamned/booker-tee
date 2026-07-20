"""add manual operation idempotency fields

Revision ID: 20260720_0016
Revises: 20260718_0015
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_0016"
down_revision: str | None = "20260718_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "operations",
        sa.Column("idempotency_key", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "operations",
        sa.Column("idempotency_fingerprint", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "uq_operations_workspace_idempotency_key",
        "operations",
        ["workspace_id", "idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_operations_workspace_idempotency_key", table_name="operations")
    op.drop_column("operations", "idempotency_fingerprint")
    op.drop_column("operations", "idempotency_key")
