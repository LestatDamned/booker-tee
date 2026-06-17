from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.imports.application.review_status import RawTransactionReviewStatusUseCase
from app.features.ledger.service import LedgerPostingService
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


class RawTransactionReviewUseCase:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.status_review = RawTransactionReviewStatusUseCase(session)
        self.ledger = LedgerPostingService(session)
        self.rules = TransactionRuleManagementUseCase(session)

    async def handle(
        self,
        *,
        context: WorkspaceContext,
        command: RawTransactionReviewCommand,
    ) -> None:
        if command.action == "confirm":
            await self._confirm_transaction(context, command)
            return

        if command.action == "transfer":
            await self._post_transfer(context, command)
            return

        await self.status_review.set_status(
            workspace_id=context.workspace.id,
            document_id=command.document_id,
            raw_transaction_id=command.raw_transaction_id,
            action=command.action,
        )

    async def _confirm_transaction(
        self,
        context: WorkspaceContext,
        command: RawTransactionReviewCommand,
    ) -> None:
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

    async def _post_transfer(
        self,
        context: WorkspaceContext,
        command: RawTransactionReviewCommand,
    ) -> None:
        await self.ledger.post_raw_transaction_as_transfer(
            context=context,
            document_id=command.document_id,
            raw_transaction_id=command.raw_transaction_id,
            counterparty_account_id=command.counterparty_account_id,
            matched_raw_transaction_id=command.matched_raw_transaction_id,
        )
