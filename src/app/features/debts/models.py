from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base, utc_now
from app.features.debts.domain import DebtKind
from app.features.workspaces.models import enum_values


class Debt(Base):
    __tablename__ = "debts"
    __table_args__ = (
        Index("ix_debts_workspace_kind", "workspace_id", "kind"),
        UniqueConstraint(
            "workspace_id",
            "creation_idempotency_key",
            name="uq_debts_workspace_creation_idempotency",
        ),
        CheckConstraint(
            "original_principal IS NULL OR original_principal > 0",
            name="original_principal_positive",
        ),
        CheckConstraint(
            "credit_limit IS NULL OR credit_limit > 0",
            name="credit_limit_positive",
        ),
        CheckConstraint(
            "opened_on IS NULL OR maturity_date IS NULL OR maturity_date >= opened_on",
            name="valid_dates",
        ),
        CheckConstraint(
            "(kind = 'credit_card' AND credit_limit IS NOT NULL) OR "
            "(kind <> 'credit_card' AND credit_limit IS NULL "
            "AND original_principal IS NOT NULL)",
            name="valid_terms_for_kind",
        ),
    )

    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
    )
    kind: Mapped[DebtKind] = mapped_column(
        Enum(DebtKind, values_callable=enum_values, name="debt_kind"),
    )
    opened_on: Mapped[date | None] = mapped_column(Date)
    original_principal: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    maturity_date: Mapped[date | None] = mapped_column(Date)
    credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    creation_idempotency_key: Mapped[UUID] = mapped_column(Uuid)
    creation_fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class DebtPayment(Base):
    __tablename__ = "debt_payments"
    __table_args__ = (
        Index(
            "ix_debt_payments_workspace_debt_created",
            "workspace_id",
            "debt_account_id",
            "created_at",
        ),
        UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name="uq_debt_payments_workspace_idempotency",
        ),
        UniqueConstraint(
            "principal_operation_id",
            name="uq_debt_payments_principal_operation",
        ),
        UniqueConstraint(
            "interest_operation_id",
            name="uq_debt_payments_interest_operation",
        ),
        CheckConstraint(
            "principal_operation_id IS NOT NULL OR interest_operation_id IS NOT NULL",
            name="has_operation",
        ),
        CheckConstraint(
            "principal_operation_id IS NULL OR interest_operation_id IS NULL "
            "OR principal_operation_id <> interest_operation_id",
            name="distinct_operations",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
    )
    debt_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("debts.account_id", ondelete="CASCADE"),
    )
    principal_operation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("operations.id", ondelete="RESTRICT"),
    )
    interest_operation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("operations.id", ondelete="RESTRICT"),
    )
    idempotency_key: Mapped[UUID] = mapped_column(Uuid)
    idempotency_fingerprint: Mapped[str] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
