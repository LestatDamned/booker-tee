from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base, utc_now
from app.features.workspaces.models import enum_values

if TYPE_CHECKING:
    from app.features.imports.models import UploadedDocument
    from app.features.ledger.models import MoneyEntry
    from app.features.workspaces.models import Workspace


class AccountType(StrEnum):
    CASH = "cash"
    CARD = "card"
    DEPOSIT = "deposit"
    CHECKING = "checking"
    OTHER = "other"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[AccountType] = mapped_column(
        Enum(AccountType, values_callable=enum_values, name="account_type"),
        default=AccountType.CARD,
    )
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    initial_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    bank_name: Mapped[str | None] = mapped_column(String(255))
    account_number_masked: Mapped[str | None] = mapped_column(String(64))
    account_number_fingerprint: Mapped[str | None] = mapped_column(String(128))
    card_last4: Mapped[str | None] = mapped_column(String(4))
    external_ref: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    workspace: Mapped[Workspace] = relationship(back_populates="accounts")
    uploaded_documents: Mapped[list[UploadedDocument]] = relationship(back_populates="account")
    money_entries: Mapped[list[MoneyEntry]] = relationship(back_populates="account")
