"""Apply transaction rules when requested from the import review workflow."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.import_review.repository import ImportReviewRepository
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
        self._review_repository = ImportReviewRepository(session)
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
        document = await self._review_repository.get_document_for_workspace(
            context.workspace.id,
            document_id,
        )
        if document is None:
            raise ImportReviewRuleApplicationNotFoundError("Import review document was not found.")
        raw_transaction = next(
            (row for row in document.raw_transactions if row.id == item_id),
            None,
        )
        if raw_transaction is None:
            raise ImportReviewRuleApplicationNotFoundError("Import review item was not found.")
        await self._management.create_rule_from_raw_transaction(
            context=context,
            raw_transaction=raw_transaction,
            category_id=category_id,
            property_id=property_id,
            pattern=pattern,
        )
        return await self._application.apply_rules_to_raw_transactions(
            workspace_id=context.workspace.id,
            raw_transactions=document.raw_transactions,
        )


class ImportReviewRuleApplicationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.review_repository = ImportReviewRepository(session)
        self.rules = TransactionRuleApplicationUseCase(session)

    async def execute(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
    ) -> ImportReviewRuleApplicationResult:
        try:
            document = await self.review_repository.get_document_for_workspace(
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
