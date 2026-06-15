from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.imports.models import (
    ParseAttempt,
    ParseAttemptStatus,
    RawTransaction,
    RawTransactionStatus,
    UploadedDocument,
    UploadedDocumentStatus,
)
from app.features.ledger.models import MoneyEntry, Operation


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
        result = await self.session.execute(
            select(UploadedDocument)
            .options(
                selectinload(UploadedDocument.account),
                selectinload(UploadedDocument.parse_attempts),
                selectinload(UploadedDocument.raw_transactions),
                selectinload(UploadedDocument.raw_transactions)
                .selectinload(RawTransaction.linked_operation)
                .selectinload(Operation.category),
                selectinload(UploadedDocument.raw_transactions)
                .selectinload(RawTransaction.linked_operation)
                .selectinload(Operation.property),
                selectinload(UploadedDocument.raw_transactions)
                .selectinload(RawTransaction.linked_operation)
                .selectinload(Operation.money_entries)
                .selectinload(MoneyEntry.account),
            )
            .where(
                UploadedDocument.id == document_id,
                UploadedDocument.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_documents_for_workspace(self, workspace_id: UUID) -> list[UploadedDocument]:
        result = await self.session.execute(
            select(UploadedDocument)
            .where(UploadedDocument.workspace_id == workspace_id)
            .order_by(UploadedDocument.created_at.desc())
        )
        return list(result.scalars().all())

    async def create_raw_transactions(
        self,
        raw_transactions: list[RawTransaction],
    ) -> list[RawTransaction]:
        self.session.add_all(raw_transactions)
        await self.session.flush()
        return raw_transactions

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

    async def has_confirmed_raw_transaction_with_dedupe_hash(
        self,
        *,
        workspace_id: UUID,
        dedupe_hash: str,
        exclude_raw_transaction_id: UUID,
    ) -> bool:
        result = await self.session.execute(
            select(RawTransaction.id)
            .where(
                RawTransaction.workspace_id == workspace_id,
                RawTransaction.dedupe_hash == dedupe_hash,
                RawTransaction.id != exclude_raw_transaction_id,
                RawTransaction.status == RawTransactionStatus.CONFIRMED,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def get_raw_transaction_for_workspace(
        self,
        workspace_id: UUID,
        document_id: UUID,
        raw_transaction_id: UUID,
    ) -> RawTransaction | None:
        result = await self.session.execute(
            select(RawTransaction).where(
                RawTransaction.id == raw_transaction_id,
                RawTransaction.workspace_id == workspace_id,
                RawTransaction.uploaded_document_id == document_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_raw_transaction_by_id_for_workspace(
        self,
        workspace_id: UUID,
        raw_transaction_id: UUID,
    ) -> RawTransaction | None:
        result = await self.session.execute(
            select(RawTransaction).where(
                RawTransaction.id == raw_transaction_id,
                RawTransaction.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_transfer_candidate_raw_transactions(
        self,
        *,
        workspace_id: UUID,
        raw_transaction: RawTransaction,
        day_window: int = 3,
    ) -> list[RawTransaction]:
        if (
            raw_transaction.amount is None
            or raw_transaction.currency is None
            or raw_transaction.operation_date is None
            or raw_transaction.account_id is None
        ):
            return []
        result = await self.session.execute(
            select(RawTransaction)
            .options(selectinload(RawTransaction.account))
            .where(
                RawTransaction.workspace_id == workspace_id,
                RawTransaction.id != raw_transaction.id,
                RawTransaction.linked_operation_id.is_(None),
                RawTransaction.account_id.is_not(None),
                RawTransaction.account_id != raw_transaction.account_id,
                RawTransaction.currency == raw_transaction.currency,
                RawTransaction.amount == -raw_transaction.amount,
                RawTransaction.operation_date.between(
                    raw_transaction.operation_date - timedelta(days=day_window),
                    raw_transaction.operation_date + timedelta(days=day_window),
                ),
                RawTransaction.status.in_(
                    [
                        RawTransactionStatus.NORMALIZED,
                        RawTransactionStatus.SUGGESTED,
                        RawTransactionStatus.MATCHED,
                        RawTransactionStatus.NEEDS_REVIEW,
                        RawTransactionStatus.POSSIBLE_DUPLICATE,
                    ]
                ),
            )
            .order_by(RawTransaction.operation_date, RawTransaction.row_index)
        )
        return list(result.scalars().all())

    async def mark_raw_transaction_status(
        self,
        raw_transaction: RawTransaction,
        status: RawTransactionStatus,
    ) -> None:
        raw_transaction.status = status
        await self.session.flush()

    async def link_raw_transaction_to_operation(
        self,
        raw_transaction: RawTransaction,
        *,
        operation_id: UUID,
    ) -> None:
        raw_transaction.status = RawTransactionStatus.CONFIRMED
        raw_transaction.linked_operation_id = operation_id
        await self.session.flush()

    async def mark_reviewable_raw_transactions_superseded(
        self,
        document: UploadedDocument,
        *,
        superseded_by_attempt_id: UUID,
    ) -> None:
        for raw_transaction in document.raw_transactions:
            if raw_transaction.status in {
                RawTransactionStatus.CONFIRMED,
                RawTransactionStatus.IGNORED,
                RawTransactionStatus.DUPLICATE,
            }:
                continue
            raw_transaction.status = RawTransactionStatus.DUPLICATE
            message = f"Superseded by reparse attempt {superseded_by_attempt_id}."
            raw_transaction.normalization_error = append_review_message(
                raw_transaction.normalization_error,
                message,
            )
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
    ) -> None:
        validation_report: dict[str, object] = {"message": message}
        attempt.status = ParseAttemptStatus.REQUIRES_REVIEW
        attempt.validation_report_json = validation_report
        await self.session.flush()


def append_review_message(existing: str | None, message: str) -> str:
    if not existing:
        return message
    if message in existing:
        return existing
    return f"{existing}; {message}"
