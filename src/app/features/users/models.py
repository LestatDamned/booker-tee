from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base, utc_now

if TYPE_CHECKING:
    from app.features.workspaces.models import Workspace, WorkspaceMember


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), default="dev-login-disabled")
    name: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    owned_workspaces: Mapped[list[Workspace]] = relationship(
        back_populates="owner",
        foreign_keys="Workspace.owner_id",
    )
    memberships: Mapped[list[WorkspaceMember]] = relationship(
        back_populates="user",
        foreign_keys="WorkspaceMember.user_id",
    )
