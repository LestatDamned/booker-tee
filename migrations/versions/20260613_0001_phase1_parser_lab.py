"""phase1 parser lab

Revision ID: 20260613_0001
Revises:
Create Date: 2026-06-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260613_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


account_type = sa.Enum("cash", "card", "deposit", "checking", "other", name="account_type")
parse_attempt_status = sa.Enum(
    "running",
    "success",
    "requires_review",
    "failed",
    name="parse_attempt_status",
)
uploaded_document_source = sa.Enum(
    "web_upload",
    "system",
    name="uploaded_document_source",
)
uploaded_document_status = sa.Enum(
    "uploaded",
    "pending_parse",
    "parsing",
    "parsed",
    "requires_review",
    "failed_to_parse",
    "imported",
    "ignored",
    name="uploaded_document_status",
)
uploaded_document_type = sa.Enum(
    "bank_statement",
    "other",
    name="uploaded_document_type",
)
workspace_member_status = sa.Enum(
    "pending",
    "active",
    "disabled",
    "removed",
    name="workspace_member_status",
)
workspace_role = sa.Enum(
    "owner",
    "admin",
    "editor",
    "viewer",
    "uploader",
    "analyst",
    name="workspace_role",
)
workspace_type = sa.Enum(
    "personal",
    "family",
    "business",
    "property_management",
    "project",
    "other",
    name="workspace_type",
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=True),
        sa.Column("type", workspace_type, nullable=False),
        sa.Column("default_currency", sa.String(length=3), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_workspaces_owner_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspaces")),
        sa.UniqueConstraint("slug", name=op.f("uq_workspaces_slug")),
    )
    op.create_index(op.f("ix_workspaces_owner_id"), "workspaces", ["owner_id"])

    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", account_type, nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("initial_balance", sa.Numeric(14, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("bank_name", sa.String(length=255), nullable=True),
        sa.Column("account_number_masked", sa.String(length=64), nullable=True),
        sa.Column("account_number_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("card_last4", sa.String(length=4), nullable=True),
        sa.Column("external_ref", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_accounts_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accounts")),
    )
    op.create_index(op.f("ix_accounts_workspace_id"), "accounts", ["workspace_id"])

    op.create_table(
        "workspace_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", workspace_role, nullable=False),
        sa.Column("status", workspace_member_status, nullable=False),
        sa.Column("invited_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"],
            ["users.id"],
            name=op.f("fk_workspace_members_invited_by_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_workspace_members_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_workspace_members_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_members")),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_members_user"),
    )
    op.create_index(op.f("ix_workspace_members_user_id"), "workspace_members", ["user_id"])
    op.create_index(
        op.f("ix_workspace_members_workspace_id"),
        "workspace_members",
        ["workspace_id"],
    )

    op.create_table(
        "uploaded_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("source", uploaded_document_source, nullable=False),
        sa.Column("document_type", uploaded_document_type, nullable=False),
        sa.Column("status", uploaded_document_status, nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256_hash", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("bank_name", sa.String(length=255), nullable=True),
        sa.Column("statement_type", sa.String(length=255), nullable=True),
        sa.Column("statement_period_start", sa.Date(), nullable=True),
        sa.Column("statement_period_end", sa.Date(), nullable=True),
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_uploaded_documents_account_id_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"],
            ["users.id"],
            name=op.f("fk_uploaded_documents_uploaded_by_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_uploaded_documents_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_uploaded_documents")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_uploaded_documents_storage_key")),
    )
    op.create_index(
        op.f("ix_uploaded_documents_sha256_hash"), "uploaded_documents", ["sha256_hash"]
    )
    op.create_index(
        op.f("ix_uploaded_documents_workspace_id"), "uploaded_documents", ["workspace_id"]
    )
    op.create_index(
        "ix_uploaded_documents_workspace_hash",
        "uploaded_documents",
        ["workspace_id", "sha256_hash"],
    )
    op.create_index(
        "ix_uploaded_documents_workspace_status",
        "uploaded_documents",
        ["workspace_id", "status"],
    )

    op.create_table(
        "parse_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_document_id", sa.Uuid(), nullable=False),
        sa.Column("parser_name", sa.String(length=255), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=True),
        sa.Column("status", parse_attempt_status, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message_sanitized", sa.Text(), nullable=True),
        sa.Column("raw_text_by_page_json", postgresql.JSONB(), nullable=True),
        sa.Column("raw_tables_json", postgresql.JSONB(), nullable=True),
        sa.Column("control_totals_json", postgresql.JSONB(), nullable=True),
        sa.Column("validation_report_json", postgresql.JSONB(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["uploaded_document_id"],
            ["uploaded_documents.id"],
            name=op.f("fk_parse_attempts_uploaded_document_id_uploaded_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_parse_attempts_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parse_attempts")),
    )
    op.create_index(
        op.f("ix_parse_attempts_uploaded_document_id"),
        "parse_attempts",
        ["uploaded_document_id"],
    )
    op.create_index(op.f("ix_parse_attempts_workspace_id"), "parse_attempts", ["workspace_id"])
    op.create_index(
        "ix_parse_attempts_workspace_document",
        "parse_attempts",
        ["workspace_id", "uploaded_document_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_parse_attempts_workspace_document", table_name="parse_attempts")
    op.drop_index(op.f("ix_parse_attempts_workspace_id"), table_name="parse_attempts")
    op.drop_index(op.f("ix_parse_attempts_uploaded_document_id"), table_name="parse_attempts")
    op.drop_table("parse_attempts")

    op.drop_index("ix_uploaded_documents_workspace_status", table_name="uploaded_documents")
    op.drop_index("ix_uploaded_documents_workspace_hash", table_name="uploaded_documents")
    op.drop_index(op.f("ix_uploaded_documents_workspace_id"), table_name="uploaded_documents")
    op.drop_index(op.f("ix_uploaded_documents_sha256_hash"), table_name="uploaded_documents")
    op.drop_table("uploaded_documents")

    op.drop_index(op.f("ix_workspace_members_workspace_id"), table_name="workspace_members")
    op.drop_index(op.f("ix_workspace_members_user_id"), table_name="workspace_members")
    op.drop_table("workspace_members")

    op.drop_index(op.f("ix_accounts_workspace_id"), table_name="accounts")
    op.drop_table("accounts")

    op.drop_index(op.f("ix_workspaces_owner_id"), table_name="workspaces")
    op.drop_table("workspaces")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    workspace_type.drop(bind, checkfirst=True)
    workspace_role.drop(bind, checkfirst=True)
    workspace_member_status.drop(bind, checkfirst=True)
    uploaded_document_type.drop(bind, checkfirst=True)
    uploaded_document_status.drop(bind, checkfirst=True)
    uploaded_document_source.drop(bind, checkfirst=True)
    parse_attempt_status.drop(bind, checkfirst=True)
    account_type.drop(bind, checkfirst=True)
