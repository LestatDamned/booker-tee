from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.models import OperationType


class PostingAccount(Protocol):
    id: UUID
    currency: str


@dataclass(frozen=True)
class TransferAmounts:
    source_amount: Decimal
    destination_amount: Decimal

    @classmethod
    def for_manual_transfer(
        cls,
        *,
        source_account_id: UUID,
        destination_account_id: UUID,
        amount: Decimal,
    ) -> "TransferAmounts":
        ensure_distinct_accounts(source_account_id, destination_account_id)
        normalized_amount = normalize_positive_money(amount)
        return cls(
            source_amount=-normalized_amount,
            destination_amount=normalized_amount,
        )

    def ensure_balanced(self) -> None:
        ensure_balanced_transfer(self.source_amount, self.destination_amount)


def operation_type_for_amount(amount: Decimal) -> OperationType:
    if amount > Decimal("0.00"):
        return OperationType.INCOME
    if amount < Decimal("0.00"):
        return OperationType.EXPENSE
    raise LedgerPostingError("Zero amount raw transactions require manual review.")


def affects_profit_for_operation_type(operation_type: OperationType) -> bool:
    return operation_type in {OperationType.INCOME, OperationType.EXPENSE}


def manual_income_expense_amount(operation_type: OperationType, amount: Decimal) -> Decimal:
    normalized_amount = normalize_positive_money(amount)
    if operation_type == OperationType.INCOME:
        return normalized_amount
    if operation_type == OperationType.EXPENSE:
        return -normalized_amount
    raise LedgerPostingError("Manual operation must be income or expense.")


def build_manual_transfer_amounts(
    *,
    source_account_id: UUID,
    destination_account_id: UUID,
    amount: Decimal,
) -> TransferAmounts:
    return TransferAmounts.for_manual_transfer(
        source_account_id=source_account_id,
        destination_account_id=destination_account_id,
        amount=amount,
    )


def ensure_distinct_accounts(source_account_id: UUID, destination_account_id: UUID) -> None:
    if source_account_id == destination_account_id:
        raise LedgerPostingError("Transfer accounts must be different.")


def normalize_positive_money(amount: Decimal) -> Decimal:
    normalized_amount = amount.quantize(Decimal("0.01"))
    if normalized_amount <= Decimal("0.00"):
        raise LedgerPostingError("Amount must be positive.")
    return normalized_amount


def ensure_same_currency(first_account: PostingAccount, second_account: PostingAccount) -> None:
    if first_account.currency != second_account.currency:
        raise LedgerPostingError("Cross-currency transfers are not supported in the MVP.")


def require_uuid(value: UUID | None, message: str) -> UUID:
    if value is None:
        raise LedgerPostingError(message)
    return value


def ensure_balanced_transfer(first_amount: Decimal, second_amount: Decimal) -> None:
    if (first_amount + second_amount).quantize(Decimal("0.01")) != Decimal("0.00"):
        raise LedgerPostingError("Transfer entries must balance to zero.")
