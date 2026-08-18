"""Replace session token hash with rotating refresh token state.

Revision ID: 20260812_0030
Revises: 20260810_0029
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0030"
down_revision: str | None = "20260810_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_user_sessions_token_hash", table_name="user_sessions")
    op.alter_column(
        "user_sessions",
        "session_token_hash",
        new_column_name="refresh_token_hash",
    )
    op.add_column(
        "user_sessions",
        sa.Column("previous_refresh_token_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "user_sessions",
        sa.Column("refresh_rotated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_user_sessions_refresh_hash",
        "user_sessions",
        ["refresh_token_hash"],
        unique=True,
    )
    op.execute("UPDATE user_sessions SET revoked_at = now() WHERE revoked_at IS NULL")


def downgrade() -> None:
    op.drop_index("ix_user_sessions_refresh_hash", table_name="user_sessions")
    op.drop_column("user_sessions", "refresh_rotated_at")
    op.drop_column("user_sessions", "previous_refresh_token_hash")
    op.alter_column(
        "user_sessions",
        "refresh_token_hash",
        new_column_name="session_token_hash",
    )
    op.create_index(
        "ix_user_sessions_token_hash",
        "user_sessions",
        ["session_token_hash"],
        unique=True,
    )
