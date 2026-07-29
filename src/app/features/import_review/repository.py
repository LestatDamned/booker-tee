"""Persistence reads, locks, and mutations owned by import review."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.base import ExecutableOption

from app.features.import_review.domain.posting import raw_transaction_effective_account_id
from app.features.import_review.domain.queue import REVIEW_QUEUE_STATUSES
from app.features.imports.models import RawTransaction, UploadedDocument
from app.features.imports.statements.types import RawTransactionStatus
from app.features.ledger.domain.types import OperationSource, OperationStatus, OperationType
from app.features.ledger.models import MoneyEntry, Operation

RawTransactionFingerprint = tuple[UUID, date, Decimal, str]


class ImportReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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

    async def count_raw_transactions_needing_attention(self, workspace_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(RawTransaction)
            .where(
                RawTransaction.workspace_id == workspace_id,
                RawTransaction.status.in_(REVIEW_QUEUE_STATUSES),
            )
        )
        return result.scalar_one()

    async def count_raw_transactions_for_document(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
    ) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(RawTransaction)
            .where(
                RawTransaction.workspace_id == workspace_id,
                RawTransaction.uploaded_document_id == document_id,
            )
        )
        return result.scalar_one()

    async def count_reviewable_raw_transactions_for_document(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
    ) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(RawTransaction)
            .where(
                RawTransaction.workspace_id == workspace_id,
                RawTransaction.uploaded_document_id == document_id,
                RawTransaction.status.in_(REVIEW_QUEUE_STATUSES),
            )
        )
        return result.scalar_one()

    async def list_reviewable_documents_with_counts(
        self,
        *,
        workspace_id: UUID,
        limit: int,
    ) -> list[tuple[UploadedDocument, int]]:
        reviewable_counts = (
            select(
                RawTransaction.uploaded_document_id.label("document_id"),
                func.count(RawTransaction.id).label("reviewable_count"),
            )
            .where(
                RawTransaction.workspace_id == workspace_id,
                RawTransaction.status.in_(REVIEW_QUEUE_STATUSES),
            )
            .group_by(RawTransaction.uploaded_document_id)
            .subquery()
        )
        result = await self.session.execute(
            select(UploadedDocument, reviewable_counts.c.reviewable_count)
            .join(reviewable_counts, reviewable_counts.c.document_id == UploadedDocument.id)
            .options(selectinload(UploadedDocument.account))
            .where(UploadedDocument.workspace_id == workspace_id)
            .order_by(UploadedDocument.created_at.desc())
            .limit(limit)
        )
        return [(document, int(reviewable_count)) for document, reviewable_count in result.all()]

    async def get_next_review_raw_transaction(
        self,
        workspace_id: UUID,
    ) -> RawTransaction | None:
        result = await self.session.execute(
            select(RawTransaction)
            .join(UploadedDocument)
            .options(*self._review_row_load_options())
            .where(
                RawTransaction.workspace_id == workspace_id,
                RawTransaction.status.in_(REVIEW_QUEUE_STATUSES),
            )
            .order_by(UploadedDocument.created_at.desc(), RawTransaction.row_index)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_next_review_raw_transaction_for_document(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
    ) -> RawTransaction | None:
        result = await self.session.execute(
            select(RawTransaction)
            .options(*self._review_row_load_options())
            .where(
                RawTransaction.workspace_id == workspace_id,
                RawTransaction.uploaded_document_id == document_id,
                RawTransaction.status.in_(REVIEW_QUEUE_STATUSES),
            )
            .order_by(RawTransaction.row_index.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_next_review_raw_transaction_after(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        current_row_index: int,
    ) -> RawTransaction | None:
        result = await self.session.execute(
            select(RawTransaction)
            .options(*self._review_row_load_options())
            .where(
                RawTransaction.workspace_id == workspace_id,
                RawTransaction.uploaded_document_id == document_id,
                RawTransaction.status.in_(REVIEW_QUEUE_STATUSES),
                RawTransaction.row_index > current_row_index,
            )
            .order_by(RawTransaction.row_index.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_review_raw_transaction(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        raw_transaction_id: UUID,
    ) -> RawTransaction | None:
        result = await self.session.execute(
            select(RawTransaction)
            .options(*self._review_row_load_options())
            .where(
                RawTransaction.id == raw_transaction_id,
                RawTransaction.workspace_id == workspace_id,
                RawTransaction.uploaded_document_id == document_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_adjacent_review_raw_transaction(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        current_row_index: int,
        direction: str,
    ) -> RawTransaction | None:
        query = (
            select(RawTransaction)
            .options(*self._review_row_load_options())
            .where(
                RawTransaction.workspace_id == workspace_id,
                RawTransaction.uploaded_document_id == document_id,
                RawTransaction.status.in_(REVIEW_QUEUE_STATUSES),
            )
            .limit(1)
        )
        if direction == "prev":
            query = query.where(RawTransaction.row_index < current_row_index).order_by(
                RawTransaction.row_index.desc(),
            )
        else:
            query = query.where(RawTransaction.row_index > current_row_index).order_by(
                RawTransaction.row_index.asc(),
            )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    def _review_row_load_options() -> tuple[ExecutableOption, ...]:
        return (
            selectinload(RawTransaction.account),
            selectinload(RawTransaction.uploaded_document),
            selectinload(RawTransaction.suggested_category),
        )

    async def list_possible_duplicate_candidates(
        self,
        *,
        workspace_id: UUID,
        fingerprints: set[RawTransactionFingerprint],
        exclude_document_id: UUID,
    ) -> list[RawTransaction]:
        if not fingerprints:
            return []

        account_ids = {fingerprint[0] for fingerprint in fingerprints}
        operation_dates = {fingerprint[1] for fingerprint in fingerprints}
        amounts = {fingerprint[2] for fingerprint in fingerprints}
        currencies = {fingerprint[3] for fingerprint in fingerprints}
        result = await self.session.execute(
            select(RawTransaction)
            .join(UploadedDocument)
            .options(selectinload(RawTransaction.uploaded_document))
            .where(
                RawTransaction.workspace_id == workspace_id,
                RawTransaction.uploaded_document_id != exclude_document_id,
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
            .order_by(UploadedDocument.created_at.desc(), RawTransaction.row_index)
        )
        return [
            candidate
            for candidate in result.scalars().all()
            if (
                candidate.account_id,
                candidate.operation_date,
                candidate.amount,
                candidate.currency,
            )
            in fingerprints
        ]

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
            self._locked_raw_transactions_query(workspace_id).where(
                RawTransaction.id == raw_transaction_id,
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
            self._locked_raw_transactions_query(workspace_id).where(
                RawTransaction.id == raw_transaction_id
            )
        )
        return result.scalar_one_or_none()

    async def lock_raw_transactions_for_workspace(
        self,
        *,
        workspace_id: UUID,
        raw_transaction_ids: set[UUID],
    ) -> list[RawTransaction]:
        if not raw_transaction_ids:
            return []
        result = await self.session.execute(
            self._locked_raw_transactions_query(workspace_id)
            .where(RawTransaction.id.in_(raw_transaction_ids))
            .order_by(RawTransaction.id)
        )
        return list(result.scalars().all())

    @staticmethod
    def _locked_raw_transactions_query(
        workspace_id: UUID,
    ) -> Select[tuple[RawTransaction]]:
        return (
            select(RawTransaction)
            .options(
                selectinload(RawTransaction.uploaded_document).selectinload(
                    UploadedDocument.account
                )
            )
            .where(RawTransaction.workspace_id == workspace_id)
            .with_for_update()
        )

    async def list_transfer_candidate_raw_transactions(
        self,
        *,
        workspace_id: UUID,
        raw_transaction: RawTransaction,
        day_window: int = 3,
    ) -> list[RawTransaction]:
        source_account_id = await self._raw_transaction_effective_account_id(
            workspace_id=workspace_id,
            raw_transaction=raw_transaction,
        )
        if (
            raw_transaction.amount is None
            or raw_transaction.currency is None
            or raw_transaction.operation_date is None
            or source_account_id is None
        ):
            return []
        candidate_account_id = func.coalesce(
            RawTransaction.account_id,
            UploadedDocument.account_id,
        )
        result = await self.session.execute(
            select(RawTransaction)
            .join(UploadedDocument, UploadedDocument.id == RawTransaction.uploaded_document_id)
            .options(
                selectinload(RawTransaction.account),
                selectinload(RawTransaction.uploaded_document).selectinload(
                    UploadedDocument.account
                ),
            )
            .where(
                RawTransaction.workspace_id == workspace_id,
                RawTransaction.id != raw_transaction.id,
                RawTransaction.linked_operation_id.is_(None),
                candidate_account_id.is_not(None),
                candidate_account_id != source_account_id,
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

    async def list_transfer_candidate_raw_transactions_for_sources(
        self,
        *,
        workspace_id: UUID,
        raw_transactions: list[RawTransaction],
        day_window: int = 3,
    ) -> list[RawTransaction]:
        eligible = [
            raw_transaction
            for raw_transaction in raw_transactions
            if raw_transaction.linked_operation_id is None
            and raw_transaction.amount is not None
            and raw_transaction.currency is not None
            and raw_transaction.operation_date is not None
            and raw_transaction_effective_account_id(raw_transaction) is not None
        ]
        if not eligible:
            return []

        operation_dates = [
            raw_transaction.operation_date
            for raw_transaction in eligible
            if raw_transaction.operation_date is not None
        ]
        amounts = {
            -raw_transaction.amount
            for raw_transaction in eligible
            if raw_transaction.amount is not None
        }
        currencies = {
            raw_transaction.currency
            for raw_transaction in eligible
            if raw_transaction.currency is not None
        }
        candidate_account_id = func.coalesce(
            RawTransaction.account_id,
            UploadedDocument.account_id,
        )
        result = await self.session.execute(
            select(RawTransaction)
            .join(UploadedDocument, UploadedDocument.id == RawTransaction.uploaded_document_id)
            .options(
                selectinload(RawTransaction.account),
                selectinload(RawTransaction.uploaded_document).selectinload(
                    UploadedDocument.account
                ),
            )
            .where(
                RawTransaction.workspace_id == workspace_id,
                RawTransaction.id.not_in({item.id for item in eligible}),
                RawTransaction.linked_operation_id.is_(None),
                candidate_account_id.is_not(None),
                RawTransaction.currency.in_(currencies),
                RawTransaction.amount.in_(amounts),
                RawTransaction.operation_date.between(
                    min(operation_dates) - timedelta(days=day_window),
                    max(operation_dates) + timedelta(days=day_window),
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

    async def list_manual_transfer_candidates_for_raw_transaction(
        self,
        *,
        workspace_id: UUID,
        raw_transaction: RawTransaction,
        day_window: int = 3,
    ) -> list[Operation]:
        source_account_id = await self._raw_transaction_effective_account_id(
            workspace_id=workspace_id,
            raw_transaction=raw_transaction,
        )
        if (
            raw_transaction.amount is None
            or raw_transaction.currency is None
            or raw_transaction.operation_date is None
            or source_account_id is None
        ):
            return []

        result = await self.session.execute(
            select(Operation)
            .join(MoneyEntry)
            .options(
                selectinload(Operation.raw_transactions).selectinload(
                    RawTransaction.uploaded_document
                ),
                selectinload(Operation.money_entries).selectinload(MoneyEntry.account),
            )
            .where(
                Operation.workspace_id == workspace_id,
                Operation.source == OperationSource.MANUAL,
                Operation.type == OperationType.TRANSFER,
                Operation.status == OperationStatus.CONFIRMED,
                Operation.operation_date.between(
                    raw_transaction.operation_date - timedelta(days=day_window),
                    raw_transaction.operation_date + timedelta(days=day_window),
                ),
                MoneyEntry.account_id == source_account_id,
                MoneyEntry.amount == raw_transaction.amount,
                MoneyEntry.currency == raw_transaction.currency,
            )
            .order_by(Operation.operation_date, Operation.created_at)
        )
        return [
            operation
            for operation in result.unique().scalars().all()
            if not any(
                raw_transaction_effective_account_id(linked_raw) == source_account_id
                for linked_raw in operation.raw_transactions
            )
        ]

    async def list_manual_transfer_candidates_for_raw_transactions(
        self,
        *,
        workspace_id: UUID,
        raw_transactions: list[RawTransaction],
        day_window: int = 3,
    ) -> list[Operation]:
        eligible = [
            raw_transaction
            for raw_transaction in raw_transactions
            if raw_transaction.linked_operation_id is None
            and raw_transaction.amount is not None
            and raw_transaction.currency is not None
            and raw_transaction.operation_date is not None
            and raw_transaction_effective_account_id(raw_transaction) is not None
        ]
        if not eligible:
            return []

        operation_dates = [
            raw_transaction.operation_date
            for raw_transaction in eligible
            if raw_transaction.operation_date is not None
        ]
        source_account_ids = {
            account_id
            for raw_transaction in eligible
            if (account_id := raw_transaction_effective_account_id(raw_transaction)) is not None
        }
        amounts = {
            raw_transaction.amount
            for raw_transaction in eligible
            if raw_transaction.amount is not None
        }
        currencies = {
            raw_transaction.currency
            for raw_transaction in eligible
            if raw_transaction.currency is not None
        }
        result = await self.session.execute(
            select(Operation)
            .join(MoneyEntry)
            .options(
                selectinload(Operation.raw_transactions).selectinload(
                    RawTransaction.uploaded_document
                ),
                selectinload(Operation.money_entries).selectinload(MoneyEntry.account),
            )
            .where(
                Operation.workspace_id == workspace_id,
                Operation.source == OperationSource.MANUAL,
                Operation.type == OperationType.TRANSFER,
                Operation.status == OperationStatus.CONFIRMED,
                Operation.operation_date.between(
                    min(operation_dates) - timedelta(days=day_window),
                    max(operation_dates) + timedelta(days=day_window),
                ),
                MoneyEntry.account_id.in_(source_account_ids),
                MoneyEntry.amount.in_(amounts),
                MoneyEntry.currency.in_(currencies),
            )
            .order_by(Operation.operation_date, Operation.created_at)
        )
        return list(result.unique().scalars().all())

    async def _raw_transaction_effective_account_id(
        self,
        *,
        workspace_id: UUID,
        raw_transaction: RawTransaction,
    ) -> UUID | None:
        account_id = raw_transaction_effective_account_id(raw_transaction)
        if account_id is not None:
            return account_id
        result = await self.session.execute(
            select(UploadedDocument.account_id).where(
                UploadedDocument.id == raw_transaction.uploaded_document_id,
                UploadedDocument.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()
