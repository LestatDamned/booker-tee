"""Add debt persistence foundations.

Revision ID: 20260808_0023
Revises: 20260804_0022
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_0023"
down_revision: str | None = "20260804_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


debt_kind = sa.Enum(
    "loan_receivable",
    "loan_payable",
    "credit_card",
    "mortgage",
    name="debt_kind",
)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE account_type ADD VALUE IF NOT EXISTS 'debt'")
        op.execute("ALTER TYPE operation_source ADD VALUE IF NOT EXISTS 'debt'")

    op.create_table(
        "debts",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("kind", debt_kind, nullable=False),
        sa.Column("opened_on", sa.Date(), nullable=True),
        sa.Column("original_principal", sa.Numeric(14, 2), nullable=True),
        sa.Column("maturity_date", sa.Date(), nullable=True),
        sa.Column("credit_limit", sa.Numeric(14, 2), nullable=True),
        sa.Column("creation_idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("creation_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "credit_limit IS NULL OR credit_limit > 0",
            name=op.f("ck_debts_credit_limit_positive"),
        ),
        sa.CheckConstraint(
            "original_principal IS NULL OR original_principal > 0",
            name=op.f("ck_debts_original_principal_positive"),
        ),
        sa.CheckConstraint(
            "opened_on IS NULL OR maturity_date IS NULL OR maturity_date >= opened_on",
            name=op.f("ck_debts_valid_dates"),
        ),
        sa.CheckConstraint(
            "(kind = 'credit_card' AND credit_limit IS NOT NULL) OR "
            "(kind <> 'credit_card' AND credit_limit IS NULL "
            "AND original_principal IS NOT NULL)",
            name=op.f("ck_debts_valid_terms_for_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_debts_account_id_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_debts_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("account_id", name=op.f("pk_debts")),
        sa.UniqueConstraint(
            "workspace_id",
            "creation_idempotency_key",
            name="uq_debts_workspace_creation_idempotency",
        ),
    )
    op.create_index(
        "ix_debts_workspace_kind",
        "debts",
        ["workspace_id", "kind"],
    )

    op.create_table(
        "debt_payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("debt_account_id", sa.Uuid(), nullable=False),
        sa.Column("principal_operation_id", sa.Uuid(), nullable=True),
        sa.Column("interest_operation_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("idempotency_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "principal_operation_id IS NULL OR interest_operation_id IS NULL "
            "OR principal_operation_id <> interest_operation_id",
            name=op.f("ck_debt_payments_distinct_operations"),
        ),
        sa.CheckConstraint(
            "principal_operation_id IS NOT NULL OR interest_operation_id IS NOT NULL",
            name=op.f("ck_debt_payments_has_operation"),
        ),
        sa.ForeignKeyConstraint(
            ["debt_account_id"],
            ["debts.account_id"],
            name=op.f("fk_debt_payments_debt_account_id_debts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["interest_operation_id"],
            ["operations.id"],
            name=op.f("fk_debt_payments_interest_operation_id_operations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["principal_operation_id"],
            ["operations.id"],
            name=op.f("fk_debt_payments_principal_operation_id_operations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_debt_payments_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_debt_payments")),
        sa.UniqueConstraint(
            "interest_operation_id",
            name="uq_debt_payments_interest_operation",
        ),
        sa.UniqueConstraint(
            "principal_operation_id",
            name="uq_debt_payments_principal_operation",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name="uq_debt_payments_workspace_idempotency",
        ),
    )
    op.create_index(
        "ix_debt_payments_workspace_debt_created",
        "debt_payments",
        ["workspace_id", "debt_account_id", "created_at"],
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM debts)
               OR EXISTS (SELECT 1 FROM accounts WHERE type = 'debt')
               OR EXISTS (SELECT 1 FROM operations WHERE source = 'debt') THEN
                RAISE EXCEPTION
                    'Cannot downgrade debt foundations while debt data exists';
            END IF;
        END
        $$
        """
    )

    op.drop_index(
        "ix_debt_payments_workspace_debt_created",
        table_name="debt_payments",
    )
    op.drop_table("debt_payments")
    op.drop_index("ix_debts_workspace_kind", table_name="debts")
    op.drop_table("debts")
    debt_kind.drop(op.get_bind(), checkfirst=True)

    # PostgreSQL cannot safely remove individual enum labels. The additive
    # account_type/operation_source labels remain unused after downgrade.
