"""Existing manual operations that may explain imported bank rows."""

from typing import Protocol
from uuid import UUID

from app.features.import_review.domain.posting import raw_transaction_effective_account_id
from app.features.import_review.schemas.review import (
    ImportReviewExistingOperationCandidateDto,
)
from app.features.imports.models import RawTransaction, UploadedDocument
from app.features.imports.statements.types import RawTransactionStatus
from app.features.ledger.models import MoneyEntry, Operation


class ExistingOperationCandidateSource(Protocol):
    async def list_manual_income_expense_candidates_for_raw_transactions(
        self,
        *,
        workspace_id: UUID,
        raw_transactions: list[RawTransaction],
        day_window: int = 3,
    ) -> list[Operation]: ...


class ExistingOperationCandidateReader:
    def __init__(self, source: ExistingOperationCandidateSource) -> None:
        self._source = source

    async def read_for_document(
        self,
        *,
        workspace_id: UUID,
        document: UploadedDocument,
    ) -> dict[UUID, tuple[ImportReviewExistingOperationCandidateDto, ...]]:
        operations = await self._source.list_manual_income_expense_candidates_for_raw_transactions(
            workspace_id=workspace_id,
            raw_transactions=document.raw_transactions,
        )
        return {
            row.id: tuple(candidates)
            for row in document.raw_transactions
            if (
                candidates := sorted(
                    filter(None, (self._candidate(row, operation) for operation in operations)),
                    key=lambda candidate: (candidate.day_distance, candidate.operation_date),
                )
            )
        }

    @staticmethod
    def _candidate(
        row: RawTransaction,
        operation: Operation,
        day_window: int = 3,
    ) -> ImportReviewExistingOperationCandidateDto | None:
        account_id = raw_transaction_effective_account_id(row)
        if (
            row.linked_operation_id is not None
            or row.status
            not in {
                RawTransactionStatus.NORMALIZED,
                RawTransactionStatus.SUGGESTED,
                RawTransactionStatus.NEEDS_REVIEW,
                RawTransactionStatus.MATCHED,
                RawTransactionStatus.POSSIBLE_DUPLICATE,
            }
            or account_id is None
            or row.operation_date is None
            or abs((operation.operation_date - row.operation_date).days) > day_window
            or any(
                raw_transaction_effective_account_id(linked_row) == account_id
                for linked_row in operation.raw_transactions
            )
        ):
            return None
        entry: MoneyEntry | None = next(
            (
                item
                for item in operation.money_entries
                if item.account_id == account_id
                and item.amount == row.amount
                and item.currency == row.currency
            ),
            None,
        )
        if entry is None:
            return None
        return ImportReviewExistingOperationCandidateDto(
            operation_id=operation.id,
            operation_date=operation.operation_date,
            description=operation.description,
            amount=entry.amount,
            currency=entry.currency,
            category_name=operation.category.name if operation.category is not None else None,
            day_distance=abs((operation.operation_date - row.operation_date).days),
        )
