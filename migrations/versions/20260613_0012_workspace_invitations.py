"""workspace invitations

Revision ID: 20260613_0012
Revises: 20260613_0011
Create Date: 2026-06-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260613_0012"
down_revision: str | None = "20260613_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


workspace_role = postgresql.ENUM(
    "owner",
    "admin",
    "editor",
    "viewer",
    "uploader",
    "analyst",
    name="workspace_role",
    create_type=False,
)
workspace_invitation_status = sa.Enum(
    "pending",
    "accepted",
    "revoked",
    "expired",
    name="workspace_invitation_status",
)


def upgrade() -> None:
    op.create_table(
        "workspace_invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("role", workspace_role, nullable=False),
        sa.Column("status", workspace_invitation_status, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("invited_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("accepted_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["accepted_by_user_id"],
            ["users.id"],
            name=op.f("fk_workspace_invitations_accepted_by_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"],
            ["users.id"],
            name=op.f("fk_workspace_invitations_invited_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_workspace_invitations_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_invitations")),
    )
    op.create_index(
        op.f("ix_workspace_invitations_workspace_id"),
        "workspace_invitations",
        ["workspace_id"],
    )
    op.create_index(
        "ix_workspace_invitations_token_hash",
        "workspace_invitations",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_workspace_invitations_workspace_status",
        "workspace_invitations",
        ["workspace_id", "status"],
    )
    op.create_index(
        "ix_workspace_invitations_expires_at",
        "workspace_invitations",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_workspace_invitations_expires_at", table_name="workspace_invitations")
    op.drop_index("ix_workspace_invitations_workspace_status", table_name="workspace_invitations")
    op.drop_index("ix_workspace_invitations_token_hash", table_name="workspace_invitations")
    op.drop_index(
        op.f("ix_workspace_invitations_workspace_id"),
        table_name="workspace_invitations",
    )
    op.drop_table("workspace_invitations")

    bind = op.get_bind()
    workspace_invitation_status.drop(bind, checkfirst=True)
