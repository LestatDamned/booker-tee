"""Undo ledger postings from the import review workflow."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.import_review.domain.lifecycle import restored_review_status_after_unlink
from app.features.import_review.errors import (
    ImportReviewConfirmationConflictError,
    RawTransactionReviewError,
)
from app.features.import_review.repository import ImportReviewRepository
from app.features.import_review.schemas.commands import (
    ImportReviewUndoResult,
    UndoImportReviewPostingCommand,
)
from app.features.imports.documents.repository import DocumentRepository
from app.features.imports.documents.types import UploadedDocumentStatus
from app.features.imports.statements.validation_service import StatementValidationService
from app.features.ledger.application.imported_operations import ImportedOperationCorrection
from app.features.ledger.domain.types import OperationSource, OperationStatus
from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.repository import LedgerRepository
from app.features.workspaces.service import WorkspaceContext


class ImportReviewUndoService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._documents = DocumentRepository(session)
        self._review_repository = ImportReviewRepository(session)
        self._ledger = LedgerRepository(session)
        self._correction = ImportedOperationCorrection(session)

    async def execute(
        self,
        *,
        context: WorkspaceContext,
        command: UndoImportReviewPostingCommand,
    ) -> ImportReviewUndoResult:
        try:
            row = await self._review_repository.get_raw_transaction_for_workspace(
                context.workspace.id,
                command.document_id,
                command.item_id,
            )
            if row is None:
                raise RawTransactionReviewError("Raw transaction row was not found.")
            if row.linked_operation_id is None:
                replay = await self._find_replay(context=context, command=command)
                if replay is not None:
                    await self._session.commit()
                    return replay
                raise ImportReviewConfirmationConflictError(
                    "Raw transaction row is no longer linked to an operation."
                )
            if row.linked_operation_id != command.expected_operation_id:
                raise ImportReviewConfirmationConflictError(
                    "Raw transaction row is linked to another operation."
                )

            operation = await self._ledger.get_operation_for_workspace(
                context.workspace.id,
                row.linked_operation_id,
            )
            if operation is None:
                raise LedgerPostingError("Linked operation was not found.")
            if operation.status is not OperationStatus.CONFIRMED:
                raise LedgerPostingError("Only confirmed operations can be undone.")

            linked_rows_by_id = (
                {linked_row.id: linked_row for linked_row in operation.raw_transactions}
                if operation.source is OperationSource.BANK_PDF
                else {}
            )
            linked_rows_by_id[row.id] = row
            linked_rows = list(linked_rows_by_id.values())
            if operation.source is OperationSource.BANK_PDF:
                await self._correction.ignore_confirmed_import(
                    context=context,
                    operation=operation,
                )
            elif operation.source is not OperationSource.MANUAL:
                raise LedgerPostingError("Only imported bank PDF operations can be undone here.")

            affected_document_ids = {linked_row.uploaded_document_id for linked_row in linked_rows}
            updated_item_ids = {linked_row.id for linked_row in linked_rows}
            affected_document_ids.add(command.document_id)
            updated_item_ids.add(command.item_id)
            for linked_row in linked_rows:
                linked_row.linked_operation_id = None
                linked_row.status = restored_review_status_after_unlink(linked_row)
            await self._refresh_documents(
                workspace_id=context.workspace.id,
                document_ids=affected_document_ids,
            )
            result = ImportReviewUndoResult(
                document_id=command.document_id,
                item_id=command.item_id,
                operation_id=operation.id,
                affected_document_ids=frozenset(affected_document_ids),
                updated_item_ids=frozenset(updated_item_ids),
                replayed=False,
            )
            await self._session.commit()
            return result
        except Exception:
            await self._session.rollback()
            raise

    async def _find_replay(
        self,
        *,
        context: WorkspaceContext,
        command: UndoImportReviewPostingCommand,
    ) -> ImportReviewUndoResult | None:
        operation = await self._ledger.get_operation_for_workspace(
            context.workspace.id,
            command.expected_operation_id,
        )
        if operation is None or operation.status is not OperationStatus.IGNORED:
            return None
        metadata = operation.extra_metadata or {}
        if metadata.get("raw_transaction_id") != str(command.item_id):
            return None
        affected_document_ids = {
            command.document_id,
            *(linked_row.uploaded_document_id for linked_row in operation.raw_transactions),
        }
        matched_document_id = metadata.get("matched_uploaded_document_id")
        if isinstance(matched_document_id, str):
            affected_document_ids.add(UUID(matched_document_id))
        updated_item_ids = {command.item_id}
        matched_item_id = metadata.get("matched_raw_transaction_id")
        if isinstance(matched_item_id, str):
            updated_item_ids.add(UUID(matched_item_id))
        return ImportReviewUndoResult(
            document_id=command.document_id,
            item_id=command.item_id,
            operation_id=operation.id,
            affected_document_ids=frozenset(affected_document_ids),
            updated_item_ids=frozenset(updated_item_ids),
            replayed=True,
        )

    async def _refresh_documents(
        self,
        *,
        workspace_id: UUID,
        document_ids: set[UUID],
    ) -> None:
        for document_id in document_ids:
            document = await self._documents.get_document_for_workspace(
                workspace_id,
                document_id,
            )
            if document is None:
                continue
            await StatementValidationService(self._documents).refresh_for_document(document)
            await self._documents.mark_document_status(
                document,
                UploadedDocumentStatus.REQUIRES_REVIEW,
            )
