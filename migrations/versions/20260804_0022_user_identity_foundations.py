"""Add user identity lifecycle foundations.

Revision ID: 20260804_0022
Revises: 20260802_0021
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260804_0022"
down_revision: str | None = "20260802_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


user_token_purpose = sa.Enum(
    "verify_email",
    "reset_password",
    "change_email",
    name="user_token_purpose",
)


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE users SET email_verified_at = created_at "
            "WHERE is_active IS TRUE AND email_verified_at IS NULL"
        )
    )
    op.add_column(
        "user_sessions",
        sa.Column("user_agent_summary", sa.String(length=160), nullable=True),
    )

    op.create_table(
        "user_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", user_token_purpose, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("target_email", sa.String(length=320), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_tokens")),
        sa.UniqueConstraint(
            "purpose",
            "token_hash",
            name="uq_user_tokens_purpose_token_hash",
        ),
    )
    op.create_index(
        op.f("ix_user_tokens_user_id"),
        "user_tokens",
        ["user_id"],
    )
    op.create_index(
        op.f("ix_user_tokens_expires_at"),
        "user_tokens",
        ["expires_at"],
    )
    op.create_index(
        op.f("ix_user_tokens_consumed_at"),
        "user_tokens",
        ["consumed_at"],
    )
    op.create_index(
        "ix_user_tokens_user_purpose_active",
        "user_tokens",
        ["user_id", "purpose", "consumed_at", "expires_at"],
    )

    op.create_table(
        "auth_rate_limits",
        sa.Column("bucket_hash", sa.String(length=64), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("bucket_hash", name=op.f("pk_auth_rate_limits")),
    )
    op.create_index(
        op.f("ix_auth_rate_limits_expires_at"),
        "auth_rate_limits",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_auth_rate_limits_expires_at"), table_name="auth_rate_limits")
    op.drop_table("auth_rate_limits")

    op.drop_index("ix_user_tokens_user_purpose_active", table_name="user_tokens")
    op.drop_index(op.f("ix_user_tokens_consumed_at"), table_name="user_tokens")
    op.drop_index(op.f("ix_user_tokens_expires_at"), table_name="user_tokens")
    op.drop_index(op.f("ix_user_tokens_user_id"), table_name="user_tokens")
    op.drop_table("user_tokens")
    user_token_purpose.drop(op.get_bind(), checkfirst=True)

    op.drop_column("user_sessions", "user_agent_summary")
    op.drop_column("users", "deactivated_at")
    op.drop_column("users", "email_verified_at")
