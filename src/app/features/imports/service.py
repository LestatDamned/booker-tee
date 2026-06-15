from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

from fastapi import UploadFile
from pdfplumber.utils.exceptions import PdfminerException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.db.base import utc_now
from app.features.accounts.repository import AccountRepository
from app.features.imports.extraction.pdfplumber_extractor import ExtractedPdf, PdfPlumberExtractor
from app.features.imports.models import (
    ParseAttempt,
    ParseAttemptStatus,
    RawTransaction,
    RawTransactionStatus,
    UploadedDocument,
    UploadedDocumentSource,
    UploadedDocumentStatus,
    UploadedDocumentType,
)
from app.features.imports.parser_types import RawTransactionDraft, StatementControlTotals
from app.features.imports.parsers.factory import default_statement_parser_registry
from app.features.imports.repository import ImportRepository
from app.features.imports.storage import UploadStorage
from app.features.imports.validation import (
    StatementValidationReport,
    StatementValidationStatus,
    validate_statement_totals,
)
from app.features.transaction_rules.service import TransactionRuleService
from app.features.workspaces.service import WorkspaceContext

PARSER_EXCEPTIONS = (OSError, ValueError, TypeError, PdfminerException)


class UploadValidationError(ValueError):
    pass


class RawTransactionReviewError(ValueError):
    pass


class ImportReparseError(ValueError):
    pass


class ImportDocumentManagementError(ValueError):
    pass


class RawTransactionDocument(Protocol):
    raw_transactions: list[RawTransaction]


