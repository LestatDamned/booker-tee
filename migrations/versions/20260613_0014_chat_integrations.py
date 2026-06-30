"""chat integrations

Revision ID: 20260613_0014
Revises: 20260613_0013
Create Date: 2026-06-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260613_0014"
down_revision: str | None = "20260613_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


chat_provider_code = postgresql.ENUM(
    "fake",
    "matrix",
    "telegram",
    name="chat_provider_code",
    create_type=False,
)
chat_conversation_type = postgresql.ENUM(
    "channel",
    "group",
    "private",
    "unknown",
    name="chat_conversation_type",
    create_type=False,
)
integration_connection_status = postgresql.ENUM(
    "active",
    "disabled",
    name="integration_connection_status",
    create_type=False,
)
chat_conversation_binding_mode = postgresql.ENUM(
    "personal_input",
    "review",
    "shared_feed",
    name="chat_conversation_binding_mode",
    create_type=False,
)
chat_notification_level = postgresql.ENUM(
    "none",
    "safe_activity",
    "review_alerts",
    name="chat_notification_level",
    create_type=False,
)
chat_conversation_flow = postgresql.ENUM(
    "main_menu",
    "link_account",
    "upload_document",
    "review",
    "record_expense",
    "record_income",
    "record_transfer",
    name="chat_conversation_flow",
    create_type=False,
)
integration_delivery_status = postgresql.ENUM(
    "pending",
    "sent",
    "failed",
    name="integration_delivery_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    chat_provider_code.create(bind, checkfirst=True)
    chat_conversation_type.create(bind, checkfirst=True)
    integration_connection_status.create(bind, checkfirst=True)
    chat_conversation_binding_mode.create(bind, checkfirst=True)
    chat_notification_level.create(bind, checkfirst=True)
    chat_conversation_flow.create(bind, checkfirst=True)
    integration_delivery_status.create(bind, checkfirst=True)

    op.create_table(
        "integration_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("provider", chat_provider_code, nullable=False),
        sa.Column("status", integration_connection_status, nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_integration_connections_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_integration_connections_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integration_connections")),
    )
    op.create_index(
        op.f("ix_integration_connections_workspace_id"),
        "integration_connections",
        ["workspace_id"],
    )
    op.create_index(
        "ix_integration_connections_workspace_provider",
        "integration_connections",
        ["workspace_id", "provider"],
    )

    op.create_table(
        "chat_conversation_bindings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("provider", chat_provider_code, nullable=False),
        sa.Column("external_chat_id", sa.String(length=128), nullable=False),
        sa.Column("conversation_type", chat_conversation_type, nullable=False),
        sa.Column("mode", chat_conversation_binding_mode, nullable=False),
        sa.Column("notification_level", chat_notification_level, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["integration_connections.id"],
            name=op.f("fk_chat_conversation_bindings_connection_id_integration_connections"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_chat_conversation_bindings_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_conversation_bindings")),
        sa.UniqueConstraint(
            "provider",
            "external_chat_id",
            name="uq_chat_conversation_bindings_provider_chat",
        ),
    )
    op.create_index(
        op.f("ix_chat_conversation_bindings_connection_id"),
        "chat_conversation_bindings",
        ["connection_id"],
    )
    op.create_index(
        op.f("ix_chat_conversation_bindings_workspace_id"),
        "chat_conversation_bindings",
        ["workspace_id"],
    )
    op.create_index(
        "ix_chat_conversation_bindings_workspace_mode",
        "chat_conversation_bindings",
        ["workspace_id", "mode"],
    )

    op.create_table(
        "chat_identity_bindings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=True),
        sa.Column("provider", chat_provider_code, nullable=False),
        sa.Column("external_user_id", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["integration_connections.id"],
            name=op.f("fk_chat_identity_bindings_connection_id_integration_connections"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_chat_identity_bindings_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_chat_identity_bindings_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_identity_bindings")),
        sa.UniqueConstraint(
            "workspace_id",
            "provider",
            "external_user_id",
            name="uq_chat_identity_bindings_workspace_provider_user",
        ),
    )
    op.create_index(
        op.f("ix_chat_identity_bindings_connection_id"),
        "chat_identity_bindings",
        ["connection_id"],
    )
    op.create_index(
        op.f("ix_chat_identity_bindings_user_id"),
        "chat_identity_bindings",
        ["user_id"],
    )
    op.create_index(
        op.f("ix_chat_identity_bindings_workspace_id"),
        "chat_identity_bindings",
        ["workspace_id"],
    )
    op.create_index(
        "ix_chat_identity_bindings_user_provider",
        "chat_identity_bindings",
        ["user_id", "provider"],
    )

    op.create_table(
        "chat_conversation_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("binding_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("flow", chat_conversation_flow, nullable=False),
        sa.Column("step", sa.String(length=64), nullable=False),
        sa.Column("action_token", sa.String(length=64), nullable=False),
        sa.Column("state_payload", postgresql.JSONB(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["binding_id"],
            ["chat_conversation_bindings.id"],
            name=op.f("fk_chat_conversation_states_binding_id_chat_conversation_bindings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_chat_conversation_states_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_chat_conversation_states_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_conversation_states")),
    )
    op.create_index(
        "ix_chat_conversation_states_action_token",
        "chat_conversation_states",
        ["action_token"],
        unique=True,
    )
    op.create_index(
        op.f("ix_chat_conversation_states_binding_id"),
        "chat_conversation_states",
        ["binding_id"],
    )
    op.create_index(
        "ix_chat_conversation_states_expires_at",
        "chat_conversation_states",
        ["expires_at"],
    )
    op.create_index(
        op.f("ix_chat_conversation_states_workspace_id"),
        "chat_conversation_states",
        ["workspace_id"],
    )
    op.create_index(
        "ix_chat_conversation_states_workspace_flow",
        "chat_conversation_states",
        ["workspace_id", "flow"],
    )

    op.create_table(
        "integration_event_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("binding_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("status", integration_delivery_status, nullable=False),
        sa.Column("error_message", sa.String(length=512), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["binding_id"],
            ["chat_conversation_bindings.id"],
            name=op.f("fk_integration_event_deliveries_binding_id_chat_conversation_bindings"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["integration_connections.id"],
            name=op.f("fk_integration_event_deliveries_connection_id_integration_connections"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_integration_event_deliveries_workspace_id_workspaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integration_event_deliveries")),
    )
    op.create_index(
        op.f("ix_integration_event_deliveries_binding_id"),
        "integration_event_deliveries",
        ["binding_id"],
    )
    op.create_index(
        op.f("ix_integration_event_deliveries_connection_id"),
        "integration_event_deliveries",
        ["connection_id"],
    )
    op.create_index(
        op.f("ix_integration_event_deliveries_workspace_id"),
        "integration_event_deliveries",
        ["workspace_id"],
    )
    op.create_index(
        "ix_integration_event_deliveries_idempotency",
        "integration_event_deliveries",
        ["workspace_id", "connection_id", "idempotency_key"],
        unique=True,
    )
    op.create_index(
        "ix_integration_event_deliveries_status",
        "integration_event_deliveries",
        ["workspace_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_integration_event_deliveries_status", table_name="integration_event_deliveries"
    )
    op.drop_index(
        "ix_integration_event_deliveries_idempotency",
        table_name="integration_event_deliveries",
    )
    op.drop_index(
        op.f("ix_integration_event_deliveries_workspace_id"),
        table_name="integration_event_deliveries",
    )
    op.drop_index(
        op.f("ix_integration_event_deliveries_connection_id"),
        table_name="integration_event_deliveries",
    )
    op.drop_index(
        op.f("ix_integration_event_deliveries_binding_id"),
        table_name="integration_event_deliveries",
    )
    op.drop_table("integration_event_deliveries")

    op.drop_index(
        "ix_chat_conversation_states_workspace_flow",
        table_name="chat_conversation_states",
    )
    op.drop_index(
        op.f("ix_chat_conversation_states_workspace_id"),
        table_name="chat_conversation_states",
    )
    op.drop_index("ix_chat_conversation_states_expires_at", table_name="chat_conversation_states")
    op.drop_index(
        op.f("ix_chat_conversation_states_binding_id"),
        table_name="chat_conversation_states",
    )
    op.drop_index("ix_chat_conversation_states_action_token", table_name="chat_conversation_states")
    op.drop_table("chat_conversation_states")

    op.drop_index("ix_chat_identity_bindings_user_provider", table_name="chat_identity_bindings")
    op.drop_index(
        op.f("ix_chat_identity_bindings_workspace_id"),
        table_name="chat_identity_bindings",
    )
    op.drop_index(op.f("ix_chat_identity_bindings_user_id"), table_name="chat_identity_bindings")
    op.drop_index(
        op.f("ix_chat_identity_bindings_connection_id"),
        table_name="chat_identity_bindings",
    )
    op.drop_table("chat_identity_bindings")

    op.drop_index(
        "ix_chat_conversation_bindings_workspace_mode",
        table_name="chat_conversation_bindings",
    )
    op.drop_index(
        op.f("ix_chat_conversation_bindings_workspace_id"),
        table_name="chat_conversation_bindings",
    )
    op.drop_index(
        op.f("ix_chat_conversation_bindings_connection_id"),
        table_name="chat_conversation_bindings",
    )
    op.drop_table("chat_conversation_bindings")

    op.drop_index(
        "ix_integration_connections_workspace_provider",
        table_name="integration_connections",
    )
    op.drop_index(
        op.f("ix_integration_connections_workspace_id"),
        table_name="integration_connections",
    )
    op.drop_table("integration_connections")

    bind = op.get_bind()
    integration_delivery_status.drop(bind, checkfirst=True)
    chat_conversation_flow.drop(bind, checkfirst=True)
    chat_notification_level.drop(bind, checkfirst=True)
    chat_conversation_binding_mode.drop(bind, checkfirst=True)
    integration_connection_status.drop(bind, checkfirst=True)
    chat_conversation_type.drop(bind, checkfirst=True)
    chat_provider_code.drop(bind, checkfirst=True)
