"""guard confirmed raw transaction dedupe hashes

Revision ID: 20260722_0017
Revises: 20260720_0016
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260722_0017"
down_revision: str | None = "20260720_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_raw_transactions_workspace_confirmed_dedupe_hash",
        "raw_transactions",
        ["workspace_id", "dedupe_hash"],
        unique=True,
        postgresql_where=sa.text("status = 'confirmed' AND dedupe_hash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_raw_transactions_workspace_confirmed_dedupe_hash",
        table_name="raw_transactions",
    )
