from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.imports.documents.errors import ImportDocumentManagementError
from app.features.imports.documents.lifecycle import (
    has_linked_operations,
    transition_document_status,
)
from app.features.imports.documents.repository import DocumentRepository
from app.features.imports.documents.types import UploadedDocumentStatus
from app.features.imports.models import UploadedDocument
from app.features.imports.statements.types import RawTransactionStatus


class ImportDocumentManagementUseCase:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.documents = DocumentRepository(session)

    async def ignore_document(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        expected_status: UploadedDocumentStatus | None = None,
    ) -> UploadedDocument:
        document = await self._get_document(workspace_id, document_id, expected_status)
        if has_linked_operations(document.raw_transactions):
            raise ImportDocumentManagementError(
                "Нельзя игнорировать документ со связанными операциями."
            )
        for raw_transaction in document.raw_transactions:
            raw_transaction.status = RawTransactionStatus.IGNORED
        await transition_document_status(
            self.documents,
            document,
            UploadedDocumentStatus.IGNORED,
        )
        await self.session.commit()
        return document

    async def delete_document(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        expected_status: UploadedDocumentStatus | None = None,
    ) -> None:
        document = await self._get_document(workspace_id, document_id, expected_status)
        if has_linked_operations(document.raw_transactions):
            raise ImportDocumentManagementError("Нельзя удалить документ со связанными операциями.")
        storage_path = self.settings.upload_storage_dir / document.storage_key
        await self.documents.delete_document(document)
        await self.session.commit()
        storage_path.unlink(missing_ok=True)

    async def _get_document(
        self,
        workspace_id: UUID,
        document_id: UUID,
        expected_status: UploadedDocumentStatus | None,
    ) -> UploadedDocument:
        document = await self.documents.get_document_for_workspace_for_update(
            workspace_id, document_id
        )
        if document is None:
            raise ImportDocumentManagementError("Документ не найден.")
        if expected_status is not None and document.status is not expected_status:
            raise ImportDocumentManagementError(
                "Состояние документа изменилось. Обновите страницу и повторите действие."
            )
        return document
