from uuid import UUID

from app.features.imports.models import RawTransactionStatus, UploadedDocumentStatus
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
    ) -> None:
        document = await self.imports.get_document_for_workspace(workspace_id, document_id)
        if document is None or not document.raw_transactions:
            return
        if all(
            row.status in COMPLETE_RAW_TRANSACTION_STATUSES for row in document.raw_transactions
        ):
            await self.imports.mark_document_status(document, UploadedDocumentStatus.IMPORTED)
