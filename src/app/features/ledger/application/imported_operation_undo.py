from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.models import UploadedDocumentStatus
from app.features.imports.repository import ImportRepository
from app.features.ledger.domain.raw_transactions import restored_raw_status_after_unlink
from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.models import Operation, OperationSource, OperationStatus
from app.features.ledger.repository import LedgerRepository
from app.features.workspaces.service import WorkspaceContext


class ImportedOperationUndoUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.imports = ImportRepository(session)
        self.ledger = LedgerRepository(session)

    async def undo_raw_transaction_posting(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
        raw_transaction_id: UUID,
    ) -> Operation:
        raw_transaction = await self.imports.get_raw_transaction_for_workspace(
            context.workspace.id,
            document_id,
            raw_transaction_id,
        )
        if raw_transaction is None:
            raise LedgerPostingError("Raw transaction row was not found.")
        if raw_transaction.linked_operation_id is None:
            raise LedgerPostingError("Raw transaction row is not linked to an operation.")

        operation = await self.ledger.get_operation_for_workspace(
            context.workspace.id,
            raw_transaction.linked_operation_id,
        )
        if operation is None:
            raise LedgerPostingError("Linked operation was not found.")
        if operation.source != OperationSource.BANK_PDF:
            raise LedgerPostingError("Only imported bank PDF operations can be undone here.")
        if operation.status != OperationStatus.CONFIRMED:
            raise LedgerPostingError("Only confirmed operations can be undone.")

        affected_document_ids = {
            linked_raw.uploaded_document_id for linked_raw in operation.raw_transactions
        }
        for linked_raw in operation.raw_transactions:
            linked_raw.linked_operation_id = None
            linked_raw.status = restored_raw_status_after_unlink(linked_raw)

        operation.status = OperationStatus.IGNORED
        operation.updated_by_user_id = context.user.id
        for affected_document_id in affected_document_ids:
            document = await self.imports.get_document_for_workspace(
                context.workspace.id,
                affected_document_id,
            )
            if document is not None:
                await self.imports.mark_document_status(
                    document,
                    UploadedDocumentStatus.REQUIRES_REVIEW,
                )
        await self.session.commit()
        return operation
