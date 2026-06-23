from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.imports.application.review.status import RawTransactionReviewStatusUseCase
from app.features.ledger.service import LedgerPostingService
from app.features.transaction_rules.application.rule_application import (
    TransactionRuleApplicationUseCase,
)
from app.features.transaction_rules.application.rule_management import (
    TransactionRuleManagementUseCase,
)
from app.features.workspaces.service import WorkspaceContext


@dataclass(frozen=True)
class RawTransactionReviewCommand:
    document_id: UUID
    raw_transaction_id: UUID
    action: str
    category_id: UUID | None = None
    property_id: UUID | None = None
    counterparty_account_id: UUID | None = None
    matched_raw_transaction_id: UUID | None = None
    remember_rule: bool = False
    rule_pattern: str | None = None


@dataclass(frozen=True)
class RawTransactionReviewResult:
    updated_raw_transaction_ids: frozenset[UUID] = frozenset()


class RawTransactionReviewUseCase:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.status_review = RawTransactionReviewStatusUseCase(session)
        self.ledger = LedgerPostingService(session)
        self.rules = TransactionRuleManagementUseCase(session)
        self.rule_application = TransactionRuleApplicationUseCase(session)

    async def handle(
        self,
        *,
        context: WorkspaceContext,
        command: RawTransactionReviewCommand,
    ) -> RawTransactionReviewResult:
        if command.action == "confirm":
            return await self._confirm_transaction(context, command)

        if command.action == "transfer":
            return await self._post_transfer(context, command)

        await self.status_review.set_status(
            workspace_id=context.workspace.id,
            document_id=command.document_id,
            raw_transaction_id=command.raw_transaction_id,
            action=command.action,
        )
        return RawTransactionReviewResult()

    async def _confirm_transaction(
        self,
        context: WorkspaceContext,
        command: RawTransactionReviewCommand,
    ) -> RawTransactionReviewResult:
        await self.ledger.post_raw_transaction(
            context=context,
            document_id=command.document_id,
            raw_transaction_id=command.raw_transaction_id,
            category_id=command.category_id,
            property_id=command.property_id,
        )
        if command.remember_rule and command.category_id is not None:
            await self.rules.create_rule_from_raw_confirmation(
                context=context,
                document_id=command.document_id,
                raw_transaction_id=command.raw_transaction_id,
                category_id=command.category_id,
                property_id=command.property_id,
                pattern=command.rule_pattern,
            )
            summary = await self.rule_application.apply_rules_to_document(
                workspace_id=context.workspace.id,
                document_id=command.document_id,
            )
            return RawTransactionReviewResult(
                updated_raw_transaction_ids=summary.updated_raw_transaction_ids,
            )
        return RawTransactionReviewResult()

    async def _post_transfer(
        self,
        context: WorkspaceContext,
        command: RawTransactionReviewCommand,
    ) -> RawTransactionReviewResult:
        await self.ledger.post_raw_transaction_as_transfer(
            context=context,
            document_id=command.document_id,
            raw_transaction_id=command.raw_transaction_id,
            counterparty_account_id=command.counterparty_account_id,
            matched_raw_transaction_id=command.matched_raw_transaction_id,
        )
        if command.matched_raw_transaction_id is None:
            return RawTransactionReviewResult()
        return RawTransactionReviewResult(
            updated_raw_transaction_ids=frozenset({command.matched_raw_transaction_id}),
        )
