"""phase6 categories properties

Revision ID: 20260613_0005
Revises: 20260613_0004
Create Date: 2026-06-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260613_0005"
down_revision: str | None = "20260613_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


category_kind = sa.Enum(
    "income",
    "expense",
    "transfer",
    "adjustment",
    "mixed",
    name="category_kind",
)
property_status = sa.Enum(
    "active",
    "inactive",
    "archived",
    name="property_status",
)


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", category_kind, nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("system_key", sa.String(length=64), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["categories.id"],
            name=op.f("fk_categories_parent_id_categories"),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_categories_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
    )
    op.create_index(op.f("ix_categories_workspace_id"), "categories", ["workspace_id"])
    op.create_index(
        "ix_categories_workspace_kind",
        "categories",
        ["workspace_id", "kind"],
    )
    op.create_index(
        "ix_categories_workspace_system_key",
        "categories",
        ["workspace_id", "system_key"],
        unique=True,
    )

    op.create_table(
        "properties",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("short_name", sa.String(length=64), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("status", property_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_properties_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_properties")),
    )
    op.create_index(op.f("ix_properties_workspace_id"), "properties", ["workspace_id"])
    op.create_index(
        "ix_properties_workspace_status",
        "properties",
        ["workspace_id", "status"],
    )

    op.create_foreign_key(
        op.f("fk_operations_category_id_categories"),
        "operations",
        "categories",
        ["category_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_operations_property_id_properties"),
        "operations",
        "properties",
        ["property_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_operations_property_id_properties"),
        "operations",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_operations_category_id_categories"),
        "operations",
        type_="foreignkey",
    )
    op.drop_index("ix_properties_workspace_status", table_name="properties")
    op.drop_index(op.f("ix_properties_workspace_id"), table_name="properties")
    op.drop_table("properties")
    op.drop_index("ix_categories_workspace_system_key", table_name="categories")
    op.drop_index("ix_categories_workspace_kind", table_name="categories")
    op.drop_index(op.f("ix_categories_workspace_id"), table_name="categories")
    op.drop_table("categories")
    property_status.drop(op.get_bind(), checkfirst=True)
    category_kind.drop(op.get_bind(), checkfirst=True)
