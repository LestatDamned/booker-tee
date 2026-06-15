"""transaction rule application mode

Revision ID: 20260613_0007
Revises: 20260613_0006
Create Date: 2026-06-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260613_0007"
down_revision: str | None = "20260613_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


transaction_rule_application_mode = postgresql.ENUM(
    "suggest",
    "auto_apply",
    name="transaction_rule_application_mode",
    create_type=False,
)


def upgrade() -> None:
    transaction_rule_application_mode.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "transaction_rules",
        sa.Column(
            "application_mode",
            transaction_rule_application_mode,
            server_default="suggest",
            nullable=False,
        ),
    )
    op.alter_column("transaction_rules", "application_mode", server_default=None)


def downgrade() -> None:
    op.drop_column("transaction_rules", "application_mode")
    transaction_rule_application_mode.drop(op.get_bind(), checkfirst=True)
