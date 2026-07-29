"""Persistence reads owned by the imported document capability."""

from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.accounts.models import Account
from app.features.imports.documents.dto import (
    ImportDocumentAccountDto,
    ImportDocumentListFilters,
    ImportDocumentListPagination,
    ImportDocumentListRow,
    ImportDocumentListSort,
    ImportDocumentListState,
    ImportDocumentListSummaryDto,
    ImportDocumentSnapshot,
    ImportParseAttemptSnapshot,
    ImportRawTransactionRow,
)
from app.features.imports.documents.types import ParseAttemptStatus, UploadedDocumentStatus
from app.features.imports.documents.validation_report import StoredValidationReport
from app.features.imports.models import (
    ParseAttempt,
    RawTransaction,
    UploadedDocument,
)
from app.features.imports.statements.types import RawTransactionStatus

DOCUMENT_ATTENTION_ROW_STATUSES = {
    RawTransactionStatus.NORMALIZED,
    RawTransactionStatus.SUGGESTED,
    RawTransactionStatus.NEEDS_REVIEW,
    RawTransactionStatus.MATCHED,
    RawTransactionStatus.POSSIBLE_DUPLICATE,
    RawTransactionStatus.FAILED,
}

ATTENTION_DOCUMENT_STATUSES = {
    UploadedDocumentStatus.PARSED,
    UploadedDocumentStatus.REQUIRES_REVIEW,
    UploadedDocumentStatus.FAILED_TO_PARSE,
}
PROCESSING_DOCUMENT_STATUSES = {
    UploadedDocumentStatus.UPLOADED,
    UploadedDocumentStatus.PENDING_PARSE,
    UploadedDocumentStatus.PARSING,
}
COMPLETED_DOCUMENT_STATUSES = {
    UploadedDocumentStatus.IMPORTED,
    UploadedDocumentStatus.IGNORED,
}


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_uploaded_document(
        self,
        document: UploadedDocument,
    ) -> UploadedDocument:
        self.session.add(document)
        await self.session.flush()
        return document

    async def create_parse_attempt(self, attempt: ParseAttempt) -> ParseAttempt:
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    async def get_document_for_workspace(
        self,
        workspace_id: UUID,
        document_id: UUID,
    ) -> UploadedDocument | None:
        result = await self.session.execute(
            select(UploadedDocument)
            .options(
                selectinload(UploadedDocument.account),
                selectinload(UploadedDocument.parse_attempts),
                selectinload(UploadedDocument.raw_transactions),
                selectinload(UploadedDocument.raw_transactions).selectinload(
                    RawTransaction.account
                ),
            )
            .where(
                UploadedDocument.id == document_id,
                UploadedDocument.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_document_snapshot(
        self,
        workspace_id: UUID,
        document_id: UUID,
    ) -> ImportDocumentSnapshot | None:
        document = await self.get_document_for_workspace(workspace_id, document_id)
        if document is None:
            return None
        return _document_snapshot(document)

    async def get_document_for_workspace_for_update(
        self,
        workspace_id: UUID,
        document_id: UUID,
    ) -> UploadedDocument | None:
        result = await self.session.execute(
            select(UploadedDocument)
            .options(
                selectinload(UploadedDocument.parse_attempts),
                selectinload(UploadedDocument.raw_transactions),
            )
            .where(
                UploadedDocument.id == document_id,
                UploadedDocument.workspace_id == workspace_id,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def list_documents_for_workspace(self, workspace_id: UUID) -> list[UploadedDocument]:
        result = await self.session.execute(
            select(UploadedDocument)
            .where(UploadedDocument.workspace_id == workspace_id)
            .order_by(UploadedDocument.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_document_rows_for_workspace(
        self,
        *,
        workspace_id: UUID,
        filters: ImportDocumentListFilters,
        pagination: ImportDocumentListPagination,
    ) -> list[ImportDocumentListRow]:
        raw_counts = (
            select(
                RawTransaction.uploaded_document_id.label("document_id"),
                func.count(RawTransaction.id).label("total_row_count"),
                func.count(RawTransaction.id)
                .filter(RawTransaction.status.in_(DOCUMENT_ATTENTION_ROW_STATUSES))
                .label("reviewable_row_count"),
            )
            .where(RawTransaction.workspace_id == workspace_id)
            .group_by(RawTransaction.uploaded_document_id)
            .subquery()
        )
        latest_attempt_status = (
            select(ParseAttempt.status)
            .where(
                ParseAttempt.workspace_id == workspace_id,
                ParseAttempt.uploaded_document_id == UploadedDocument.id,
            )
            .order_by(ParseAttempt.created_at.desc(), ParseAttempt.id.desc())
            .limit(1)
            .correlate(UploadedDocument)
            .scalar_subquery()
        )
        query = (
            select(
                UploadedDocument.id.label("id"),
                UploadedDocument.original_filename.label("filename"),
                UploadedDocument.status.label("status"),
                UploadedDocument.created_at.label("created_at"),
                UploadedDocument.file_size_bytes.label("file_size_bytes"),
                UploadedDocument.bank_name.label("detected_bank_name"),
                UploadedDocument.statement_period_start.label("statement_period_start"),
                UploadedDocument.statement_period_end.label("statement_period_end"),
                Account.id.label("account_id"),
                Account.name.label("account_name"),
                Account.currency.label("account_currency"),
                Account.bank_name.label("account_bank_name"),
                func.coalesce(raw_counts.c.total_row_count, 0).label("total_row_count"),
                func.coalesce(raw_counts.c.reviewable_row_count, 0).label("reviewable_row_count"),
                latest_attempt_status.label("latest_parse_attempt_status"),
            )
            .outerjoin(
                Account,
                and_(
                    Account.id == UploadedDocument.account_id,
                    Account.workspace_id == workspace_id,
                ),
            )
            .outerjoin(
                raw_counts,
                raw_counts.c.document_id == UploadedDocument.id,
            )
            .where(UploadedDocument.workspace_id == workspace_id)
        )
        query = self._apply_document_list_filters(query, filters)
        if filters.sort is ImportDocumentListSort.CREATED_AT_ASC:
            query = query.order_by(
                UploadedDocument.created_at.asc(),
                UploadedDocument.id.asc(),
            )
        else:
            query = query.order_by(
                UploadedDocument.created_at.desc(),
                UploadedDocument.id.desc(),
            )
        result = await self.session.execute(
            query.offset(pagination.offset).limit(pagination.per_page)
        )
        return [ImportDocumentListRow.model_validate(row) for row in result.mappings().all()]

    async def count_document_rows_for_workspace(
        self,
        *,
        workspace_id: UUID,
        filters: ImportDocumentListFilters,
    ) -> int:
        query = (
            select(func.count())
            .select_from(UploadedDocument)
            .where(UploadedDocument.workspace_id == workspace_id)
        )
        query = self._apply_document_list_filters(query, filters)
        result = await self.session.execute(query)
        return result.scalar_one()

    async def list_document_filter_accounts_for_workspace(
        self,
        workspace_id: UUID,
    ) -> list[ImportDocumentAccountDto]:
        result = await self.session.execute(
            select(
                Account.id.label("id"),
                Account.name.label("name"),
                Account.currency.label("currency"),
                Account.bank_name.label("bank_name"),
            )
            .where(Account.workspace_id == workspace_id)
            .order_by(Account.name.asc(), Account.id.asc())
        )
        return [ImportDocumentAccountDto.model_validate(row) for row in result.mappings().all()]

    async def summarize_documents_for_workspace(
        self,
        workspace_id: UUID,
    ) -> ImportDocumentListSummaryDto:
        result = await self.session.execute(
            select(
                func.count(UploadedDocument.id).label("total_document_count"),
                func.count(UploadedDocument.id)
                .filter(UploadedDocument.status.in_(ATTENTION_DOCUMENT_STATUSES))
                .label("attention_document_count"),
            ).where(UploadedDocument.workspace_id == workspace_id)
        )
        return ImportDocumentListSummaryDto.model_validate(result.mappings().one())

    @staticmethod
    def _apply_document_list_filters(
        query: Any,
        filters: ImportDocumentListFilters,
    ) -> Any:
        if filters.state is not None:
            statuses = {
                ImportDocumentListState.ATTENTION: ATTENTION_DOCUMENT_STATUSES,
                ImportDocumentListState.PROCESSING: PROCESSING_DOCUMENT_STATUSES,
                ImportDocumentListState.COMPLETED: COMPLETED_DOCUMENT_STATUSES,
            }[filters.state]
            query = query.where(UploadedDocument.status.in_(statuses))
        if filters.account_id is not None:
            query = query.where(UploadedDocument.account_id == filters.account_id)
        if filters.period_from is not None:
            query = query.where(
                func.coalesce(
                    UploadedDocument.statement_period_end,
                    UploadedDocument.statement_period_start,
                )
                >= filters.period_from
            )
        if filters.period_to is not None:
            query = query.where(
                func.coalesce(
                    UploadedDocument.statement_period_start,
                    UploadedDocument.statement_period_end,
                )
                <= filters.period_to
            )
        return query

    async def count_documents_needing_attention(self, workspace_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(UploadedDocument)
            .where(
                UploadedDocument.workspace_id == workspace_id,
                UploadedDocument.status.in_(
                    {
                        UploadedDocumentStatus.REQUIRES_REVIEW,
                        UploadedDocumentStatus.FAILED_TO_PARSE,
                        UploadedDocumentStatus.PENDING_PARSE,
                    }
                ),
            )
        )
        return result.scalar_one()

    async def mark_document_status(
        self,
        document: UploadedDocument,
        status: UploadedDocumentStatus,
    ) -> None:
        document.status = status
        await self.session.flush()

    async def delete_document(self, document: UploadedDocument) -> None:
        await self.session.delete(document)
        await self.session.flush()

    async def mark_attempt_success(
        self,
        attempt: ParseAttempt,
        *,
        raw_text_by_page_json: list[str],
        raw_tables_json: list[dict[str, object]],
        metadata: dict[str, object],
    ) -> None:
        attempt.status = ParseAttemptStatus.SUCCESS
        attempt.raw_text_by_page_json = raw_text_by_page_json
        attempt.raw_tables_json = raw_tables_json
        attempt.extra_metadata = metadata
        await self.session.flush()

    async def mark_attempt_status(
        self,
        attempt: ParseAttempt,
        status: ParseAttemptStatus,
    ) -> None:
        attempt.status = status
        await self.session.flush()

    async def mark_attempt_failed(
        self,
        attempt: ParseAttempt,
        *,
        error_code: str,
        error_message: str,
    ) -> None:
        attempt.status = ParseAttemptStatus.FAILED
        attempt.error_code = error_code
        attempt.error_message_sanitized = error_message
        await self.session.flush()

    async def store_attempt_validation(
        self,
        attempt: ParseAttempt,
        *,
        control_totals: dict[str, object] | None,
        validation_report: dict[str, object],
    ) -> None:
        attempt.control_totals_json = control_totals
        attempt.validation_report_json = validation_report
        await self.session.flush()

    async def mark_attempt_requires_review(
        self,
        attempt: ParseAttempt,
        *,
        message: str,
        validation_report: dict[str, object] | None = None,
    ) -> None:
        report = dict(validation_report or {})
        report.setdefault("message", message)
        report.setdefault("parser_message", message)
        attempt.status = ParseAttemptStatus.REQUIRES_REVIEW
        attempt.validation_report_json = report
        await self.session.flush()


def _document_snapshot(document: UploadedDocument) -> ImportDocumentSnapshot:
    parse_attempts = sorted(
        document.parse_attempts,
        key=lambda attempt: attempt.started_at,
        reverse=True,
    )
    attempts = [_parse_attempt_snapshot(attempt) for attempt in parse_attempts]
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
        account=_account_ref(document),
        validation=latest_attempt.validation if latest_attempt else None,
        raw_transactions=[_raw_transaction_row(row) for row in document.raw_transactions],
        parse_attempts=attempts,
    )


def _account_ref(document: UploadedDocument) -> ImportDocumentAccountDto | None:
    if document.account is None:
        return None
    return ImportDocumentAccountDto(
        id=document.account.id,
        name=document.account.name,
        currency=document.account.currency,
        bank_name=document.account.bank_name,
    )


def _raw_transaction_row(row: RawTransaction) -> ImportRawTransactionRow:
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


def _parse_attempt_snapshot(attempt: ParseAttempt) -> ImportParseAttemptSnapshot:
    return ImportParseAttemptSnapshot(
        id=attempt.id,
        status=attempt.status,
        parser_name=attempt.parser_name,
        parser_version=attempt.parser_version,
        started_at=attempt.started_at,
        finished_at=attempt.finished_at,
        error_message=attempt.error_message_sanitized,
        validation=(
            StoredValidationReport.model_validate(attempt.validation_report_json)
            if attempt.validation_report_json is not None
            else None
        ),
        raw_tables=attempt.raw_tables_json,
    )
