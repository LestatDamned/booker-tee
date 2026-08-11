from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.features.ledger.application.ledger_reference_resolver import LedgerReferenceResolver
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
from app.features.workspaces.activity_repository import WorkspaceActivityRepository
from app.features.workspaces.application.activity_details import (
    ImportedOperationUpdatedActivityDetails,
)
from app.features.workspaces.application.activity_writer import WorkspaceActivityWriter
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
        self.activity = WorkspaceActivityWriter(WorkspaceActivityRepository(session))

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
            await self.activity.imported_operation_updated(
                context=context,
                operation_id=operation.id,
                details=ImportedOperationUpdatedActivityDetails(),
            )
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


class ImportedOperationCorrection:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ignore_confirmed_import(
        self,
        *,
        context: WorkspaceContext,
        operation: Operation,
    ) -> Operation:
        if operation.workspace_id != context.workspace.id:
            raise LedgerPostingError("Linked operation was not found.")
        if operation.status is not OperationStatus.CONFIRMED:
            raise LedgerPostingError("Only confirmed operations can be undone.")
        if operation.source is not OperationSource.BANK_PDF:
            raise LedgerPostingError("Only imported bank PDF operations can be undone here.")
        operation.status = OperationStatus.IGNORED
        operation.updated_by_user_id = context.user.id
        await self.session.flush()
        return operation
