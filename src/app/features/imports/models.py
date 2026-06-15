from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Date, DateTime, Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base, utc_now
from app.features.ledger.models import OperationType
from app.features.workspaces.models import enum_values

if TYPE_CHECKING:
    from app.features.accounts.models import Account
    from app.features.ledger.models import Operation
    from app.features.workspaces.models import Workspace


class UploadedDocumentSource(StrEnum):
    WEB_UPLOAD = "web_upload"
    SYSTEM = "system"


class UploadedDocumentType(StrEnum):
    BANK_STATEMENT = "bank_statement"
    OTHER = "other"


class UploadedDocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    PENDING_PARSE = "pending_parse"
    PARSING = "parsing"
    PARSED = "parsed"
    REQUIRES_REVIEW = "requires_review"
    FAILED_TO_PARSE = "failed_to_parse"
    IMPORTED = "imported"
    IGNORED = "ignored"


class ParseAttemptStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    REQUIRES_REVIEW = "requires_review"
    FAILED = "failed"


class RawTransactionStatus(StrEnum):
    EXTRACTED = "extracted"
    NORMALIZED = "normalized"
    SUGGESTED = "suggested"
    NEEDS_REVIEW = "needs_review"
    MATCHED = "matched"
    IGNORED = "ignored"
    DUPLICATE = "duplicate"
    POSSIBLE_DUPLICATE = "possible_duplicate"
    FAILED = "failed"
    CONFIRMED = "confirmed"


