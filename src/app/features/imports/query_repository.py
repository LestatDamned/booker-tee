from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.accounts.models import Account
from app.features.imports.application.documents.listing import (
    ImportDocumentListAccountRow,
    ImportDocumentListFilters,
    ImportDocumentListPagination,
    ImportDocumentListRow,
    ImportDocumentListSort,
    ImportDocumentListState,
    ImportDocumentListSummaryRow,
)
from app.features.imports.models import (
    ParseAttempt,
    RawTransaction,
    RawTransactionStatus,
    UploadedDocument,
    UploadedDocumentStatus,
)
from app.features.ledger.models import MoneyEntry, Operation

REVIEWABLE_RAW_TRANSACTION_STATUSES = {
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


class ImportQueryRepository:
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
                .filter(RawTransaction.status.in_(REVIEWABLE_RAW_TRANSACTION_STATUSES))
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
                UploadedDocument.id,
                UploadedDocument.original_filename,
                UploadedDocument.status,
                UploadedDocument.created_at,
                UploadedDocument.file_size_bytes,
                UploadedDocument.bank_name,
                UploadedDocument.statement_period_start,
                UploadedDocument.statement_period_end,
                Account.id,
                Account.name,
                Account.currency,
                Account.bank_name,
                func.coalesce(raw_counts.c.total_row_count, 0),
                func.coalesce(raw_counts.c.reviewable_row_count, 0),
                latest_attempt_status,
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
        return [
            ImportDocumentListRow(
                id=document_id,
                filename=filename,
                status=document_status,
                created_at=created_at,
                file_size_bytes=file_size_bytes,
                detected_bank_name=detected_bank_name,
                statement_period_start=statement_period_start,
                statement_period_end=statement_period_end,
                account_id=account_id,
                account_name=account_name,
                account_currency=account_currency,
                account_bank_name=account_bank_name,
                total_row_count=int(total_row_count),
                reviewable_row_count=int(reviewable_row_count),
                latest_parse_attempt_status=attempt_status,
            )
            for (
                document_id,
                filename,
                document_status,
                created_at,
                file_size_bytes,
                detected_bank_name,
                statement_period_start,
                statement_period_end,
                account_id,
                account_name,
                account_currency,
                account_bank_name,
                total_row_count,
                reviewable_row_count,
                attempt_status,
            ) in result.all()
        ]

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
    ) -> list[ImportDocumentListAccountRow]:
        result = await self.session.execute(
            select(
                Account.id,
                Account.name,
                Account.currency,
                Account.bank_name,
            )
            .where(Account.workspace_id == workspace_id)
            .order_by(Account.name.asc(), Account.id.asc())
        )
        return [
            ImportDocumentListAccountRow(
                id=account_id,
                name=name,
                currency=currency,
                bank_name=bank_name,
            )
            for account_id, name, currency, bank_name in result.all()
        ]

    async def summarize_documents_for_workspace(
        self,
        workspace_id: UUID,
    ) -> ImportDocumentListSummaryRow:
        result = await self.session.execute(
            select(
                func.count(UploadedDocument.id),
                func.count(UploadedDocument.id).filter(
                    UploadedDocument.status.in_(ATTENTION_DOCUMENT_STATUSES)
                ),
            ).where(UploadedDocument.workspace_id == workspace_id)
        )
        total_document_count, attention_document_count = result.one()
        return ImportDocumentListSummaryRow(
            total_document_count=int(total_document_count),
            attention_document_count=int(attention_document_count),
        )

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

    async def count_raw_transactions_needing_attention(self, workspace_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(RawTransaction)
            .where(
                RawTransaction.workspace_id == workspace_id,
                RawTransaction.status.in_(REVIEWABLE_RAW_TRANSACTION_STATUSES),
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
                RawTransaction.status.in_(REVIEWABLE_RAW_TRANSACTION_STATUSES),
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
                RawTransaction.status.in_(REVIEWABLE_RAW_TRANSACTION_STATUSES),
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

    async def get_next_review_raw_transaction(self, workspace_id: UUID) -> RawTransaction | None:
        result = await self.session.execute(
            select(RawTransaction)
            .join(UploadedDocument)
            .options(
                selectinload(RawTransaction.account),
                selectinload(RawTransaction.uploaded_document),
                selectinload(RawTransaction.suggested_category),
            )
            .where(
                RawTransaction.workspace_id == workspace_id,
                RawTransaction.status.in_(REVIEWABLE_RAW_TRANSACTION_STATUSES),
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
            .options(
                selectinload(RawTransaction.account),
                selectinload(RawTransaction.uploaded_document),
                selectinload(RawTransaction.suggested_category),
            )
            .where(
                RawTransaction.workspace_id == workspace_id,
                RawTransaction.uploaded_document_id == document_id,
                RawTransaction.status.in_(REVIEWABLE_RAW_TRANSACTION_STATUSES),
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
            .options(
                selectinload(RawTransaction.account),
                selectinload(RawTransaction.uploaded_document),
                selectinload(RawTransaction.suggested_category),
            )
            .where(
                RawTransaction.workspace_id == workspace_id,
                RawTransaction.uploaded_document_id == document_id,
                RawTransaction.status.in_(REVIEWABLE_RAW_TRANSACTION_STATUSES),
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
            .options(
                selectinload(RawTransaction.account),
                selectinload(RawTransaction.uploaded_document),
                selectinload(RawTransaction.suggested_category),
            )
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
            .options(
                selectinload(RawTransaction.account),
                selectinload(RawTransaction.uploaded_document),
                selectinload(RawTransaction.suggested_category),
            )
            .where(
                RawTransaction.workspace_id == workspace_id,
                RawTransaction.uploaded_document_id == document_id,
                RawTransaction.status.in_(REVIEWABLE_RAW_TRANSACTION_STATUSES),
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
