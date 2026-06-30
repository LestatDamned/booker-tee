from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.models import RawTransaction
from app.features.imports.repository import ImportRepository
from app.features.ledger.models import MoneyEntry, Operation
from app.features.ledger.repository import LedgerRepository


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
        self.ledger = LedgerRepository(session)

    async def list_for_document(
        self,
        *,
        workspace_id: UUID,
        raw_transactions: list[RawTransaction],
    ) -> dict[UUID, list[TransferSuggestion]]:
        suggestions: dict[UUID, list[TransferSuggestion]] = {}
        for raw_transaction in raw_transactions:
            if raw_transaction.linked_operation_id is not None:
                continue

            candidates = await self.imports.list_transfer_candidate_raw_transactions(
                workspace_id=workspace_id,
                raw_transaction=raw_transaction,
            )
            if candidates:
                suggestions[raw_transaction.id] = [
                    self._suggestion_from_pair(raw_transaction, candidate)
                    for candidate in candidates
                ]
        return suggestions

    async def list_existing_manual_for_document(
        self,
        *,
        workspace_id: UUID,
        raw_transactions: list[RawTransaction],
    ) -> dict[UUID, list[ExistingTransferSuggestion]]:
        suggestions: dict[UUID, list[ExistingTransferSuggestion]] = {}
        for raw_transaction in raw_transactions:
            if raw_transaction.linked_operation_id is not None:
                continue

            candidates = await self.ledger.list_manual_transfer_candidates_for_raw_transaction(
                workspace_id=workspace_id,
                raw_transaction=raw_transaction,
            )
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
    ) -> ExistingTransferSuggestion | None:
        account_entry = next(
            (
                entry
                for entry in operation.money_entries
                if (
                    entry.account_id == raw_transaction.account_id
                    and entry.amount == raw_transaction.amount
                    and entry.currency == raw_transaction.currency
                )
            ),
            None,
        )
        if account_entry is None:
            return None
        counterparty_entry = next(
            (
                entry
                for entry in operation.money_entries
                if entry.account_id != raw_transaction.account_id
            ),
            None,
        )
        if raw_transaction.operation_date:
            day_distance = abs((operation.operation_date - raw_transaction.operation_date).days)
        else:
            day_distance = 0
        return ExistingTransferSuggestion(
            operation=operation,
            account_entry=account_entry,
            counterparty_entry=counterparty_entry,
            day_distance=day_distance,
        )