class ImportService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.imports = ImportRepository(session)
        self.accounts = AccountRepository(session)
        self.storage = UploadStorage(settings.upload_storage_dir)
        self.extractor = PdfPlumberExtractor()
        self.parser_registry = default_statement_parser_registry()

    async def upload_and_extract_statement(
        self,
        *,
        context: WorkspaceContext,
        upload_file: UploadFile,
        account_id: UUID | None,
    ) -> UploadedDocument:
        validate_pdf_upload(upload_file)
        account = None
        if account_id is not None:
            account = await self.accounts.get_for_workspace(context.workspace.id, account_id)
            if account is None:
                raise UploadValidationError("Selected account is not available in this workspace.")

        document_id = uuid4()
        stored_upload = await self.storage.save_pdf(
            upload_file,
            workspace_id=context.workspace.id,
            document_id=document_id,
        )
        selected_currency = (
            account.currency if account is not None else context.workspace.default_currency
        )
        document = await self._create_document(
            context=context,
            document_id=document_id,
            upload_file=upload_file,
            stored_path=stored_upload.path,
            storage_key=stored_upload.storage_key,
            sha256_hash=stored_upload.sha256_hash,
            file_size_bytes=stored_upload.file_size_bytes,
            account_id=account.id if account is not None else None,
        )
        await self.session.commit()

        attempt = await self._create_running_attempt(context.workspace.id, document.id)
        await self.session.commit()

        try:
            extracted = self.extractor.extract(stored_upload.path)
        except PARSER_EXCEPTIONS as exc:
            await self._record_failed_attempt(document, attempt, exc)
        else:
            await self._record_successful_attempt(
                document,
                attempt,
                extracted,
                currency=selected_currency,
            )

        await self.session.commit()
        return document

    async def list_documents(self, workspace_id: UUID) -> list[UploadedDocument]:
        return await self.imports.list_documents_for_workspace(workspace_id)

    async def get_document(self, workspace_id: UUID, document_id: UUID) -> UploadedDocument | None:
        return await self.imports.get_document_for_workspace(workspace_id, document_id)

    async def reparse_document(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
    ) -> UploadedDocument:
        document = await self.imports.get_document_for_workspace(context.workspace.id, document_id)
        if document is None:
            raise ImportReparseError("Document was not found.")
        if any(row.status == RawTransactionStatus.CONFIRMED for row in document.raw_transactions):
            raise ImportReparseError("Documents with confirmed ledger rows cannot be reparsed.")

        selected_currency = context.workspace.default_currency
        if document.account_id is not None:
            account = await self.accounts.get_for_workspace(
                context.workspace.id, document.account_id
            )
            if account is not None:
                selected_currency = account.currency

        attempt = await self._create_running_attempt(context.workspace.id, document.id)
        await self.session.commit()
        try:
            extracted = self.extractor.extract(
                self.settings.upload_storage_dir / document.storage_key
            )
        except PARSER_EXCEPTIONS as exc:
            await self._record_failed_attempt(
                document,
                attempt,
                exc,
                document_status=UploadedDocumentStatus.REQUIRES_REVIEW,
            )
        else:
            await self._record_successful_attempt(
                document,
                attempt,
                extracted,
                currency=selected_currency,
                exclude_duplicate_document_id=document.id,
                supersede_existing_rows=True,
            )

        await self.session.commit()
        reparsed_document = await self.imports.get_document_for_workspace(
            context.workspace.id,
            document_id,
        )
        if reparsed_document is None:
            raise ImportReparseError("Document was not found after reparse.")
        return reparsed_document

    async def set_raw_transaction_review_status(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        raw_transaction_id: UUID,
        action: str,
    ) -> UploadedDocument:
        target_status = raw_transaction_status_for_review_action(action)
        raw_transaction = await self.imports.get_raw_transaction_for_workspace(
            workspace_id,
            document_id,
            raw_transaction_id,
        )
        if raw_transaction is None:
            raise RawTransactionReviewError("Raw transaction row was not found.")

        await self.imports.mark_raw_transaction_status(raw_transaction, target_status)
        document = await self.imports.get_document_for_workspace(workspace_id, document_id)
        if document is None:
            raise RawTransactionReviewError("Document was not found.")

        await self._refresh_document_validation(document)
        await self.session.commit()
        return document

    async def ignore_document(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
    ) -> UploadedDocument:
        document = await self.imports.get_document_for_workspace(workspace_id, document_id)
        if document is None:
            raise ImportDocumentManagementError("Документ не найден.")
        if document_has_linked_operations(document):
            raise ImportDocumentManagementError(
                "Нельзя игнорировать документ со связанными операциями."
            )
        for raw_transaction in document.raw_transactions:
            raw_transaction.status = RawTransactionStatus.IGNORED
        await self.imports.mark_document_status(document, UploadedDocumentStatus.IGNORED)
        await self.session.commit()
        return document

    async def delete_document(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
    ) -> None:
        document = await self.imports.get_document_for_workspace(workspace_id, document_id)
        if document is None:
            raise ImportDocumentManagementError("Документ не найден.")
        if document_has_linked_operations(document):
            raise ImportDocumentManagementError("Нельзя удалить документ со связанными операциями.")
        storage_path = self.settings.upload_storage_dir / document.storage_key
        await self.imports.delete_document(document)
        await self.session.commit()
        storage_path.unlink(missing_ok=True)

    async def _create_document(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
        upload_file: UploadFile,
        stored_path: Path,
        storage_key: str,
        sha256_hash: str,
        file_size_bytes: int,
        account_id: UUID | None,
    ) -> UploadedDocument:
        document = UploadedDocument(
            id=document_id,
            workspace_id=context.workspace.id,
            source=UploadedDocumentSource.WEB_UPLOAD,
            document_type=UploadedDocumentType.BANK_STATEMENT,
            status=UploadedDocumentStatus.UPLOADED,
            original_filename=upload_file.filename or stored_path.name,
            storage_key=storage_key,
            content_type=upload_file.content_type,
            file_size_bytes=file_size_bytes,
            sha256_hash=sha256_hash,
            uploaded_by_user_id=context.user.id,
            account_id=account_id,
        )
        return await self.imports.create_uploaded_document(document)

    async def _create_running_attempt(
        self,
        workspace_id: UUID,
        document_id: UUID,
    ) -> ParseAttempt:
        attempt = ParseAttempt(
            workspace_id=workspace_id,
            uploaded_document_id=document_id,
            parser_name="auto_statement_parser",
            parser_version=None,
        )
        return await self.imports.create_parse_attempt(attempt)

    async def _record_successful_attempt(
        self,
        document: UploadedDocument,
        attempt: ParseAttempt,
        extracted: ExtractedPdf,
        *,
        currency: str,
        exclude_duplicate_document_id: UUID | None = None,
        supersede_existing_rows: bool = False,
    ) -> None:
        parser = self.parser_registry.find_parser(extracted)
        attempt.finished_at = utc_now()
        if parser is not None:
            attempt.parser_name = parser.parser_name
            attempt.parser_version = parser.parser_version
            document.bank_name = parser.bank_code
            document.statement_type = parser.statement_type
        await self.imports.mark_attempt_success(
            attempt,
            raw_text_by_page_json=extracted.text_by_page,
            raw_tables_json=[
                {"page_number": page_tables.page_number, "tables": page_tables.tables}
                for page_tables in extracted.tables_by_page
            ],
            metadata=extracted.metadata,
        )
        if parser is None:
            await self.imports.mark_attempt_requires_review(
                attempt,
                message="No supported bank statement parser matched this document.",
            )
            await self.imports.mark_document_status(
                document, UploadedDocumentStatus.REQUIRES_REVIEW
            )
            return

        drafts = parser.extract_raw_transactions(
            extracted,
            account_id=document.account_id,
            currency=currency,
        )
        if not drafts:
            await self.imports.mark_attempt_requires_review(
                attempt,
                message="Parser matched the document but did not find transaction rows.",
            )
            await self.imports.mark_document_status(
                document, UploadedDocumentStatus.REQUIRES_REVIEW
            )
            return

        if supersede_existing_rows:
            await self.imports.mark_reviewable_raw_transactions_superseded(
                document,
                superseded_by_attempt_id=attempt.id,
            )

        raw_transactions = await self.imports.create_raw_transactions(
            [
                raw_transaction_from_draft(
                    draft,
                    workspace_id=document.workspace_id,
                    uploaded_document_id=document.id,
                    parse_attempt_id=attempt.id,
                )
                for draft in drafts
            ]
        )
        await self._mark_duplicate_candidates(
            document.workspace_id,
            raw_transactions,
            exclude_document_id=exclude_duplicate_document_id or document.id,
        )
        await TransactionRuleService(self.session).apply_rules_to_raw_transactions(
            workspace_id=document.workspace_id,
            raw_transactions=raw_transactions,
        )
        control_totals = parser.extract_control_totals(
            extracted,
            currency=currency,
        )
        report = validate_statement_totals(
            rows=raw_transactions,
            control_totals=control_totals,
        )
        await self._store_validation_result(
            document,
            attempt,
            control_totals=control_totals,
            report=report,
        )

    async def _record_failed_attempt(
        self,
        document: UploadedDocument,
        attempt: ParseAttempt,
        exc: OSError | ValueError | TypeError | PdfminerException,
        *,
        document_status: UploadedDocumentStatus = UploadedDocumentStatus.FAILED_TO_PARSE,
    ) -> None:
        attempt.finished_at = utc_now()
        await self.imports.mark_attempt_failed(
            attempt,
            error_code=type(exc).__name__,
            error_message=sanitize_error_message(exc),
        )
        await self.imports.mark_document_status(document, document_status)

    async def _mark_duplicate_candidates(
        self,
        workspace_id: UUID,
        raw_transactions: list[RawTransaction],
        *,
        exclude_document_id: UUID | None,
    ) -> None:
        exact_hashes = {
            raw_transaction.dedupe_hash
            for raw_transaction in raw_transactions
            if raw_transaction.dedupe_hash
        }
        existing_hashes = await self.imports.find_existing_dedupe_hashes(
            workspace_id=workspace_id,
            dedupe_hashes=exact_hashes,
            exclude_document_id=exclude_document_id,
        )
        fingerprints = possible_duplicate_fingerprints(raw_transactions)
        existing_fingerprints = await self.imports.find_existing_possible_duplicate_fingerprints(
            workspace_id=workspace_id,
            fingerprints=fingerprints,
            exclude_document_id=exclude_document_id,
        )
        for raw_transaction in raw_transactions:
            if raw_transaction.dedupe_hash in existing_hashes:
                mark_raw_transaction_duplicate(
                    raw_transaction,
                    RawTransactionStatus.DUPLICATE,
                    "Exact duplicate: another row has the same dedupe hash.",
                )
                continue
            fingerprint = possible_duplicate_fingerprint(raw_transaction)
            if fingerprint in existing_fingerprints:
                mark_raw_transaction_duplicate(
                    raw_transaction,
                    RawTransactionStatus.POSSIBLE_DUPLICATE,
                    "Possible duplicate: same account, date, amount, and currency.",
                )
        await self.session.flush()

    async def _refresh_document_validation(self, document: UploadedDocument) -> None:
        attempt = latest_parse_attempt(document)
        if attempt is None:
            return
        control_totals = statement_control_totals_from_json(attempt.control_totals_json)
        report = validate_statement_totals(
            rows=document.raw_transactions,
            control_totals=control_totals,
        )
        await self._store_validation_result(
            document,
            attempt,
            control_totals=control_totals,
            report=report,
        )

    async def _store_validation_result(
        self,
        document: UploadedDocument,
        attempt: ParseAttempt,
        *,
        control_totals: StatementControlTotals | None,
        report: StatementValidationReport,
    ) -> None:
        await self.imports.store_attempt_validation(
            attempt,
            control_totals=control_totals.as_json() if control_totals else None,
            validation_report=report.as_json(),
        )
        if report.status == StatementValidationStatus.VALID:
            await self.imports.mark_attempt_status(attempt, ParseAttemptStatus.SUCCESS)
            await self.imports.mark_document_status(document, UploadedDocumentStatus.PARSED)
            return

        await self.imports.mark_attempt_status(attempt, ParseAttemptStatus.REQUIRES_REVIEW)
        await self.imports.mark_document_status(document, UploadedDocumentStatus.REQUIRES_REVIEW)


