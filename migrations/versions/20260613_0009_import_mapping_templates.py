"""import mapping templates

Revision ID: 20260613_0009
Revises: 20260613_0008
Create Date: 2026-06-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260613_0009"
down_revision: str | None = "20260613_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_mapping_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("bank_name", sa.String(length=255), nullable=True),
        sa.Column("statement_type", sa.String(length=255), nullable=True),
        sa.Column("default_currency", sa.String(length=3), nullable=False),
        sa.Column("column_mapping_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_import_mapping_templates_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_mapping_templates")),
    )
    op.create_index(
        op.f("ix_import_mapping_templates_workspace_id"),
        "import_mapping_templates",
        ["workspace_id"],
    )
    op.create_index(
        "ix_import_mapping_templates_workspace_bank_type",
        "import_mapping_templates",
        ["workspace_id", "bank_name", "statement_type"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_import_mapping_templates_workspace_bank_type",
        table_name="import_mapping_templates",
    )
    op.drop_index(
        op.f("ix_import_mapping_templates_workspace_id"),
        table_name="import_mapping_templates",
    )
    op.drop_table("import_mapping_templates")
