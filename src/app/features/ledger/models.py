from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base, utc_now
from app.features.workspaces.models import enum_values

if TYPE_CHECKING:
    from app.features.accounts.models import Account
    from app.features.categories.models import Category
    from app.features.imports.models import RawTransaction
    from app.features.properties.models import Property
    from app.features.users.models import User
    from app.features.workspaces.models import Workspace


class OperationType(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    ADJUSTMENT = "adjustment"


class OperationStatus(StrEnum):
    DRAFT = "draft"
    NEEDS_REVIEW = "needs_review"
    CONFIRMED = "confirmed"
    IGNORED = "ignored"
    DUPLICATE = "duplicate"


class OperationSource(StrEnum):
    MANUAL = "manual"
    BANK_PDF = "bank_pdf"
    SYSTEM = "system"


class Operation(Base):
    __tablename__ = "operations"
    __table_args__ = (
        Index("ix_operations_workspace_date", "workspace_id", "operation_date"),
        Index("ix_operations_workspace_status", "workspace_id", "status"),
        Index("ix_operations_workspace_category", "workspace_id", "category_id"),
        Index("ix_operations_workspace_property", "workspace_id", "property_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    type: Mapped[OperationType] = mapped_column(
        Enum(OperationType, values_callable=enum_values, name="operation_type"),
    )
    status: Mapped[OperationStatus] = mapped_column(
        Enum(OperationStatus, values_callable=enum_values, name="operation_status"),
        default=OperationStatus.DRAFT,
    )
    affects_profit: Mapped[bool] = mapped_column(Boolean, default=True)
    category_id: Mapped[UUID | None] = mapped_column(ForeignKey("categories.id"))
    property_id: Mapped[UUID | None] = mapped_column(ForeignKey("properties.id"))
    description: Mapped[str | None] = mapped_column(Text)
    operation_date: Mapped[date] = mapped_column(Date)
    posting_date: Mapped[date | None] = mapped_column(Date)
    source: Mapped[OperationSource] = mapped_column(
        Enum(OperationSource, values_callable=enum_values, name="operation_source"),
        default=OperationSource.MANUAL,
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    external_id: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    extra_metadata: Mapped[dict[str, object] | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    workspace: Mapped[Workspace] = relationship(back_populates="operations")
    created_by_user: Mapped[User | None] = relationship(foreign_keys=[created_by_user_id])
    updated_by_user: Mapped[User | None] = relationship(foreign_keys=[updated_by_user_id])
    category: Mapped[Category | None] = relationship(back_populates="operations")
    property: Mapped[Property | None] = relationship(back_populates="operations")
    money_entries: Mapped[list[MoneyEntry]] = relationship(
        back_populates="operation",
        cascade="all, delete-orphan",
        order_by="MoneyEntry.entry_order",
    )
    raw_transactions: Mapped[list[RawTransaction]] = relationship(back_populates="linked_operation")


class MoneyEntry(Base):
    __tablename__ = "money_entries"
    __table_args__ = (
        Index("ix_money_entries_workspace_account", "workspace_id", "account_id"),
        Index("ix_money_entries_workspace_operation", "workspace_id", "operation_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    operation_id: Mapped[UUID] = mapped_column(
        ForeignKey("operations.id", ondelete="CASCADE"),
        index=True,
    )
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    entry_order: Mapped[int] = mapped_column(default=1)
    balance_after: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    extra_metadata: Mapped[dict[str, object] | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    workspace: Mapped[Workspace] = relationship(back_populates="money_entries")
    operation: Mapped[Operation] = relationship(back_populates="money_entries")
    account: Mapped[Account] = relationship(back_populates="money_entries")
