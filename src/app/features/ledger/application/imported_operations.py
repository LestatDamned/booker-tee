from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.features.imports.application.pipelines.document_validation import (
    refresh_document_validation,
)
from app.features.imports.models import UploadedDocumentStatus
from app.features.imports.repository import ImportRepository
from app.features.ledger.application.ledger_reference_resolver import LedgerReferenceResolver
from app.features.ledger.domain.raw_transactions import restored_raw_status_after_unlink
from app.features.ledger.domain.text import clean_description
from app.features.ledger.domain.types import (
    OperationSource,
    OperationStatus,
    imported_operation_actions,
)
from app.features.ledger.errors import (
    ImportedOperationNotEditableError,
    ImportedOperationNotFoundError,
    LedgerPostingError,
    OperationVersionConflictError,
)
from app.features.ledger.models import Operation
from app.features.ledger.repository import LedgerRepository
from app.features.workspaces.service import WorkspaceContext


@dataclass(frozen=True)
class UpdateImportedOperationReviewFieldsCommand:
    operation_id: UUID
    expected_version: int
    category_id: UUID | None
    property_id: UUID | None
    description: str | None


class ImportedOperationReviewUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ledger = LedgerRepository(session)
        self.references = LedgerReferenceResolver(session)

    async def update_review_fields(
        self,
        *,
        context: WorkspaceContext,
        command: UpdateImportedOperationReviewFieldsCommand,
    ) -> Operation:
        try:
            operation = await self._get_imported_operation(
                context.workspace.id,
                command.operation_id,
            )
            if not imported_operation_actions(operation.status).can_edit_review_fields:
                raise ImportedOperationNotEditableError()
            if operation.version != command.expected_version:
                raise OperationVersionConflictError()
            category = await self.references.get_category_or_uncategorized(
                context.workspace.id,
                command.category_id,
            )
            property_ = await self.references.get_property(
                context.workspace.id,
                command.property_id,
            )
            operation.category_id = category.id
            operation.property_id = property_.id if property_ else None
            operation.description = clean_description(command.description)
            operation.updated_by_user_id = context.user.id
            await self.session.flush()
            await self.session.commit()
            return operation
        except StaleDataError as error:
            await self.session.rollback()
            raise OperationVersionConflictError() from error
        except Exception:
            await self.session.rollback()
            raise

    async def _get_imported_operation(self, workspace_id: UUID, operation_id: UUID) -> Operation:
        operation = await self.ledger.get_operation_for_workspace(workspace_id, operation_id)
        if operation is None:
            raise ImportedOperationNotFoundError()
        if operation.source != OperationSource.BANK_PDF:
            raise LedgerPostingError("Only imported bank PDF operations can be changed here.")
        return operation


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
        if operation.status != OperationStatus.CONFIRMED:
            raise LedgerPostingError("Only confirmed operations can be undone.")

        if operation.source == OperationSource.MANUAL:
            raw_transaction.linked_operation_id = None
            raw_transaction.status = restored_raw_status_after_unlink(raw_transaction)
            document = await self.imports.get_document_for_workspace(
                context.workspace.id,
                document_id,
            )
            if document is not None:
                await refresh_document_validation(self.imports, document)
                await self.imports.mark_document_status(
                    document,
                    UploadedDocumentStatus.REQUIRES_REVIEW,
                )
            await self.session.commit()
            return operation

        if operation.source != OperationSource.BANK_PDF:
            raise LedgerPostingError("Only imported bank PDF operations can be undone here.")

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
                await refresh_document_validation(self.imports, document)
                await self.imports.mark_document_status(
                    document,
                    UploadedDocumentStatus.REQUIRES_REVIEW,
                )
        await self.session.commit()
        return operation
