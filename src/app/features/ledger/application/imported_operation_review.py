from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.ledger.application.commands import UpdateImportedOperationReviewFieldsCommand
from app.features.ledger.application.ledger_reference_resolver import LedgerReferenceResolver
from app.features.ledger.domain.text import clean_description
from app.features.ledger.domain.types import OperationSource
from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.models import Operation
from app.features.ledger.repository import LedgerRepository
from app.features.workspaces.service import WorkspaceContext


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
            operation.status = command.status
            operation.updated_by_user_id = context.user.id
            await self.session.commit()
            return operation
        except Exception:
            await self.session.rollback()
            raise

    async def _get_imported_operation(self, workspace_id: UUID, operation_id: UUID) -> Operation:
        operation = await self.ledger.get_operation_for_workspace(workspace_id, operation_id)
        if operation is None:
            raise LedgerPostingError("Imported operation was not found.")
        if operation.source != OperationSource.BANK_PDF:
            raise LedgerPostingError("Only imported bank PDF operations can be changed here.")
        return operation
