from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.imports.errors import ImportDocumentManagementError
from app.features.imports.models import (
    RawTransaction,
    RawTransactionStatus,
    UploadedDocument,
    UploadedDocumentStatus,
)
from app.features.imports.repository import ImportRepository


class RawTransactionDocument(Protocol):
    raw_transactions: list[RawTransaction]


class ImportDocumentManagementUseCase:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.imports = ImportRepository(session)

    async def ignore_document(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
    ) -> UploadedDocument:
        document = await self._get_document(workspace_id, document_id)
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
        document = await self._get_document(workspace_id, document_id)
        if document_has_linked_operations(document):
            raise ImportDocumentManagementError("Нельзя удалить документ со связанными операциями.")
        storage_path = self.settings.upload_storage_dir / document.storage_key
        await self.imports.delete_document(document)
        await self.session.commit()
        storage_path.unlink(missing_ok=True)

    async def _get_document(
        self,
        workspace_id: UUID,
        document_id: UUID,
    ) -> UploadedDocument:
        document = await self.imports.get_document_for_workspace(workspace_id, document_id)
        if document is None:
            raise ImportDocumentManagementError("Документ не найден.")
        return document


def document_has_linked_operations(document: RawTransactionDocument) -> bool:
    return any(
        raw_transaction.linked_operation_id is not None
        for raw_transaction in document.raw_transactions
    )
