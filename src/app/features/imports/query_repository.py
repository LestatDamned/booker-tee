from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.imports.models import (
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
