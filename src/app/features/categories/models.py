from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base, utc_now
from app.features.workspaces.models import enum_values

if TYPE_CHECKING:
    from app.features.ledger.models import Operation
    from app.features.workspaces.models import Workspace


class CategoryKind(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    ADJUSTMENT = "adjustment"
    MIXED = "mixed"


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        Index("ix_categories_workspace_kind", "workspace_id", "kind"),
        Index("ix_categories_workspace_system_key", "workspace_id", "system_key", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("categories.id"))
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[CategoryKind] = mapped_column(
        Enum(CategoryKind, values_callable=enum_values, name="category_kind"),
        default=CategoryKind.MIXED,
    )
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    system_key: Mapped[str | None] = mapped_column(String(64))
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    workspace: Mapped[Workspace] = relationship(back_populates="categories")
    parent: Mapped[Category | None] = relationship(remote_side=lambda: [Category.id])
    operations: Mapped[list[Operation]] = relationship(back_populates="category")
