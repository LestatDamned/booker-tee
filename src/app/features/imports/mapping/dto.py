from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from app.features.accounts.models import AccountType
from app.features.imports.models import (
    ParseAttempt,
    ParseAttemptStatus,
    RawTransaction,
    RawTransactionStatus,
    UploadedDocument,
    UploadedDocumentStatus,
)


@dataclass(frozen=True)
class ImportAccountRef:
    id: UUID
    name: str
    type: AccountType
    currency: str


@dataclass(frozen=True)
class ImportRawTransactionRow:
    row_index: int
    status: RawTransactionStatus
    parse_attempt_id: UUID
    display_date: date | str | None
    amount: Decimal | None
    amount_raw: str | None
    currency: str | None
    description: str
    normalization_error: str


@dataclass(frozen=True)
class ImportParseAttemptView:
    id: UUID
    status: ParseAttemptStatus
    parser_name: str
    parser_version: str | None
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None
    validation_report: dict[str, object] | None
    raw_tables: list[dict[str, object]] | None
    raw_text_by_page: list[str] | None

    @property
    def message(self) -> str:
        if self.error_message:
            return self.error_message
        if self.validation_report is None:
            return ""
        message = self.validation_report.get("message")
        return message if isinstance(message, str) else ""


@dataclass(frozen=True)
class ImportDocumentDetailView:
    id: UUID
    status: UploadedDocumentStatus
    original_filename: str
    sha256_hash: str
    storage_key: str
    bank_name: str | None
    statement_type: str | None
    account: ImportAccountRef | None
    validation: dict[str, object] | None
    raw_transactions: list[ImportRawTransactionRow]
    parse_attempts: list[ImportParseAttemptView]


class ImportViewMapper:
    @staticmethod
    def document_detail_from_uploaded_document(
        document: UploadedDocument,
    ) -> ImportDocumentDetailView:
        parse_attempts = sorted(
            document.parse_attempts,
            key=lambda attempt: attempt.started_at,
            reverse=True,
        )
        attempts = [ImportViewMapper.parse_attempt(attempt) for attempt in parse_attempts]
        latest_attempt = attempts[0] if attempts else None
        return ImportDocumentDetailView(
            id=document.id,
            status=document.status,
            original_filename=document.original_filename,
            sha256_hash=document.sha256_hash,
            storage_key=document.storage_key,
            bank_name=document.bank_name,
            statement_type=document.statement_type,
            account=ImportViewMapper.account_ref(document),
            validation=latest_attempt.validation_report if latest_attempt else None,
            raw_transactions=[
                ImportViewMapper.raw_transaction_row(row) for row in document.raw_transactions
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
            type=document.account.type,
            currency=document.account.currency,
        )

    @staticmethod
    def raw_transaction_row(row: RawTransaction) -> ImportRawTransactionRow:
        return ImportRawTransactionRow(
            row_index=row.row_index,
            status=row.status,
            parse_attempt_id=row.parse_attempt_id,
            display_date=row.operation_date or row.operation_date_raw,
            amount=row.amount,
            amount_raw=row.amount_raw,
            currency=row.currency,
            description=row.description_normalized or row.description_raw or "",
            normalization_error=row.normalization_error or "",
        )

    @staticmethod
    def parse_attempt(attempt: ParseAttempt) -> ImportParseAttemptView:
        return ImportParseAttemptView(
            id=attempt.id,
            status=attempt.status,
            parser_name=attempt.parser_name,
            parser_version=attempt.parser_version,
            started_at=attempt.started_at,
            finished_at=attempt.finished_at,
            error_message=attempt.error_message_sanitized,
            validation_report=attempt.validation_report_json,
            raw_tables=attempt.raw_tables_json,
            raw_text_by_page=attempt.raw_text_by_page_json,
        )