def validate_pdf_upload(upload_file: UploadFile) -> None:
    filename = upload_file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise UploadValidationError("Only PDF statement files can be uploaded.")


def document_has_linked_operations(document: RawTransactionDocument) -> bool:
    return any(
        raw_transaction.linked_operation_id is not None
        for raw_transaction in document.raw_transactions
    )


def raw_transaction_status_for_review_action(action: str) -> RawTransactionStatus:
    action_map = {
        "ignore": RawTransactionStatus.IGNORED,
        "mark_unique": RawTransactionStatus.MATCHED,
        "needs_review": RawTransactionStatus.NEEDS_REVIEW,
    }
    try:
        return action_map[action]
    except KeyError as exc:
        raise RawTransactionReviewError(f"Unsupported review action: {action}") from exc


def possible_duplicate_fingerprints(
    raw_transactions: list[RawTransaction],
) -> set[tuple[UUID, date, Decimal, str]]:
    return {
        fingerprint
        for raw_transaction in raw_transactions
        if (fingerprint := possible_duplicate_fingerprint(raw_transaction)) is not None
    }


def possible_duplicate_fingerprint(
    raw_transaction: RawTransaction,
) -> tuple[UUID, date, Decimal, str] | None:
    if (
        raw_transaction.account_id is None
        or raw_transaction.operation_date is None
        or raw_transaction.amount is None
        or raw_transaction.currency is None
    ):
        return None
    return (
        raw_transaction.account_id,
        raw_transaction.operation_date,
        raw_transaction.amount,
        raw_transaction.currency,
    )


