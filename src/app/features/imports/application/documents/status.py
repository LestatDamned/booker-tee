from uuid import UUID

from app.features.imports.models import (
    RawTransactionStatus,
    UploadedDocument,
    UploadedDocumentStatus,
)
from app.features.imports.repository import ImportRepository

COMPLETE_RAW_TRANSACTION_STATUSES = {
    RawTransactionStatus.CONFIRMED,
    RawTransactionStatus.IGNORED,
    RawTransactionStatus.DUPLICATE,
}


class ImportedDocumentStatusUpdater:
    def __init__(self, imports: ImportRepository) -> None:
        self.imports = imports

    async def mark_imported_if_complete(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
    ) -> bool:
        document = await self.imports.get_document_for_workspace(workspace_id, document_id)
        if document is None or not document.raw_transactions:
            return False
        if all(
            row.status in COMPLETE_RAW_TRANSACTION_STATUSES for row in document.raw_transactions
        ):
            await self.imports.mark_document_status(document, UploadedDocumentStatus.IMPORTED)
            return True
        return False

    async def sync_review_status(self, document: UploadedDocument) -> bool:
        if not document.raw_transactions:
            return False
        target_status = (
            UploadedDocumentStatus.IMPORTED
            if all(
                row.status in COMPLETE_RAW_TRANSACTION_STATUSES for row in document.raw_transactions
            )
            else UploadedDocumentStatus.REQUIRES_REVIEW
        )
        if document.status is target_status:
            return False
        await self.imports.mark_document_status(document, target_status)
        return True
