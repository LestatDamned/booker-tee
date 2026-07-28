from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.application.review.status import RawTransactionReviewStatusUseCase
from app.features.ledger.application.raw_transaction_posting import RawTransactionPoster
from app.features.workspaces.service import WorkspaceContext


@dataclass(frozen=True)
class RawTransactionReviewCommand:
    document_id: UUID
    raw_transaction_id: UUID
    action: str
    counterparty_account_id: UUID | None = None
    matched_raw_transaction_id: UUID | None = None
    matched_operation_id: UUID | None = None


@dataclass(frozen=True)
class RawTransactionReviewResult:
    updated_raw_transaction_ids: frozenset[UUID] = frozenset()


class RawTransactionReviewer:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.status_review = RawTransactionReviewStatusUseCase(session)
        self.ledger = RawTransactionPoster(session)

    async def handle(
        self,
        *,
        context: WorkspaceContext,
        command: RawTransactionReviewCommand,
    ) -> RawTransactionReviewResult:
        if command.action == "transfer":
            return await self._post_transfer(context, command)

        await self.status_review.set_status(
            workspace_id=context.workspace.id,
            document_id=command.document_id,
            raw_transaction_id=command.raw_transaction_id,
            action=command.action,
        )
        return RawTransactionReviewResult()

    async def _post_transfer(
        self,
        context: WorkspaceContext,
        command: RawTransactionReviewCommand,
    ) -> RawTransactionReviewResult:
        if (
            command.matched_raw_transaction_id is not None
            and command.matched_operation_id is not None
        ):
            raise ValueError("Choose either a paired raw row or an existing transfer.")
        if command.matched_operation_id is not None:
            await self.ledger.link_raw_transaction_to_existing_transfer(
                context=context,
                document_id=command.document_id,
                raw_transaction_id=command.raw_transaction_id,
                operation_id=command.matched_operation_id,
            )
            return RawTransactionReviewResult()

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
