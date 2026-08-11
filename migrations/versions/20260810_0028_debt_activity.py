"""Add debt workspace activity event types.

Revision ID: 20260810_0028
Revises: 20260810_0027
Create Date: 2026-08-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260810_0028"
down_revision: str | None = "20260810_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_EVENT_TYPES = (
    "debt_created",
    "debt_payment_recorded",
    "debt_payment_undone",
    "debt_updated",
    "debt_archived",
    "debt_restored",
    "debt_deleted",
)


def upgrade() -> None:
    for event_type in NEW_EVENT_TYPES:
        op.execute(f"ALTER TYPE workspace_audit_event_type ADD VALUE IF NOT EXISTS '{event_type}'")


def downgrade() -> None:
    op.execute(
        "UPDATE workspace_audit_events SET event_type = 'workspace_updated' "
        "WHERE event_type IN ("
        "'debt_created', 'debt_payment_recorded', 'debt_payment_undone', "
        "'debt_updated', 'debt_archived', 'debt_restored', 'debt_deleted')"
    )
