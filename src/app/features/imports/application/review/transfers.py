from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Protocol
from uuid import UUID

from app.features.accounts.models import Account
from app.features.import_review.domain.classification import resolve_review_classification
from app.features.imports.models import RawTransaction, UploadedDocument
from app.features.ledger.application.transfer_suggestions import (
    ExistingTransferSuggestion,
    TransferSuggestion,
)
from app.features.ledger.domain.types import OperationType


class ImportReviewTransferDirection(StrEnum):
    SOURCE_TO_COUNTERPARTY = "source_to_counterparty"
    COUNTERPARTY_TO_SOURCE = "counterparty_to_source"


@dataclass(frozen=True)
class ImportReviewTransferAccountDto:
    id: UUID
    name: str
    currency: str


@dataclass(frozen=True)
class ImportReviewRawTransferCandidateDto:
    item_id: UUID
    document_id: UUID
    row_index: int
    operation_date: date | None
    description: str | None
    amount: Decimal
    currency: str
    account: ImportReviewTransferAccountDto
    day_distance: int


@dataclass(frozen=True)
class ImportReviewExistingTransferCandidateDto:
    operation_id: UUID
    operation_date: date
    description: str | None
    amount: Decimal
    currency: str
    counterparty_account: ImportReviewTransferAccountDto | None
    day_distance: int


@dataclass(frozen=True)
class ImportReviewTransferOptionsDto:
    direction: ImportReviewTransferDirection | None
    ordinary_operation_type: Literal[OperationType.INCOME, OperationType.EXPENSE] | None
    source_account: ImportReviewTransferAccountDto | None
    counterparty_account: ImportReviewTransferAccountDto | None
    accounts: tuple[ImportReviewTransferAccountDto, ...]
    raw_row_candidates: tuple[ImportReviewRawTransferCandidateDto, ...]
    existing_operation_candidates: tuple[ImportReviewExistingTransferCandidateDto, ...]


EMPTY_TRANSFER_OPTIONS = ImportReviewTransferOptionsDto(
    direction=None,
    ordinary_operation_type=None,
    source_account=None,
    counterparty_account=None,
    accounts=(),
    raw_row_candidates=(),
    existing_operation_candidates=(),
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
    ) -> ImportReviewTransferAccountDto | None:
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
    ) -> ImportReviewTransferAccountDto | None:
        if account is None or account.workspace_id != workspace_id:
            return None
        return self._account(account)

    @staticmethod
    def _account(account: Account) -> ImportReviewTransferAccountDto:
        return ImportReviewTransferAccountDto(
            id=account.id,
            name=account.name,
            currency=account.currency,
        )

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
