"""transaction rules

Revision ID: 20260613_0006
Revises: 20260613_0005
Create Date: 2026-06-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260613_0006"
down_revision: str | None = "20260613_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


transaction_rule_match_type = postgresql.ENUM(
    "contains",
    "exact",
    name="transaction_rule_match_type",
    create_type=False,
)
money_direction = postgresql.ENUM(
    "inflow",
    "outflow",
    "any",
    name="money_direction",
    create_type=False,
)
operation_type = postgresql.ENUM(
    "income",
    "expense",
    "transfer",
    "adjustment",
    name="operation_type",
    create_type=False,
)


def upgrade() -> None:
    transaction_rule_match_type.create(op.get_bind(), checkfirst=True)
    money_direction.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "transaction_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("match_type", transaction_rule_match_type, nullable=False),
        sa.Column("pattern", sa.String(length=255), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("amount_min", sa.Numeric(14, 2), nullable=True),
        sa.Column("amount_max", sa.Numeric(14, 2), nullable=True),
        sa.Column("direction", money_direction, nullable=False),
        sa.Column("target_operation_type", operation_type, nullable=True),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("property_id", sa.Uuid(), nullable=True),
        sa.Column("auto_description", sa.Text(), nullable=True),
        sa.Column("affects_profit", sa.Boolean(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_transaction_rules_account_id_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_transaction_rules_category_id_categories"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_transaction_rules_created_by_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
            name=op.f("fk_transaction_rules_property_id_properties"),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_transaction_rules_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transaction_rules")),
    )
    op.create_index(
        op.f("ix_transaction_rules_workspace_id"),
        "transaction_rules",
        ["workspace_id"],
    )
    op.create_index(
        "ix_transaction_rules_workspace_active",
        "transaction_rules",
        ["workspace_id", "is_active", "priority"],
    )
    op.create_index(
        "ix_transaction_rules_workspace_category",
        "transaction_rules",
        ["workspace_id", "category_id"],
    )

    op.add_column("raw_transactions", sa.Column("suggested_category_id", sa.Uuid()))
    op.add_column("raw_transactions", sa.Column("suggested_property_id", sa.Uuid()))
    op.add_column("raw_transactions", sa.Column("suggested_operation_type", operation_type))
    op.add_column("raw_transactions", sa.Column("suggested_by_rule_id", sa.Uuid()))
    op.create_foreign_key(
        op.f("fk_raw_transactions_suggested_category_id_categories"),
        "raw_transactions",
        "categories",
        ["suggested_category_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_raw_transactions_suggested_property_id_properties"),
        "raw_transactions",
        "properties",
        ["suggested_property_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_raw_transactions_suggested_by_rule_id_transaction_rules"),
        "raw_transactions",
        "transaction_rules",
        ["suggested_by_rule_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_raw_transactions_suggested_by_rule_id_transaction_rules"),
        "raw_transactions",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_raw_transactions_suggested_property_id_properties"),
        "raw_transactions",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_raw_transactions_suggested_category_id_categories"),
        "raw_transactions",
        type_="foreignkey",
    )
    op.drop_column("raw_transactions", "suggested_by_rule_id")
    op.drop_column("raw_transactions", "suggested_operation_type")
    op.drop_column("raw_transactions", "suggested_property_id")
    op.drop_column("raw_transactions", "suggested_category_id")

    op.drop_index("ix_transaction_rules_workspace_category", table_name="transaction_rules")
    op.drop_index("ix_transaction_rules_workspace_active", table_name="transaction_rules")
    op.drop_index(op.f("ix_transaction_rules_workspace_id"), table_name="transaction_rules")
    op.drop_table("transaction_rules")
    money_direction.drop(op.get_bind(), checkfirst=True)
    transaction_rule_match_type.drop(op.get_bind(), checkfirst=True)
