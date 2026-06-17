from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.features.imports.models import RawTransactionStatus
from app.features.ledger.domain.money import (
    PostingAccount,
    affects_profit_for_operation_type,
    operation_type_for_amount,
)
from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.models import OperationType


class PostableRawTransaction(Protocol):
    id: UUID
    status: RawTransactionStatus
    linked_operation_id: UUID | None
    account_id: UUID | None
    amount: Decimal | None
    currency: str | None
    operation_date: date | None
    posting_date: date | None
    description_normalized: str | None
    description_raw: str | None
    balance_after: Decimal | None
    dedupe_hash: str | None


class RawTransactionSuggestionState(Protocol):
    suggested_by_rule_id: UUID | None


@dataclass(frozen=True)
class LedgerPostingPlan:
    operation_type: OperationType
    affects_profit: bool
    amount: Decimal
    currency: str
    operation_date: date
    posting_date: date | None
    description: str | None
    balance_after: Decimal | None

    @classmethod
    def from_raw_transaction(
        cls,
        raw_transaction: PostableRawTransaction,
        account: PostingAccount,
    ) -> "LedgerPostingPlan":
        if raw_transaction.linked_operation_id is not None:
            raise LedgerPostingError("Raw transaction row is already linked to an operation.")
        if raw_transaction.status not in POSTABLE_RAW_STATUSES:
            raise LedgerPostingError(
                f"Raw transaction status cannot be posted: {raw_transaction.status}"
            )
        if raw_transaction.account_id != account.id:
            raise LedgerPostingError("Raw transaction account does not match selected account.")
        if raw_transaction.amount is None:
            raise LedgerPostingError("Raw transaction row has no normalized amount.")
        if raw_transaction.currency is None:
            raise LedgerPostingError("Raw transaction row has no normalized currency.")
        if raw_transaction.currency != account.currency:
            raise LedgerPostingError("Raw transaction currency does not match account currency.")
        if raw_transaction.operation_date is None:
            raise LedgerPostingError("Raw transaction row has no normalized operation date.")

        operation_type = operation_type_for_amount(raw_transaction.amount)
        return cls(
            operation_type=operation_type,
            affects_profit=affects_profit_for_operation_type(operation_type),
            amount=raw_transaction.amount,
            currency=raw_transaction.currency,
            operation_date=raw_transaction.operation_date,
            posting_date=raw_transaction.posting_date,
            description=raw_transaction.description_normalized or raw_transaction.description_raw,
            balance_after=raw_transaction.balance_after,
        )


POSTABLE_RAW_STATUSES = {
    RawTransactionStatus.NORMALIZED,
    RawTransactionStatus.SUGGESTED,
    RawTransactionStatus.MATCHED,
}
TRANSFER_POSTABLE_RAW_STATUSES = {
    RawTransactionStatus.NORMALIZED,
    RawTransactionStatus.SUGGESTED,
    RawTransactionStatus.MATCHED,
    RawTransactionStatus.NEEDS_REVIEW,
    RawTransactionStatus.POSSIBLE_DUPLICATE,
}


def build_ledger_posting_plan(
    raw_transaction: PostableRawTransaction,
    account: PostingAccount,
) -> LedgerPostingPlan:
    return LedgerPostingPlan.from_raw_transaction(raw_transaction, account)


def ensure_matched_transfer_account(
    matched_raw_transaction: PostableRawTransaction,
    selected_account_id: UUID | None,
) -> None:
    if (
        selected_account_id is not None
        and matched_raw_transaction.account_id != selected_account_id
    ):
        raise LedgerPostingError(
            "Matched transfer row does not belong to the selected transfer account."
        )


def require_raw_amount(raw_transaction: PostableRawTransaction) -> Decimal:
    if raw_transaction.amount is None:
        raise LedgerPostingError("Raw transaction row has no normalized amount.")
    return raw_transaction.amount


def require_raw_operation_date(raw_transaction: PostableRawTransaction) -> date:
    if raw_transaction.operation_date is None:
        raise LedgerPostingError("Raw transaction row has no normalized operation date.")
    return raw_transaction.operation_date


def ensure_raw_transaction_can_post_as_transfer(
    raw_transaction: PostableRawTransaction,
) -> None:
    if raw_transaction.linked_operation_id is not None:
        raise LedgerPostingError("Raw transaction row is already linked to an operation.")
    if raw_transaction.status not in TRANSFER_POSTABLE_RAW_STATUSES:
        raise LedgerPostingError(
            f"Raw transaction status cannot be posted as transfer: {raw_transaction.status}"
        )
    if raw_transaction.currency is None:
        raise LedgerPostingError("Raw transaction row has no normalized currency.")


def restored_raw_status_after_unlink(
    raw_transaction: RawTransactionSuggestionState,
) -> RawTransactionStatus:
    if raw_transaction.suggested_by_rule_id is not None:
        return RawTransactionStatus.SUGGESTED
    return RawTransactionStatus.NORMALIZED
