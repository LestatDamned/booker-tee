"""Link an imported row to an existing manual income or expense."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.import_review.errors import RawTransactionReviewError
from app.features.import_review.repository import ImportReviewRepository
from app.features.import_review.schemas.commands import (
    ImportReviewExistingOperationLinkResult,
    LinkImportReviewExistingOperationCommand,
)
from app.features.imports.documents.lifecycle import ImportedDocumentStatusUpdater
from app.features.imports.documents.repository import DocumentRepository
from app.features.imports.statements.validation_service import StatementValidationService
from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.repository import LedgerRepository
from app.features.workspaces.activity_repository import WorkspaceActivityRepository
from app.features.workspaces.application.activity_details import (
    ImportReviewOperationLinkedActivityDetails,
)
from app.features.workspaces.application.activity_writer import WorkspaceActivityWriter
from app.features.workspaces.service import WorkspaceContext


class ExistingOperationLinkService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._documents = DocumentRepository(session)
        self._review = ImportReviewRepository(session)
        self._ledger = LedgerRepository(session)
        self._activity = WorkspaceActivityWriter(WorkspaceActivityRepository(session))

    async def execute(
        self,
        *,
        context: WorkspaceContext,
        command: LinkImportReviewExistingOperationCommand,
    ) -> ImportReviewExistingOperationLinkResult:
        try:
            result = await self._link(workspace_id=context.workspace.id, command=command)
            if not result.replayed:
                await self._activity.import_review_operation_linked(
                    context=context,
                    operation_id=result.operation_id,
                    details=ImportReviewOperationLinkedActivityDetails(
                        document_id=result.document_id,
                        item_id=result.item_id,
                    ),
                )
            await self._session.commit()
            return result
        except Exception:
            await self._session.rollback()
            raise

    async def _link(
        self,
        *,
        workspace_id: UUID,
        command: LinkImportReviewExistingOperationCommand,
    ) -> ImportReviewExistingOperationLinkResult:
        row = await self._review.get_raw_transaction_for_workspace(
            workspace_id,
            command.document_id,
            command.item_id,
        )
        if row is None:
            raise RawTransactionReviewError("Raw transaction row was not found.")
        if row.linked_operation_id == command.operation_id:
            return self._result(command, replayed=True)
        if row.linked_operation_id is not None or row.status is not command.expected_status:
            raise LedgerPostingError("Import review row is no longer available for linking.")

        operation = await self._ledger.get_operation_for_workspace_for_update(
            workspace_id=workspace_id,
            operation_id=command.operation_id,
        )
        if operation is None:
            raise LedgerPostingError("Manual operation candidate was not found.")
        candidates = await self._review.list_manual_income_expense_candidates_for_raw_transactions(
            workspace_id=workspace_id,
            raw_transactions=[row],
        )
        if not any(candidate.id == operation.id for candidate in candidates):
            raise LedgerPostingError("Manual operation is no longer a match candidate.")

        await self._review.link_raw_transaction_to_operation(row, operation_id=operation.id)
        document = await self._documents.get_document_for_workspace_for_update(
            workspace_id,
            command.document_id,
        )
        if document is None:
            raise RawTransactionReviewError("Document was not found.")
        await StatementValidationService(self._documents).refresh_for_document(document)
        await ImportedDocumentStatusUpdater(self._documents).sync_review_status(document)
        return self._result(command, replayed=False)

    @staticmethod
    def _result(
        command: LinkImportReviewExistingOperationCommand,
        *,
        replayed: bool,
    ) -> ImportReviewExistingOperationLinkResult:
        return ImportReviewExistingOperationLinkResult(
            item_id=command.item_id,
            document_id=command.document_id,
            operation_id=command.operation_id,
            replayed=replayed,
        )
