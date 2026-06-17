from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.models import RawTransaction
from app.features.imports.repository import ImportRepository


@dataclass(frozen=True)
class TransferSuggestion:
    raw_transaction: RawTransaction
    day_distance: int


class TransferSuggestionUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.imports = ImportRepository(session)

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
