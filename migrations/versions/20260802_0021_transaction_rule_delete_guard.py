"""Protect transaction rule suggestion provenance on delete.

Revision ID: 20260802_0021
Revises: 20260801_0020
Create Date: 2026-08-02
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260802_0021"
down_revision: str | None = "20260801_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("fk_raw_transactions_suggested_by_rule_id_transaction_rules"),
        "raw_transactions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_raw_transactions_suggested_by_rule_id_transaction_rules"),
        "raw_transactions",
        "transaction_rules",
        ["suggested_by_rule_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_raw_transactions_workspace_suggested_rule",
        "raw_transactions",
        ["workspace_id", "suggested_by_rule_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_raw_transactions_workspace_suggested_rule",
        table_name="raw_transactions",
    )
    op.drop_constraint(
        op.f("fk_raw_transactions_suggested_by_rule_id_transaction_rules"),
        "raw_transactions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_raw_transactions_suggested_by_rule_id_transaction_rules"),
        "raw_transactions",
        "transaction_rules",
        ["suggested_by_rule_id"],
        ["id"],
        ondelete="SET NULL",
    )
