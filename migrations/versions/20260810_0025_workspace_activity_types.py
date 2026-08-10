"""Add explicit workspace activity event types and keyset index.

Revision ID: 20260810_0025
Revises: 20260810_0024
Create Date: 2026-08-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260810_0025"
down_revision: str | None = "20260810_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_EVENT_TYPES = (
    "workspace_deactivated",
    "workspace_restored",
    "ownership_transferred",
    "member_left",
)


def upgrade() -> None:
    for event_type in NEW_EVENT_TYPES:
        op.execute(f"ALTER TYPE workspace_audit_event_type ADD VALUE IF NOT EXISTS '{event_type}'")
    op.drop_index(
        "ix_workspace_audit_events_workspace_created",
        table_name="workspace_audit_events",
    )
    op.create_index(
        "ix_workspace_audit_events_workspace_created",
        "workspace_audit_events",
        ["workspace_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workspace_audit_events_workspace_created",
        table_name="workspace_audit_events",
    )
    op.create_index(
        "ix_workspace_audit_events_workspace_created",
        "workspace_audit_events",
        ["workspace_id", "created_at"],
    )
    op.execute(
        "UPDATE workspace_audit_events SET event_type = 'workspace_updated' "
        "WHERE event_type IN ('workspace_deactivated', 'workspace_restored', "
        "'ownership_transferred')"
    )
    op.execute(
        "UPDATE workspace_audit_events SET event_type = 'member_disabled' "
        "WHERE event_type = 'member_left'"
    )
