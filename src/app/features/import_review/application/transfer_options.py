"""Transfer candidates and options shown during import review."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import Account
from app.features.import_review.domain.classification import resolve_review_classification
from app.features.import_review.domain.posting import raw_transaction_effective_account_id
from app.features.import_review.repository import ImportReviewRepository
from app.features.import_review.schemas.review import (
    ImportReviewAccountDto,
    ImportReviewExistingTransferCandidateDto,
    ImportReviewRawTransferCandidateDto,
    ImportReviewTransferDirection,
    ImportReviewTransferOptionsDto,
)
from app.features.imports.models import RawTransaction, UploadedDocument
from app.features.ledger.domain.types import OperationType
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
        self.review_repository = ImportReviewRepository(session)

    async def list_for_document(
        self,
        *,
        workspace_id: UUID,
        raw_transactions: list[RawTransaction],
    ) -> dict[UUID, list[TransferSuggestion]]:
        candidates = (
            await self.review_repository.list_transfer_candidate_raw_transactions_for_sources(
                workspace_id=workspace_id,
                raw_transactions=raw_transactions,
            )
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


class ImportReviewAccountSource(Protocol):
    async def list_active_accounts(self, workspace_id: UUID) -> list[Account]: ...


class ImportReviewTransferSuggestionSource(Protocol):
    async def list_for_document(
        self,
        *,
        workspace_id: UUID,
        raw_transactions: list[RawTransaction],
    ) -> dict[UUID, list[TransferSuggestion]]: ...

    async def list_existing_manual_for_document(
        self,
        *,
        workspace_id: UUID,
        raw_transactions: list[RawTransaction],
    ) -> dict[UUID, list[ExistingTransferSuggestion]]: ...


class ImportReviewTransferReader:
    def __init__(
        self,
        accounts: ImportReviewAccountSource,
        suggestions: ImportReviewTransferSuggestionSource,
    ) -> None:
        self._accounts = accounts
        self._suggestions = suggestions

    async def read_for_document(
        self,
        *,
        workspace_id: UUID,
        document: UploadedDocument,
    ) -> dict[UUID, ImportReviewTransferOptionsDto]:
        accounts = await self._accounts.list_active_accounts(workspace_id)
        raw_suggestions = await self._suggestions.list_for_document(
            workspace_id=workspace_id,
            raw_transactions=document.raw_transactions,
        )
        existing_suggestions = await self._suggestions.list_existing_manual_for_document(
            workspace_id=workspace_id,
            raw_transactions=document.raw_transactions,
        )
        return {
            row.id: self._options(
                row,
                workspace_id=workspace_id,
                document=document,
                accounts=accounts,
                raw_suggestions=raw_suggestions.get(row.id, []),
                existing_suggestions=existing_suggestions.get(row.id, []),
            )
            for row in document.raw_transactions
        }

    def _options(
        self,
        row: RawTransaction,
        *,
        workspace_id: UUID,
        document: UploadedDocument,
        accounts: list[Account],
        raw_suggestions: list[TransferSuggestion],
        existing_suggestions: list[ExistingTransferSuggestion],
    ) -> ImportReviewTransferOptionsDto:
        source_account_id = row.account_id or document.account_id
        source_account = row.account or document.account
        currency = row.currency
        eligible_accounts = tuple(
            self._account(account)
            for account in accounts
            if account.workspace_id == workspace_id
            and account.id != source_account_id
            and currency is not None
            and account.currency == currency
        )
        return ImportReviewTransferOptionsDto(
            direction=self._direction(row.amount),
            ordinary_operation_type=self._ordinary_operation_type(row.amount),
            source_account=self._workspace_account(source_account, workspace_id),
            counterparty_account=self._confirmed_counterparty_account(
                row,
                workspace_id=workspace_id,
                source_account_id=source_account_id,
            ),
            accounts=eligible_accounts,
            raw_row_candidates=tuple(
                candidate
                for suggestion in raw_suggestions
                if (candidate := self._raw_candidate(suggestion)) is not None
            ),
            existing_operation_candidates=tuple(
                self._existing_candidate(suggestion) for suggestion in existing_suggestions
            ),
        )

    def _raw_candidate(
        self,
        suggestion: TransferSuggestion,
    ) -> ImportReviewRawTransferCandidateDto | None:
        row = suggestion.raw_transaction
        account = row.account or row.uploaded_document.account
        if row.amount is None or row.currency is None or account is None:
            return None
        return ImportReviewRawTransferCandidateDto(
            item_id=row.id,
            document_id=row.uploaded_document_id,
            row_index=row.row_index,
            operation_date=row.operation_date,
            description=row.description_normalized or row.description_raw,
            amount=row.amount,
            currency=row.currency,
            account=self._account(account),
            day_distance=suggestion.day_distance,
        )

    def _existing_candidate(
        self,
        suggestion: ExistingTransferSuggestion,
    ) -> ImportReviewExistingTransferCandidateDto:
        counterparty = suggestion.counterparty_entry
        return ImportReviewExistingTransferCandidateDto(
            operation_id=suggestion.operation.id,
            operation_date=suggestion.operation.operation_date,
            description=suggestion.operation.description,
            amount=suggestion.account_entry.amount,
            currency=suggestion.account_entry.currency,
            counterparty_account=(
                self._account(counterparty.account) if counterparty is not None else None
            ),
            day_distance=suggestion.day_distance,
        )

    def _confirmed_counterparty_account(
        self,
        row: RawTransaction,
        *,
        workspace_id: UUID,
        source_account_id: UUID | None,
    ) -> ImportReviewAccountDto | None:
        operation = getattr(row, "linked_operation", None)
        if (
            operation is None
            or operation.type is not OperationType.TRANSFER
            or operation.workspace_id != workspace_id
            or source_account_id is None
        ):
            return None
        counterparty_entry = next(
            (
                entry
                for entry in operation.money_entries
                if entry.workspace_id == workspace_id and entry.account_id != source_account_id
            ),
            None,
        )
        if counterparty_entry is None:
            return None
        return self._workspace_account(counterparty_entry.account, workspace_id)

    def _workspace_account(
        self,
        account: Account | None,
        workspace_id: UUID,
    ) -> ImportReviewAccountDto | None:
        if account is None or account.workspace_id != workspace_id:
            return None
        return self._account(account)

    @staticmethod
    def _account(account: Account) -> ImportReviewAccountDto:
        return ImportReviewAccountDto.model_validate(account)

    @staticmethod
    def _direction(amount: Decimal | None) -> ImportReviewTransferDirection | None:
        if amount is None or amount == 0:
            return None
        if amount < 0:
            return ImportReviewTransferDirection.SOURCE_TO_COUNTERPARTY
        return ImportReviewTransferDirection.COUNTERPARTY_TO_SOURCE

    @staticmethod
    def _ordinary_operation_type(
        amount: Decimal | None,
    ) -> Literal[OperationType.INCOME, OperationType.EXPENSE] | None:
        operation_type = resolve_review_classification(
            explicit_operation_type=None,
            suggested_operation_type=None,
            amount=amount,
        ).operation_type
        if operation_type is OperationType.INCOME:
            return OperationType.INCOME
        if operation_type is OperationType.EXPENSE:
            return OperationType.EXPENSE
        return None
