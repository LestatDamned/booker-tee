"""Apply transaction rules when requested from the import review workflow."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.repository import ImportRepository
from app.features.transaction_rules.application.rule_application import (
    RuleApplicationSummary,
    TransactionRuleApplicationUseCase,
)
from app.features.transaction_rules.application.rule_management import (
    TransactionRuleManagementUseCase,
)
from app.features.workspaces.service import WorkspaceContext


class ImportReviewRuleApplicationNotFoundError(ValueError):
    """Raised when the review document is outside the current workspace."""


@dataclass(frozen=True)
class ImportReviewRuleApplicationResult:
    checked_count: int
    suggested_count: int
    updated_item_ids: frozenset[UUID]


class ImportReviewRuleCreator:
    def __init__(self, session: AsyncSession) -> None:
        self._management = TransactionRuleManagementUseCase(session)
        self._application = TransactionRuleApplicationUseCase(session)

    async def create_and_apply(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
        item_id: UUID,
        category_id: UUID,
        property_id: UUID | None,
        pattern: str | None,
    ) -> RuleApplicationSummary:
        await self._management.create_rule_from_raw_confirmation(
            context=context,
            document_id=document_id,
            raw_transaction_id=item_id,
            category_id=category_id,
            property_id=property_id,
            pattern=pattern,
        )
        return await self._application.apply_rules_to_document(
            workspace_id=context.workspace.id,
            document_id=document_id,
        )


class ImportReviewRuleApplicationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.imports = ImportRepository(session)
        self.rules = TransactionRuleApplicationUseCase(session)

    async def execute(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
    ) -> ImportReviewRuleApplicationResult:
        try:
            document = await self.imports.get_document_for_workspace(
                workspace_id,
                document_id,
            )
            if document is None:
                raise ImportReviewRuleApplicationNotFoundError(
                    "Import review document was not found."
                )
            summary = await self.rules.apply_rules_to_raw_transactions(
                workspace_id=workspace_id,
                raw_transactions=document.raw_transactions,
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        return ImportReviewRuleApplicationResult(
            checked_count=summary.checked_count,
            suggested_count=summary.suggested_count,
            updated_item_ids=summary.updated_raw_transaction_ids,
        )