def mark_raw_transaction_duplicate(
    raw_transaction: RawTransaction,
    status: RawTransactionStatus,
    message: str,
) -> None:
    raw_transaction.status = status
    raw_transaction.normalization_error = append_review_message(
        raw_transaction.normalization_error,
        message,
    )


def append_review_message(existing: str | None, message: str) -> str:
    if not existing:
        return message
    if message in existing:
        return existing
    return f"{existing}; {message}"


def latest_parse_attempt(document: UploadedDocument) -> ParseAttempt | None:
    if not document.parse_attempts:
        return None
    return document.parse_attempts[0]


def statement_control_totals_from_json(
    payload: dict[str, object] | None,
) -> StatementControlTotals | None:
    if payload is None:
        return None
    currency = payload.get("currency")
    if not isinstance(currency, str):
        return None
    return StatementControlTotals(
        currency=currency,
        opening_balance=_decimal_from_json(payload.get("opening_balance")),
        closing_balance=_decimal_from_json(payload.get("closing_balance")),
        total_inflow=_decimal_from_json(payload.get("total_inflow")),
        total_outflow=_decimal_from_json(payload.get("total_outflow")),
    )


def _decimal_from_json(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, str):
        return Decimal(value)
    if isinstance(value, int):
        return Decimal(value)
    return None


def sanitize_error_message(exc: BaseException) -> str:
    message = str(exc).strip()
    if not message:
        return type(exc).__name__
    return f"{type(exc).__name__}: {message[:300]}"


def raw_transaction_from_draft(
    draft: RawTransactionDraft,
    *,
    workspace_id: UUID,
    uploaded_document_id: UUID,
    parse_attempt_id: UUID,
) -> RawTransaction:
    return RawTransaction(
        workspace_id=workspace_id,
        uploaded_document_id=uploaded_document_id,
        parse_attempt_id=parse_attempt_id,
        row_index=draft.row_index,
        status=draft.status,
        raw_payload=draft.raw_payload,
        operation_date_raw=draft.operation_date_raw,
        posting_date_raw=draft.posting_date_raw,
        description_raw=draft.description_raw,
        amount_raw=draft.amount_raw,
        currency_raw=draft.currency_raw,
        balance_after_raw=draft.balance_after_raw,
        account_hint_raw=draft.account_hint_raw,
        account_id=draft.account_id,
        operation_date=draft.operation_date,
        posting_date=draft.posting_date,
        description_normalized=draft.description_normalized,
        amount=draft.amount,
        currency=draft.currency,
        balance_after=draft.balance_after,
        dedupe_hash=draft.dedupe_hash,
        confidence_score=draft.confidence_score,
        normalization_error=draft.normalization_error,
    )
