"""Bind workspace invitations to an email address.

Revision ID: 20260810_0024
Revises: 20260808_0023
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0024"
down_revision: str | None = "20260808_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workspace_invitations",
        sa.Column("invitee_email", sa.String(length=320), nullable=True),
    )
    op.create_index(
        "ix_workspace_invitations_workspace_email_status",
        "workspace_invitations",
        ["workspace_id", "invitee_email", "status"],
    )
    op.execute(
        sa.text(
            "UPDATE workspace_invitations "
            "SET status = 'revoked', revoked_at = CURRENT_TIMESTAMP, "
            "updated_at = CURRENT_TIMESTAMP "
            "WHERE status = 'pending' AND invitee_email IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workspace_invitations_workspace_email_status",
        table_name="workspace_invitations",
    )
    op.drop_column("workspace_invitations", "invitee_email")
