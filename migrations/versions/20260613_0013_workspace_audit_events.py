"""workspace audit events

Revision ID: 20260613_0013
Revises: 20260613_0012
Create Date: 2026-06-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260613_0013"
down_revision: str | None = "20260613_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


workspace_audit_event_type = sa.Enum(
    "workspace_created",
    "workspace_updated",
    "invitation_created",
    "invitation_accepted",
    "invitation_revoked",
    "member_role_changed",
    "member_disabled",
    "member_reactivated",
    name="workspace_audit_event_type",
)


def upgrade() -> None:
    op.create_table(
        "workspace_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", workspace_audit_event_type, nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("target_user_id", sa.Uuid(), nullable=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_workspace_audit_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["target_user_id"],
            ["users.id"],
            name=op.f("fk_workspace_audit_events_target_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_workspace_audit_events_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_audit_events")),
    )
    op.create_index(
        op.f("ix_workspace_audit_events_workspace_id"),
        "workspace_audit_events",
        ["workspace_id"],
    )
    op.create_index(
        "ix_workspace_audit_events_workspace_created",
        "workspace_audit_events",
        ["workspace_id", "created_at"],
    )
    op.create_index(
        "ix_workspace_audit_events_actor_created",
        "workspace_audit_events",
        ["actor_user_id", "created_at"],
    )
    op.create_index(
        "ix_workspace_audit_events_event_type",
        "workspace_audit_events",
        ["event_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_workspace_audit_events_event_type", table_name="workspace_audit_events")
    op.drop_index("ix_workspace_audit_events_actor_created", table_name="workspace_audit_events")
    op.drop_index(
        "ix_workspace_audit_events_workspace_created",
        table_name="workspace_audit_events",
    )
    op.drop_index(
        op.f("ix_workspace_audit_events_workspace_id"),
        table_name="workspace_audit_events",
    )
    op.drop_table("workspace_audit_events")

    bind = op.get_bind()
    workspace_audit_event_type.drop(bind, checkfirst=True)
