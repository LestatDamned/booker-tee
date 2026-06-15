"""phase4 ledger posting

Revision ID: 20260613_0003
Revises: 20260613_0002
Create Date: 2026-06-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260613_0003"
down_revision: str | None = "20260613_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


operation_type = sa.Enum(
    "income",
    "expense",
    "transfer",
    "adjustment",
    name="operation_type",
)
operation_status = sa.Enum(
    "draft",
    "needs_review",
    "confirmed",
    "ignored",
    "duplicate",
    name="operation_status",
)
operation_source = sa.Enum(
    "manual",
    "bank_pdf",
    "system",
    name="operation_source",
)


def upgrade() -> None:
    op.execute("ALTER TYPE raw_transaction_status ADD VALUE IF NOT EXISTS 'confirmed'")
    op.create_table(
        "operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("type", operation_type, nullable=False),
        sa.Column("status", operation_status, nullable=False),
        sa.Column("affects_profit", sa.Boolean(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("property_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("operation_date", sa.Date(), nullable=False),
        sa.Column("posting_date", sa.Date(), nullable=True),
        sa.Column("source", operation_source, nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_operations_created_by_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name=op.f("fk_operations_updated_by_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_operations_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_operations")),
    )
    op.create_index(op.f("ix_operations_workspace_id"), "operations", ["workspace_id"])
    op.create_index(
        "ix_operations_workspace_category",
        "operations",
        ["workspace_id", "category_id"],
    )
    op.create_index(
        "ix_operations_workspace_date",
        "operations",
        ["workspace_id", "operation_date"],
    )
    op.create_index(
        "ix_operations_workspace_property",
        "operations",
        ["workspace_id", "property_id"],
    )
    op.create_index(
        "ix_operations_workspace_status",
        "operations",
        ["workspace_id", "status"],
    )

    op.create_table(
        "money_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("entry_order", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Numeric(14, 2), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_money_entries_account_id_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["operation_id"],
            ["operations.id"],
            name=op.f("fk_money_entries_operation_id_operations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_money_entries_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_money_entries")),
    )
    op.create_index(op.f("ix_money_entries_account_id"), "money_entries", ["account_id"])
    op.create_index(op.f("ix_money_entries_operation_id"), "money_entries", ["operation_id"])
    op.create_index(op.f("ix_money_entries_workspace_id"), "money_entries", ["workspace_id"])
    op.create_index(
        "ix_money_entries_workspace_account",
        "money_entries",
        ["workspace_id", "account_id"],
    )
    op.create_index(
        "ix_money_entries_workspace_operation",
        "money_entries",
        ["workspace_id", "operation_id"],
    )

    op.create_foreign_key(
        op.f("fk_raw_transactions_linked_operation_id_operations"),
        "raw_transactions",
        "operations",
        ["linked_operation_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_raw_transactions_linked_operation_id_operations"),
        "raw_transactions",
        type_="foreignkey",
    )
    op.drop_index("ix_money_entries_workspace_operation", table_name="money_entries")
    op.drop_index("ix_money_entries_workspace_account", table_name="money_entries")
    op.drop_index(op.f("ix_money_entries_workspace_id"), table_name="money_entries")
    op.drop_index(op.f("ix_money_entries_operation_id"), table_name="money_entries")
    op.drop_index(op.f("ix_money_entries_account_id"), table_name="money_entries")
    op.drop_table("money_entries")
    op.drop_index("ix_operations_workspace_status", table_name="operations")
    op.drop_index("ix_operations_workspace_property", table_name="operations")
    op.drop_index("ix_operations_workspace_date", table_name="operations")
    op.drop_index("ix_operations_workspace_category", table_name="operations")
    op.drop_index(op.f("ix_operations_workspace_id"), table_name="operations")
    op.drop_table("operations")
    operation_source.drop(op.get_bind(), checkfirst=True)
    operation_status.drop(op.get_bind(), checkfirst=True)
    operation_type.drop(op.get_bind(), checkfirst=True)
