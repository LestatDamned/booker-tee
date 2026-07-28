from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from app.features.imports.domain.types import RawTransactionStatus, UploadedDocumentStatus
from app.features.imports.models import (
    ParseAttempt,
    ParseAttemptStatus,
    RawTransaction,
    UploadedDocument,
)


@dataclass(frozen=True)
class ImportAccountRef:
    id: UUID
    name: str
    currency: str


@dataclass(frozen=True)
class ImportRawTransactionRow:
    row_index: int
    status: RawTransactionStatus
    display_date: date | str | None
    amount: Decimal | None
    amount_raw: str | None
    currency: str | None
    description: str
    normalization_error: str
    linked_operation_id: UUID | None = None


@dataclass(frozen=True)
class ImportParseAttemptSnapshot:
    id: UUID
    status: ParseAttemptStatus
    parser_name: str
    parser_version: str | None
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None
    validation_report: dict[str, object] | None
    raw_tables: list[dict[str, object]] | None

    @property
    def message(self) -> str:
        if self.error_message:
            return self.error_message
        if self.validation_report is None:
            return ""
        message = self.validation_report.get("message")
        return message if isinstance(message, str) else ""


@dataclass(frozen=True)
class ImportDocumentSnapshot:
    id: UUID
    status: UploadedDocumentStatus
    original_filename: str
    bank_name: str | None
    statement_type: str | None
    account: ImportAccountRef | None
    validation: dict[str, object] | None
    raw_transactions: list[ImportRawTransactionRow]
    parse_attempts: list[ImportParseAttemptSnapshot]
    statement_period_start: date | None = None
    statement_period_end: date | None = None
    file_size_bytes: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ImportDocumentSnapshotMapper:
    @staticmethod
    def from_uploaded_document(
        document: UploadedDocument,
    ) -> ImportDocumentSnapshot:
        parse_attempts = sorted(
            document.parse_attempts,
            key=lambda attempt: attempt.started_at,
            reverse=True,
        )
        attempts = [
            ImportDocumentSnapshotMapper.parse_attempt(attempt) for attempt in parse_attempts
        ]
        latest_attempt = attempts[0] if attempts else None
        return ImportDocumentSnapshot(
            id=document.id,
            status=document.status,
            original_filename=document.original_filename,
            bank_name=document.bank_name,
            statement_type=document.statement_type,
            statement_period_start=document.statement_period_start,
            statement_period_end=document.statement_period_end,
            file_size_bytes=document.file_size_bytes,
            created_at=document.created_at,
            updated_at=document.updated_at,
            account=ImportDocumentSnapshotMapper.account_ref(document),
            validation=latest_attempt.validation_report if latest_attempt else None,
            raw_transactions=[
                ImportDocumentSnapshotMapper.raw_transaction_row(row)
                for row in document.raw_transactions
            ],
            parse_attempts=attempts,
        )

    @staticmethod
    def account_ref(document: UploadedDocument) -> ImportAccountRef | None:
        if document.account is None:
            return None
        return ImportAccountRef(
            id=document.account.id,
            name=document.account.name,
            currency=document.account.currency,
        )

    @staticmethod
    def raw_transaction_row(row: RawTransaction) -> ImportRawTransactionRow:
        return ImportRawTransactionRow(
            row_index=row.row_index,
            status=row.status,
            display_date=row.operation_date or row.operation_date_raw,
            amount=row.amount,
            amount_raw=row.amount_raw,
            currency=row.currency,
            description=row.description_normalized or row.description_raw or "",
            normalization_error=row.normalization_error or "",
            linked_operation_id=row.linked_operation_id,
        )

    @staticmethod
    def parse_attempt(attempt: ParseAttempt) -> ImportParseAttemptSnapshot:
        return ImportParseAttemptSnapshot(
            id=attempt.id,
            status=attempt.status,
            parser_name=attempt.parser_name,
            parser_version=attempt.parser_version,
            started_at=attempt.started_at,
            finished_at=attempt.finished_at,
            error_message=attempt.error_message_sanitized,
            validation_report=attempt.validation_report_json,
            raw_tables=attempt.raw_tables_json,
        )
