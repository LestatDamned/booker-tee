"""Add document-upload workspace activity event type.

Revision ID: 20260810_0029
Revises: 20260810_0028
Create Date: 2026-08-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260810_0029"
down_revision: str | None = "20260810_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE workspace_audit_event_type ADD VALUE IF NOT EXISTS 'document_uploaded'")


def downgrade() -> None:
    op.execute(
        "UPDATE workspace_audit_events SET event_type = 'workspace_updated' "
        "WHERE event_type = 'document_uploaded'"
    )
