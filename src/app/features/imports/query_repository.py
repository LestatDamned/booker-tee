from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.imports.models import RawTransaction, UploadedDocument
from app.features.ledger.models import MoneyEntry, Operation


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
