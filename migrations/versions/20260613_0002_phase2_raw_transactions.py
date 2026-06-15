"""phase2 raw transactions

Revision ID: 20260613_0002
Revises: 20260613_0001
Create Date: 2026-06-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260613_0002"
down_revision: str | None = "20260613_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


raw_transaction_status = sa.Enum(
    "extracted",
    "normalized",
    "suggested",
    "needs_review",
    "matched",
    "ignored",
    "duplicate",
    "failed",
    name="raw_transaction_status",
)


def upgrade() -> None:
    op.create_table(
        "raw_transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_document_id", sa.Uuid(), nullable=False),
        sa.Column("parse_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("status", raw_transaction_status, nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False),
        sa.Column("operation_date_raw", sa.String(length=64), nullable=True),
        sa.Column("posting_date_raw", sa.String(length=64), nullable=True),
        sa.Column("description_raw", sa.Text(), nullable=True),
        sa.Column("amount_raw", sa.String(length=128), nullable=True),
        sa.Column("currency_raw", sa.String(length=16), nullable=True),
        sa.Column("balance_after_raw", sa.String(length=128), nullable=True),
        sa.Column("account_hint_raw", sa.Text(), nullable=True),
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("operation_date", sa.Date(), nullable=True),
        sa.Column("posting_date", sa.Date(), nullable=True),
        sa.Column("description_normalized", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("balance_after", sa.Numeric(14, 2), nullable=True),
        sa.Column("dedupe_hash", sa.String(length=64), nullable=True),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("linked_operation_id", sa.Uuid(), nullable=True),
        sa.Column("normalization_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_raw_transactions_account_id_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["parse_attempt_id"],
            ["parse_attempts.id"],
            name=op.f("fk_raw_transactions_parse_attempt_id_parse_attempts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_document_id"],
            ["uploaded_documents.id"],
            name=op.f("fk_raw_transactions_uploaded_document_id_uploaded_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_raw_transactions_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_raw_transactions")),
    )
    op.create_index(
        op.f("ix_raw_transactions_parse_attempt_id"), "raw_transactions", ["parse_attempt_id"]
    )
    op.create_index(
        op.f("ix_raw_transactions_uploaded_document_id"),
        "raw_transactions",
        ["uploaded_document_id"],
    )
    op.create_index(op.f("ix_raw_transactions_workspace_id"), "raw_transactions", ["workspace_id"])
    op.create_index(
        "ix_raw_transactions_workspace_attempt",
        "raw_transactions",
        ["workspace_id", "parse_attempt_id"],
    )
    op.create_index(
        "ix_raw_transactions_workspace_dedupe_hash",
        "raw_transactions",
        ["workspace_id", "dedupe_hash"],
    )
    op.create_index(
        "ix_raw_transactions_workspace_document",
        "raw_transactions",
        ["workspace_id", "uploaded_document_id"],
    )
    op.create_index(
        "ix_raw_transactions_workspace_status",
        "raw_transactions",
        ["workspace_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_raw_transactions_workspace_status", table_name="raw_transactions")
    op.drop_index("ix_raw_transactions_workspace_document", table_name="raw_transactions")
    op.drop_index("ix_raw_transactions_workspace_dedupe_hash", table_name="raw_transactions")
    op.drop_index("ix_raw_transactions_workspace_attempt", table_name="raw_transactions")
    op.drop_index(op.f("ix_raw_transactions_workspace_id"), table_name="raw_transactions")
    op.drop_index(op.f("ix_raw_transactions_uploaded_document_id"), table_name="raw_transactions")
    op.drop_index(op.f("ix_raw_transactions_parse_attempt_id"), table_name="raw_transactions")
    op.drop_table("raw_transactions")
    raw_transaction_status.drop(op.get_bind(), checkfirst=True)
