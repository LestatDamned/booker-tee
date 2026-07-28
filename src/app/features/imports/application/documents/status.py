from uuid import UUID

from app.features.imports.domain.document_lifecycle import (
    resolve_document_review_status,
    resolve_document_status_transition,
)
from app.features.imports.models import (
    UploadedDocument,
    UploadedDocumentStatus,
)
from app.features.imports.repository import ImportRepository


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
        if document is None:
            return False
        target_status = resolve_document_review_status(
            row.status for row in document.raw_transactions
        )
        if target_status is not UploadedDocumentStatus.IMPORTED:
            return False
        await transition_document_status(self.imports, document, target_status)
        return True

    async def sync_review_status(self, document: UploadedDocument) -> bool:
        target_status = resolve_document_review_status(
            row.status for row in document.raw_transactions
        )
        if target_status is None:
            return False
        if document.status is target_status:
            return False
        await transition_document_status(self.imports, document, target_status)
        return True


async def transition_document_status(
    imports: ImportRepository,
    document: UploadedDocument,
    target_status: UploadedDocumentStatus,
) -> None:
    resolved_status = resolve_document_status_transition(
        current_status=document.status,
        target_status=target_status,
    )
    await imports.mark_document_status(document, resolved_status)
