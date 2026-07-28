"""Candidate matching for imported rows that may represent transfers."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.import_review.domain.posting import raw_transaction_effective_account_id
from app.features.import_review.repository import ImportReviewRepository
from app.features.imports.models import RawTransaction
from app.features.imports.repository import ImportRepository
from app.features.ledger.models import MoneyEntry, Operation


@dataclass(frozen=True)
class TransferSuggestion:
    raw_transaction: RawTransaction
    day_distance: int


@dataclass(frozen=True)
class ExistingTransferSuggestion:
    operation: Operation
    account_entry: MoneyEntry
    counterparty_entry: MoneyEntry | None
    day_distance: int


class TransferSuggestionUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.imports = ImportRepository(session)
        self.review_repository = ImportReviewRepository(session)

    async def list_for_document(
        self,
        *,
        workspace_id: UUID,
        raw_transactions: list[RawTransaction],
    ) -> dict[UUID, list[TransferSuggestion]]:
        candidates = await self.imports.list_transfer_candidate_raw_transactions_for_sources(
            workspace_id=workspace_id,
            raw_transactions=raw_transactions,
        )
        suggestions: dict[UUID, list[TransferSuggestion]] = {}
        for raw_transaction in raw_transactions:
            matching_candidates = [
                candidate
                for candidate in candidates
                if self._raw_rows_can_match(raw_transaction, candidate)
            ]
            if matching_candidates:
                suggestions[raw_transaction.id] = [
                    self._suggestion_from_pair(raw_transaction, candidate)
                    for candidate in matching_candidates
                ]
        return suggestions

    async def list_existing_manual_for_document(
        self,
        *,
        workspace_id: UUID,
        raw_transactions: list[RawTransaction],
    ) -> dict[UUID, list[ExistingTransferSuggestion]]:
        candidates = (
            await self.review_repository.list_manual_transfer_candidates_for_raw_transactions(
                workspace_id=workspace_id,
                raw_transactions=raw_transactions,
            )
        )
        suggestions: dict[UUID, list[ExistingTransferSuggestion]] = {}
        for raw_transaction in raw_transactions:
            if raw_transaction.linked_operation_id is not None:
                continue
            raw_suggestions = [
                suggestion
                for candidate in candidates
                if (
                    suggestion := self._existing_suggestion_from_operation(
                        raw_transaction,
                        candidate,
                    )
                )
                is not None
            ]
            if raw_suggestions:
                suggestions[raw_transaction.id] = raw_suggestions
        return suggestions

    @staticmethod
    def _raw_rows_can_match(
        raw_transaction: RawTransaction,
        candidate: RawTransaction,
        day_window: int = 3,
    ) -> bool:
        source_account_id = raw_transaction_effective_account_id(raw_transaction)
        candidate_account_id = raw_transaction_effective_account_id(candidate)
        return (
            raw_transaction.linked_operation_id is None
            and source_account_id is not None
            and candidate_account_id is not None
            and source_account_id != candidate_account_id
            and raw_transaction.amount is not None
            and candidate.amount == -raw_transaction.amount
            and raw_transaction.currency is not None
            and candidate.currency == raw_transaction.currency
            and raw_transaction.operation_date is not None
            and candidate.operation_date is not None
            and abs((candidate.operation_date - raw_transaction.operation_date).days) <= day_window
        )

    @staticmethod
    def _suggestion_from_pair(
        raw_transaction: RawTransaction,
        candidate: RawTransaction,
    ) -> TransferSuggestion:
        if raw_transaction.operation_date and candidate.operation_date:
            day_distance = abs((candidate.operation_date - raw_transaction.operation_date).days)
        else:
            day_distance = 0
        return TransferSuggestion(raw_transaction=candidate, day_distance=day_distance)

    @staticmethod
    def _existing_suggestion_from_operation(
        raw_transaction: RawTransaction,
        operation: Operation,
        day_window: int = 3,
    ) -> ExistingTransferSuggestion | None:
        account_id = raw_transaction_effective_account_id(raw_transaction)
        if (
            account_id is None
            or raw_transaction.operation_date is None
            or abs((operation.operation_date - raw_transaction.operation_date).days) > day_window
            or any(
                raw_transaction_effective_account_id(linked_raw) == account_id
                for linked_raw in operation.raw_transactions
            )
        ):
            return None
        account_entry = next(
            (
                entry
                for entry in operation.money_entries
                if (
                    entry.account_id == account_id
                    and entry.amount == raw_transaction.amount
                    and entry.currency == raw_transaction.currency
                )
            ),
            None,
        )
        if account_entry is None:
            return None
        counterparty_entry = next(
            (entry for entry in operation.money_entries if entry.account_id != account_id),
            None,
        )
        day_distance = abs((operation.operation_date - raw_transaction.operation_date).days)
        return ExistingTransferSuggestion(
            operation=operation,
            account_entry=account_entry,
            counterparty_entry=counterparty_entry,
            day_distance=day_distance,
        )
