from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.imports.documents.repository import DocumentRepository
from app.features.imports.domain.types import RawTransactionStatus, UploadedDocumentStatus
from app.features.imports.models import (
    ImportMappingExecution,
    ImportMappingTemplate,
    ParseAttempt,
    ParseAttemptStatus,
    RawTransaction,
    UploadedDocument,
)


class ImportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_uploaded_document(self, document: UploadedDocument) -> UploadedDocument:
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
        return await DocumentRepository(self.session).get_document_for_workspace(
            workspace_id,
            document_id,
        )

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

    async def create_raw_transactions(
        self,
        raw_transactions: list[RawTransaction],
    ) -> list[RawTransaction]:
        self.session.add_all(raw_transactions)
        await self.session.flush()
        return raw_transactions

    async def create_mapping_template(
        self,
        template: ImportMappingTemplate,
    ) -> ImportMappingTemplate:
        self.session.add(template)
        await self.session.flush()
        return template

    async def create_mapping_execution(
        self,
        execution: ImportMappingExecution,
    ) -> ImportMappingExecution:
        self.session.add(execution)
        await self.session.flush()
        return execution

    async def get_mapping_execution(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        idempotency_key: UUID,
    ) -> ImportMappingExecution | None:
        result = await self.session.execute(
            select(ImportMappingExecution).where(
                ImportMappingExecution.workspace_id == workspace_id,
                ImportMappingExecution.uploaded_document_id == document_id,
                ImportMappingExecution.idempotency_key == str(idempotency_key),
            )
        )
        return result.scalar_one_or_none()

    async def list_mapping_templates(
        self,
        *,
        workspace_id: UUID,
        bank_name: str | None = None,
        statement_type: str | None = None,
    ) -> list[ImportMappingTemplate]:
        query = select(ImportMappingTemplate).where(
            ImportMappingTemplate.workspace_id == workspace_id
        )
        if bank_name:
            query = query.where(ImportMappingTemplate.bank_name == bank_name)
        if statement_type:
            query = query.where(ImportMappingTemplate.statement_type == statement_type)
        query = query.order_by(ImportMappingTemplate.updated_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def find_existing_dedupe_hashes(
        self,
        *,
        workspace_id: UUID,
        dedupe_hashes: set[str],
        exclude_document_id: UUID | None = None,
    ) -> set[str]:
        if not dedupe_hashes:
            return set()
        query = select(RawTransaction.dedupe_hash).where(
            RawTransaction.workspace_id == workspace_id,
            RawTransaction.dedupe_hash.in_(dedupe_hashes),
            RawTransaction.status.not_in(
                [
                    RawTransactionStatus.DUPLICATE,
                    RawTransactionStatus.IGNORED,
                    RawTransactionStatus.FAILED,
                ]
            ),
        )
        if exclude_document_id is not None:
            query = query.where(RawTransaction.uploaded_document_id != exclude_document_id)

        result = await self.session.execute(query)
        return {value for value in result.scalars().all() if value is not None}

    async def find_existing_possible_duplicate_fingerprints(
        self,
        *,
        workspace_id: UUID,
        fingerprints: set[tuple[UUID, date, Decimal, str]],
        exclude_document_id: UUID | None = None,
    ) -> set[tuple[UUID, date, Decimal, str]]:
        if not fingerprints:
            return set()

        account_ids = {fingerprint[0] for fingerprint in fingerprints}
        operation_dates = {fingerprint[1] for fingerprint in fingerprints}
        amounts = {fingerprint[2] for fingerprint in fingerprints}
        currencies = {fingerprint[3] for fingerprint in fingerprints}
        query = select(
            RawTransaction.account_id,
            RawTransaction.operation_date,
            RawTransaction.amount,
            RawTransaction.currency,
        ).where(
            RawTransaction.workspace_id == workspace_id,
            RawTransaction.account_id.in_(account_ids),
            RawTransaction.operation_date.in_(operation_dates),
            RawTransaction.amount.in_(amounts),
            RawTransaction.currency.in_(currencies),
            RawTransaction.status.not_in(
                [
                    RawTransactionStatus.DUPLICATE,
                    RawTransactionStatus.IGNORED,
                    RawTransactionStatus.FAILED,
                ]
            ),
        )
        if exclude_document_id is not None:
            query = query.where(RawTransaction.uploaded_document_id != exclude_document_id)

        result = await self.session.execute(query)
        matches: set[tuple[UUID, date, Decimal, str]] = set()
        for account_id, operation_date, amount, currency in result.all():
            if account_id and operation_date and amount is not None and currency:
                fingerprint = (account_id, operation_date, amount, currency)
                if fingerprint in fingerprints:
                    matches.add(fingerprint)
        return matches

    async def mark_reviewable_raw_transactions_superseded(
        self,
        document: UploadedDocument,
    ) -> None:
        for raw_transaction in document.raw_transactions:
            if raw_transaction.status in {
                RawTransactionStatus.CONFIRMED,
                RawTransactionStatus.IGNORED,
                RawTransactionStatus.DUPLICATE,
            }:
                continue
            raw_transaction.status = RawTransactionStatus.DUPLICATE
        await self.session.flush()

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
