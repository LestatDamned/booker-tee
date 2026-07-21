from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.application.review.confirmation_commands import (
    ImportReviewConfirmationConflictError,
)
from app.features.imports.errors import RawTransactionReviewError
from app.features.imports.repository import ImportRepository
from app.features.ledger.application.imported_operations import ImportedOperationUndoUseCase
from app.features.ledger.domain.types import OperationStatus
from app.features.ledger.repository import LedgerRepository
from app.features.workspaces.service import WorkspaceContext


@dataclass(frozen=True)
class UndoImportReviewPostingCommand:
    document_id: UUID
    item_id: UUID
    expected_operation_id: UUID


@dataclass(frozen=True)
class ImportReviewUndoResult:
    document_id: UUID
    item_id: UUID
    operation_id: UUID
    affected_document_ids: frozenset[UUID]
    updated_item_ids: frozenset[UUID]
    replayed: bool


class ImportReviewUndoService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._imports = ImportRepository(session)
        self._ledger = LedgerRepository(session)
        self._undo = ImportedOperationUndoUseCase(session)

    async def execute(
        self,
        *,
        context: WorkspaceContext,
        command: UndoImportReviewPostingCommand,
    ) -> ImportReviewUndoResult:
        try:
            row = await self._imports.get_raw_transaction_for_workspace(
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

            operation = await self._undo.undo_raw_transaction_posting(
                context=context,
                document_id=command.document_id,
                raw_transaction_id=command.item_id,
            )
            affected_document_ids = {
                linked_row.uploaded_document_id for linked_row in operation.raw_transactions
            }
            updated_item_ids = {linked_row.id for linked_row in operation.raw_transactions}
            affected_document_ids.add(command.document_id)
            updated_item_ids.add(command.item_id)
            return ImportReviewUndoResult(
                document_id=command.document_id,
                item_id=command.item_id,
                operation_id=operation.id,
                affected_document_ids=frozenset(affected_document_ids),
                updated_item_ids=frozenset(updated_item_ids),
                replayed=False,
            )
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
