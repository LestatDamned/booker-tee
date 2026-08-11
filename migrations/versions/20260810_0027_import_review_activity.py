"""Add import-review workspace activity event types.

Revision ID: 20260810_0027
Revises: 20260810_0026
Create Date: 2026-08-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260810_0027"
down_revision: str | None = "20260810_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_EVENT_TYPES = (
    "import_review_item_confirmed",
    "import_review_transfer_created",
    "import_review_operation_linked",
    "import_review_posting_undone",
    "import_review_operation_unlinked",
    "imported_operation_updated",
)


def upgrade() -> None:
    for event_type in NEW_EVENT_TYPES:
        op.execute(f"ALTER TYPE workspace_audit_event_type ADD VALUE IF NOT EXISTS '{event_type}'")


def downgrade() -> None:
    op.execute(
        "UPDATE workspace_audit_events SET event_type = 'workspace_updated' "
        "WHERE event_type IN ("
        "'import_review_item_confirmed', 'import_review_transfer_created', "
        "'import_review_operation_linked', 'import_review_posting_undone', "
        "'import_review_operation_unlinked', 'imported_operation_updated')"
    )