class UploadedDocument(Base):
    __tablename__ = "uploaded_documents"
    __table_args__ = (
        Index("ix_uploaded_documents_workspace_status", "workspace_id", "status"),
        Index("ix_uploaded_documents_workspace_hash", "workspace_id", "sha256_hash"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    source: Mapped[UploadedDocumentSource] = mapped_column(
        Enum(
            UploadedDocumentSource,
            values_callable=enum_values,
            name="uploaded_document_source",
        ),
        default=UploadedDocumentSource.WEB_UPLOAD,
    )
    document_type: Mapped[UploadedDocumentType] = mapped_column(
        Enum(
            UploadedDocumentType,
            values_callable=enum_values,
            name="uploaded_document_type",
        ),
        default=UploadedDocumentType.BANK_STATEMENT,
    )
    status: Mapped[UploadedDocumentStatus] = mapped_column(
        Enum(
            UploadedDocumentStatus,
            values_callable=enum_values,
            name="uploaded_document_status",
        ),
        default=UploadedDocumentStatus.UPLOADED,
    )
    original_filename: Mapped[str] = mapped_column(String(512))
    storage_key: Mapped[str] = mapped_column(String(1024), unique=True)
    content_type: Mapped[str | None] = mapped_column(String(255))
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    sha256_hash: Mapped[str] = mapped_column(String(64), index=True)
    uploaded_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    bank_name: Mapped[str | None] = mapped_column(String(255))
    statement_type: Mapped[str | None] = mapped_column(String(255))
    statement_period_start: Mapped[date | None] = mapped_column(Date)
    statement_period_end: Mapped[date | None] = mapped_column(Date)
    account_id: Mapped[UUID | None] = mapped_column(ForeignKey("accounts.id"))
    extra_metadata: Mapped[dict[str, object] | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    workspace: Mapped[Workspace] = relationship(back_populates="uploaded_documents")
    account: Mapped[Account | None] = relationship(back_populates="uploaded_documents")
    parse_attempts: Mapped[list[ParseAttempt]] = relationship(
        back_populates="uploaded_document",
        cascade="all, delete-orphan",
        order_by="ParseAttempt.created_at.desc()",
        passive_deletes=True,
    )
    raw_transactions: Mapped[list[RawTransaction]] = relationship(
        back_populates="uploaded_document",
        cascade="all, delete-orphan",
        order_by="RawTransaction.row_index",
        passive_deletes=True,
    )


class ParseAttempt(Base):
    __tablename__ = "parse_attempts"
    __table_args__ = (
        Index("ix_parse_attempts_workspace_document", "workspace_id", "uploaded_document_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    uploaded_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("uploaded_documents.id", ondelete="CASCADE"),
        index=True,
    )
    parser_name: Mapped[str] = mapped_column(String(255))
    parser_version: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[ParseAttemptStatus] = mapped_column(
        Enum(ParseAttemptStatus, values_callable=enum_values, name="parse_attempt_status"),
        default=ParseAttemptStatus.RUNNING,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(128))
    error_message_sanitized: Mapped[str | None] = mapped_column(Text)
    raw_text_by_page_json: Mapped[list[str] | None] = mapped_column(JSONB)
    raw_tables_json: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB)
    control_totals_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    validation_report_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    extra_metadata: Mapped[dict[str, object] | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    workspace: Mapped[Workspace] = relationship(back_populates="parse_attempts")
    uploaded_document: Mapped[UploadedDocument] = relationship(back_populates="parse_attempts")
    raw_transactions: Mapped[list[RawTransaction]] = relationship(
        back_populates="parse_attempt",
        cascade="all, delete-orphan",
        order_by="RawTransaction.row_index",
        passive_deletes=True,
    )


class RawTransaction(Base):
    __tablename__ = "raw_transactions"
    __table_args__ = (
        Index("ix_raw_transactions_workspace_document", "workspace_id", "uploaded_document_id"),
        Index("ix_raw_transactions_workspace_attempt", "workspace_id", "parse_attempt_id"),
        Index("ix_raw_transactions_workspace_status", "workspace_id", "status"),
        Index("ix_raw_transactions_workspace_dedupe_hash", "workspace_id", "dedupe_hash"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
    )
    uploaded_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("uploaded_documents.id", ondelete="CASCADE"),
        index=True,
    )
    parse_attempt_id: Mapped[UUID] = mapped_column(
        ForeignKey("parse_attempts.id", ondelete="CASCADE"),
        index=True,
    )
    row_index: Mapped[int] = mapped_column()
    status: Mapped[RawTransactionStatus] = mapped_column(
        Enum(RawTransactionStatus, values_callable=enum_values, name="raw_transaction_status"),
        default=RawTransactionStatus.EXTRACTED,
    )
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    operation_date_raw: Mapped[str | None] = mapped_column(String(64))
    posting_date_raw: Mapped[str | None] = mapped_column(String(64))
    description_raw: Mapped[str | None] = mapped_column(Text)
    amount_raw: Mapped[str | None] = mapped_column(String(128))
    currency_raw: Mapped[str | None] = mapped_column(String(16))
    balance_after_raw: Mapped[str | None] = mapped_column(String(128))
    account_hint_raw: Mapped[str | None] = mapped_column(Text)
    account_id: Mapped[UUID | None] = mapped_column(ForeignKey("accounts.id"))
    operation_date: Mapped[date | None] = mapped_column(Date)
    posting_date: Mapped[date | None] = mapped_column(Date)
    description_normalized: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    balance_after: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    dedupe_hash: Mapped[str | None] = mapped_column(String(64))
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    suggested_category_id: Mapped[UUID | None] = mapped_column(ForeignKey("categories.id"))
    suggested_property_id: Mapped[UUID | None] = mapped_column(ForeignKey("properties.id"))
    suggested_operation_type: Mapped[OperationType | None] = mapped_column(
        Enum(OperationType, values_callable=enum_values, name="operation_type")
    )
    suggested_by_rule_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("transaction_rules.id", ondelete="SET NULL")
    )
    linked_operation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("operations.id", ondelete="SET NULL")
    )
    normalization_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    uploaded_document: Mapped[UploadedDocument] = relationship(back_populates="raw_transactions")
    parse_attempt: Mapped[ParseAttempt] = relationship(back_populates="raw_transactions")
    account: Mapped[Account | None] = relationship()
    linked_operation: Mapped[Operation | None] = relationship(back_populates="raw_transactions")
