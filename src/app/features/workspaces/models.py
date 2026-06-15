from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base, utc_now

if TYPE_CHECKING:
    from app.features.accounts.models import Account
    from app.features.categories.models import Category
    from app.features.imports.models import ParseAttempt, UploadedDocument
    from app.features.ledger.models import MoneyEntry, Operation
    from app.features.properties.models import Property
    from app.features.transaction_rules.models import TransactionRule
    from app.features.users.models import User


class WorkspaceType(StrEnum):
    PERSONAL = "personal"
    FAMILY = "family"
    BUSINESS = "business"
    PROPERTY_MANAGEMENT = "property_management"
    PROJECT = "project"
    OTHER = "other"


class WorkspaceRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
    UPLOADER = "uploader"
    ANALYST = "analyst"


class WorkspaceMemberStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    DISABLED = "disabled"
    REMOVED = "removed"


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
    accounts: Mapped[list[Account]] = relationship(back_populates="workspace")
    uploaded_documents: Mapped[list[UploadedDocument]] = relationship(back_populates="workspace")
    parse_attempts: Mapped[list[ParseAttempt]] = relationship(back_populates="workspace")
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
