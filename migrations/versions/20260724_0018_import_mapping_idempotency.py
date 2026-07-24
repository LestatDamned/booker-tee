"""add idempotent import mapping executions

Revision ID: 20260724_0018
Revises: 20260722_0017
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260724_0018"
down_revision: str | None = "20260722_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_mapping_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_document_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=36), nullable=False),
        sa.Column("payload_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("imported_row_count", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["import_mapping_templates.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_document_id"],
            ["uploaded_documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "uploaded_document_id",
            "idempotency_key",
            name="uq_import_mapping_executions_workspace_document_key",
        ),
    )
    op.create_index(
        "ix_import_mapping_executions_workspace_id",
        "import_mapping_executions",
        ["workspace_id"],
    )
    op.create_index(
        "ix_import_mapping_executions_workspace_document",
        "import_mapping_executions",
        ["workspace_id", "uploaded_document_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_import_mapping_executions_workspace_document",
        table_name="import_mapping_executions",
    )
    op.drop_index(
        "ix_import_mapping_executions_workspace_id",
        table_name="import_mapping_executions",
    )
    op.drop_table("import_mapping_executions")
