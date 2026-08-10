from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base, utc_now
from app.features.workspaces.domain.types import (
    WorkspaceAuditEventType,
    WorkspaceInvitationStatus,
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)

if TYPE_CHECKING:
    from app.features.accounts.models import Account
    from app.features.categories.models import Category
    from app.features.imports.models import (
        ImportMappingTemplate,
        ParseAttempt,
        UploadedDocument,
    )
    from app.features.ledger.models import MoneyEntry, Operation
    from app.features.properties.models import Property
    from app.features.transaction_rules.models import TransactionRule
    from app.features.users.models import User


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str | None] = mapped_column(String(255), unique=True)
    type: Mapped[WorkspaceType] = mapped_column(
        Enum(WorkspaceType, values_callable=enum_values, name="workspace_type"),
        default=WorkspaceType.PERSONAL,
    )
    default_currency: Mapped[str] = mapped_column(String(3), default="RUB")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    owner: Mapped[User] = relationship(
        back_populates="owned_workspaces",
        foreign_keys=[owner_id],
    )
    members: Mapped[list[WorkspaceMember]] = relationship(back_populates="workspace")
    invitations: Mapped[list[WorkspaceInvitation]] = relationship(back_populates="workspace")
    audit_events: Mapped[list[WorkspaceAuditEvent]] = relationship(back_populates="workspace")
    accounts: Mapped[list[Account]] = relationship(back_populates="workspace")
    uploaded_documents: Mapped[list[UploadedDocument]] = relationship(back_populates="workspace")
    parse_attempts: Mapped[list[ParseAttempt]] = relationship(back_populates="workspace")
    import_mapping_templates: Mapped[list[ImportMappingTemplate]] = relationship(
        back_populates="workspace"
    )
    operations: Mapped[list[Operation]] = relationship(back_populates="workspace")
    money_entries: Mapped[list[MoneyEntry]] = relationship(back_populates="workspace")
    categories: Mapped[list[Category]] = relationship(back_populates="workspace")
    properties: Mapped[list[Property]] = relationship(back_populates="workspace")
    transaction_rules: Mapped[list[TransactionRule]] = relationship(back_populates="workspace")


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_members_user"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[WorkspaceRole] = mapped_column(
        Enum(WorkspaceRole, values_callable=enum_values, name="workspace_role"),
        default=WorkspaceRole.OWNER,
    )
    status: Mapped[WorkspaceMemberStatus] = mapped_column(
        Enum(
            WorkspaceMemberStatus,
            values_callable=enum_values,
            name="workspace_member_status",
        ),
        default=WorkspaceMemberStatus.ACTIVE,
    )
    invited_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    workspace: Mapped[Workspace] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships", foreign_keys=[user_id])


class WorkspaceInvitation(Base):
    __tablename__ = "workspace_invitations"
    __table_args__ = (
        Index("ix_workspace_invitations_token_hash", "token_hash", unique=True),
        Index("ix_workspace_invitations_workspace_status", "workspace_id", "status"),
        Index(
            "ix_workspace_invitations_workspace_email_status",
            "workspace_id",
            "invitee_email",
            "status",
        ),
        Index("ix_workspace_invitations_expires_at", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    invitee_email: Mapped[str | None] = mapped_column(String(320))
    role: Mapped[WorkspaceRole] = mapped_column(
        Enum(WorkspaceRole, values_callable=enum_values, name="workspace_role"),
        default=WorkspaceRole.VIEWER,
    )
    status: Mapped[WorkspaceInvitationStatus] = mapped_column(
        Enum(
            WorkspaceInvitationStatus,
            values_callable=enum_values,
            name="workspace_invitation_status",
        ),
        default=WorkspaceInvitationStatus.PENDING,
    )
    token_hash: Mapped[str] = mapped_column(String(64))
    invited_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    accepted_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    workspace: Mapped[Workspace] = relationship(back_populates="invitations")
    invited_by: Mapped[User] = relationship(foreign_keys=[invited_by_user_id])
    accepted_by: Mapped[User | None] = relationship(foreign_keys=[accepted_by_user_id])


class WorkspaceAuditEvent(Base):
    __tablename__ = "workspace_audit_events"
    __table_args__ = (
        Index(
            "ix_workspace_audit_events_workspace_created",
            "workspace_id",
            "created_at",
            "id",
        ),
        Index("ix_workspace_audit_events_actor_created", "actor_user_id", "created_at"),
        Index("ix_workspace_audit_events_event_type", "event_type"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    event_type: Mapped[WorkspaceAuditEventType] = mapped_column(
        Enum(
            WorkspaceAuditEventType,
            values_callable=enum_values,
            name="workspace_audit_event_type",
        )
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    target_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[UUID | None] = mapped_column(Uuid)
    details: Mapped[dict[str, str] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    workspace: Mapped[Workspace] = relationship(back_populates="audit_events")
    actor: Mapped[User | None] = relationship(foreign_keys=[actor_user_id])
    target_user: Mapped[User | None] = relationship(foreign_keys=[target_user_id])
