from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base, utc_now
from app.features.chat_integrations.schemas import ChatConversationType, ChatProviderCode
from app.features.workspaces.models import enum_values


class IntegrationConnectionStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class ChatConversationBindingMode(StrEnum):
    PERSONAL_INPUT = "personal_input"
    REVIEW = "review"
    SHARED_FEED = "shared_feed"


class ChatNotificationLevel(StrEnum):
    NONE = "none"
    SAFE_ACTIVITY = "safe_activity"
    REVIEW_ALERTS = "review_alerts"


class ChatConversationFlow(StrEnum):
    MAIN_MENU = "main_menu"
    LINK_ACCOUNT = "link_account"
    UPLOAD_DOCUMENT = "upload_document"
    REVIEW = "review"
    RECORD_EXPENSE = "record_expense"
    RECORD_INCOME = "record_income"
    RECORD_TRANSFER = "record_transfer"


class IntegrationDeliveryStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class IntegrationConnection(Base):
    __tablename__ = "integration_connections"
    __table_args__ = (
        Index("ix_integration_connections_workspace_provider", "workspace_id", "provider"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    provider: Mapped[ChatProviderCode] = mapped_column(
        Enum(ChatProviderCode, values_callable=enum_values, name="chat_provider_code")
    )
    status: Mapped[IntegrationConnectionStatus] = mapped_column(
        Enum(
            IntegrationConnectionStatus,
            values_callable=enum_values,
            name="integration_connection_status",
        ),
        default=IntegrationConnectionStatus.ACTIVE,
    )
    display_name: Mapped[str | None] = mapped_column(String(255))
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class ChatConversationBinding(Base):
    __tablename__ = "chat_conversation_bindings"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "external_chat_id",
            name="uq_chat_conversation_bindings_provider_chat",
        ),
        Index(
            "ix_chat_conversation_bindings_workspace_mode",
            "workspace_id",
            "mode",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="CASCADE"),
        index=True,
    )
    provider: Mapped[ChatProviderCode] = mapped_column(
        Enum(ChatProviderCode, values_callable=enum_values, name="chat_provider_code")
    )
    external_chat_id: Mapped[str] = mapped_column(String(128))
    conversation_type: Mapped[ChatConversationType] = mapped_column(
        Enum(
            ChatConversationType,
            values_callable=enum_values,
            name="chat_conversation_type",
        )
    )
    mode: Mapped[ChatConversationBindingMode] = mapped_column(
        Enum(
            ChatConversationBindingMode,
            values_callable=enum_values,
            name="chat_conversation_binding_mode",
        ),
        default=ChatConversationBindingMode.PERSONAL_INPUT,
    )
    notification_level: Mapped[ChatNotificationLevel] = mapped_column(
        Enum(
            ChatNotificationLevel,
            values_callable=enum_values,
            name="chat_notification_level",
        ),
        default=ChatNotificationLevel.NONE,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class ChatIdentityBinding(Base):
    __tablename__ = "chat_identity_bindings"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "provider",
            "external_user_id",
            name="uq_chat_identity_bindings_workspace_provider_user",
        ),
        Index("ix_chat_identity_bindings_user_provider", "user_id", "provider"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    connection_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="SET NULL"),
        index=True,
    )
    provider: Mapped[ChatProviderCode] = mapped_column(
        Enum(ChatProviderCode, values_callable=enum_values, name="chat_provider_code")
    )
    external_user_id: Mapped[str] = mapped_column(String(128))
    display_name: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class ChatConversationState(Base):
    __tablename__ = "chat_conversation_states"
    __table_args__ = (
        Index("ix_chat_conversation_states_workspace_flow", "workspace_id", "flow"),
        Index("ix_chat_conversation_states_action_token", "action_token", unique=True),
        Index("ix_chat_conversation_states_expires_at", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    binding_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chat_conversation_bindings.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    flow: Mapped[ChatConversationFlow] = mapped_column(
        Enum(ChatConversationFlow, values_callable=enum_values, name="chat_conversation_flow")
    )
    step: Mapped[str] = mapped_column(String(64))
    action_token: Mapped[str] = mapped_column(String(64))
    state_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class IntegrationEventDelivery(Base):
    __tablename__ = "integration_event_deliveries"
    __table_args__ = (
        Index(
            "ix_integration_event_deliveries_idempotency",
            "workspace_id",
            "connection_id",
            "idempotency_key",
            unique=True,
        ),
        Index("ix_integration_event_deliveries_status", "workspace_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="CASCADE"),
        index=True,
    )
    binding_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chat_conversation_bindings.id", ondelete="SET NULL"),
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(128))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    status: Mapped[IntegrationDeliveryStatus] = mapped_column(
        Enum(
            IntegrationDeliveryStatus,
            values_callable=enum_values,
            name="integration_delivery_status",
        ),
        default=IntegrationDeliveryStatus.PENDING,
    )
    error_message: Mapped[str | None] = mapped_column(String(512))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
