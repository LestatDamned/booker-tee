from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base, utc_now
from app.features.ledger.models import OperationType
from app.features.workspaces.models import enum_values

if TYPE_CHECKING:
    from app.features.accounts.models import Account
    from app.features.categories.models import Category
    from app.features.properties.models import Property
    from app.features.users.models import User
    from app.features.workspaces.models import Workspace


class TransactionRuleMatchType(StrEnum):
    CONTAINS = "contains"
    EXACT = "exact"


class MoneyDirection(StrEnum):
    INFLOW = "inflow"
    OUTFLOW = "outflow"
    ANY = "any"


class TransactionRuleApplicationMode(StrEnum):
    SUGGEST = "suggest"
    AUTO_APPLY = "auto_apply"


class TransactionRule(Base):
    __tablename__ = "transaction_rules"
    __table_args__ = (
        Index("ix_transaction_rules_workspace_active", "workspace_id", "is_active", "priority"),
        Index("ix_transaction_rules_workspace_category", "workspace_id", "category_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    match_type: Mapped[TransactionRuleMatchType] = mapped_column(
        Enum(
            TransactionRuleMatchType,
            values_callable=enum_values,
            name="transaction_rule_match_type",
        ),
        default=TransactionRuleMatchType.CONTAINS,
    )
    pattern: Mapped[str] = mapped_column(String(255))
    application_mode: Mapped[TransactionRuleApplicationMode] = mapped_column(
        Enum(
            TransactionRuleApplicationMode,
            values_callable=enum_values,
            name="transaction_rule_application_mode",
        ),
        default=TransactionRuleApplicationMode.SUGGEST,
    )
    account_id: Mapped[UUID | None] = mapped_column(ForeignKey("accounts.id"))
    amount_min: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    amount_max: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    direction: Mapped[MoneyDirection] = mapped_column(
        Enum(MoneyDirection, values_callable=enum_values, name="money_direction"),
        default=MoneyDirection.ANY,
    )
    target_operation_type: Mapped[OperationType | None] = mapped_column(
        Enum(OperationType, values_callable=enum_values, name="operation_type")
    )
    category_id: Mapped[UUID | None] = mapped_column(ForeignKey("categories.id"))
    property_id: Mapped[UUID | None] = mapped_column(ForeignKey("properties.id"))
    auto_description: Mapped[str | None] = mapped_column(Text)
    affects_profit: Mapped[bool | None] = mapped_column(Boolean)
    created_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    workspace: Mapped[Workspace] = relationship(back_populates="transaction_rules")
    account: Mapped[Account | None] = relationship()
    category: Mapped[Category | None] = relationship()
    property: Mapped[Property | None] = relationship()
    created_by_user: Mapped[User | None] = relationship()
