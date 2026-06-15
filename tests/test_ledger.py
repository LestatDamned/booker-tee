from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.features.imports.models import RawTransactionStatus
from app.features.ledger.models import OperationType
from app.features.ledger.service import (
    LedgerPostingError,
    affects_profit_for_operation_type,
    build_ledger_posting_plan,
    build_manual_transfer_amounts,
    ensure_balanced_transfer,
    ensure_matched_transfer_account,
    ensure_raw_transaction_can_post_as_transfer,
    manual_income_expense_amount,
    operation_type_for_amount,
    restored_raw_status_after_unlink,
)


@dataclass(frozen=True)
class RawTransactionStub:
    status: RawTransactionStatus
    account_id: UUID | None
    amount: Decimal | None
    id: UUID = uuid4()
    currency: str | None = "RUB"
    operation_date: date | None = date(2026, 5, 29)
    linked_operation_id: UUID | None = None
    posting_date: date | None = None
    description_normalized: str | None = "Rent"
    description_raw: str | None = None
    balance_after: Decimal | None = None
    dedupe_hash: str | None = "hash"
    suggested_by_rule_id: UUID | None = None


@dataclass(frozen=True)
class AccountStub:
    id: UUID
    currency: str = "RUB"


def test_operation_type_for_amount_maps_income_and_expense() -> None:
    assert operation_type_for_amount(Decimal("100.00")) == OperationType.INCOME
    assert operation_type_for_amount(Decimal("-100.00")) == OperationType.EXPENSE
    assert affects_profit_for_operation_type(OperationType.INCOME) is True
    assert affects_profit_for_operation_type(OperationType.EXPENSE) is True
    assert affects_profit_for_operation_type(OperationType.TRANSFER) is False


def test_operation_type_for_amount_rejects_zero() -> None:
    with pytest.raises(LedgerPostingError):
        operation_type_for_amount(Decimal("0.00"))


def test_manual_income_expense_amount_normalizes_signs() -> None:
    assert manual_income_expense_amount(OperationType.INCOME, Decimal("100")) == Decimal("100.00")
    assert manual_income_expense_amount(OperationType.EXPENSE, Decimal("100")) == Decimal("-100.00")


def test_manual_transfer_amounts_create_balanced_entries() -> None:
    source_account_id = uuid4()
    destination_account_id = uuid4()

    amounts = build_manual_transfer_amounts(
        source_account_id=source_account_id,
        destination_account_id=destination_account_id,
        amount=Decimal("250.5"),
    )

    assert amounts.source_amount == Decimal("-250.50")
    assert amounts.destination_amount == Decimal("250.50")
    ensure_balanced_transfer(amounts.source_amount, amounts.destination_amount)


def test_manual_transfer_amounts_reject_same_account_and_non_positive_amount() -> None:
    account_id = uuid4()

    with pytest.raises(LedgerPostingError, match="different"):
        build_manual_transfer_amounts(
            source_account_id=account_id,
            destination_account_id=account_id,
            amount=Decimal("100.00"),
        )

    with pytest.raises(LedgerPostingError, match="positive"):
        build_manual_transfer_amounts(
            source_account_id=uuid4(),
            destination_account_id=uuid4(),
            amount=Decimal("0.00"),
        )


def test_ensure_balanced_transfer_rejects_unbalanced_entries() -> None:
    with pytest.raises(LedgerPostingError, match="balance"):
        ensure_balanced_transfer(Decimal("-10.00"), Decimal("9.99"))


def test_build_ledger_posting_plan_for_income_raw_row() -> None:
    account_id = uuid4()
    plan = build_ledger_posting_plan(
        RawTransactionStub(
            status=RawTransactionStatus.NORMALIZED,
            account_id=account_id,
            amount=Decimal("100.00"),
        ),
        AccountStub(id=account_id),
    )

    assert plan.operation_type == OperationType.INCOME
    assert plan.amount == Decimal("100.00")
    assert plan.affects_profit is True
    assert plan.description == "Rent"


def test_build_ledger_posting_plan_for_expense_raw_row() -> None:
    account_id = uuid4()
    plan = build_ledger_posting_plan(
        RawTransactionStub(
            status=RawTransactionStatus.MATCHED,
            account_id=account_id,
            amount=Decimal("-25.50"),
        ),
        AccountStub(id=account_id),
    )

    assert plan.operation_type == OperationType.EXPENSE
    assert plan.amount == Decimal("-25.50")


def test_build_ledger_posting_plan_blocks_already_linked_row() -> None:
    account_id = uuid4()
    with pytest.raises(LedgerPostingError, match="already linked"):
        build_ledger_posting_plan(
            RawTransactionStub(
                status=RawTransactionStatus.NORMALIZED,
                account_id=account_id,
                amount=Decimal("100.00"),
                linked_operation_id=uuid4(),
            ),
            AccountStub(id=account_id),
        )


def test_build_ledger_posting_plan_blocks_review_status() -> None:
    account_id = uuid4()
    with pytest.raises(LedgerPostingError, match="cannot be posted"):
        build_ledger_posting_plan(
            RawTransactionStub(
                status=RawTransactionStatus.NEEDS_REVIEW,
                account_id=account_id,
                amount=Decimal("100.00"),
            ),
            AccountStub(id=account_id),
        )


def test_build_ledger_posting_plan_blocks_currency_mismatch() -> None:
    account_id = uuid4()
    with pytest.raises(LedgerPostingError, match="currency"):
        build_ledger_posting_plan(
            RawTransactionStub(
                status=RawTransactionStatus.NORMALIZED,
                account_id=account_id,
                amount=Decimal("100.00"),
                currency="USD",
            ),
            AccountStub(id=account_id, currency="RUB"),
        )


def test_transfer_source_allows_manual_reviewable_raw_rows() -> None:
    ensure_raw_transaction_can_post_as_transfer(
        RawTransactionStub(
            status=RawTransactionStatus.POSSIBLE_DUPLICATE,
            account_id=uuid4(),
            amount=Decimal("-100.00"),
        )
    )


def test_transfer_source_blocks_already_linked_rows() -> None:
    with pytest.raises(LedgerPostingError, match="already linked"):
        ensure_raw_transaction_can_post_as_transfer(
            RawTransactionStub(
                status=RawTransactionStatus.NORMALIZED,
                account_id=uuid4(),
                amount=Decimal("-100.00"),
                linked_operation_id=uuid4(),
            )
        )


def test_matched_transfer_row_must_belong_to_selected_account() -> None:
    matched_account_id = uuid4()

    ensure_matched_transfer_account(
        RawTransactionStub(
            status=RawTransactionStatus.NORMALIZED,
            account_id=matched_account_id,
            amount=Decimal("100.00"),
        ),
        matched_account_id,
    )

    with pytest.raises(LedgerPostingError, match="selected transfer account"):
        ensure_matched_transfer_account(
            RawTransactionStub(
                status=RawTransactionStatus.NORMALIZED,
                account_id=matched_account_id,
                amount=Decimal("100.00"),
            ),
            uuid4(),
        )


def test_restored_raw_status_after_unlink_preserves_rule_suggestion() -> None:
    assert (
        restored_raw_status_after_unlink(
            RawTransactionStub(
                status=RawTransactionStatus.CONFIRMED,
                account_id=uuid4(),
                amount=Decimal("-100.00"),
                suggested_by_rule_id=uuid4(),
            )
        )
        == RawTransactionStatus.SUGGESTED
    )
    assert (
        restored_raw_status_after_unlink(
            RawTransactionStub(
                status=RawTransactionStatus.CONFIRMED,
                account_id=uuid4(),
                amount=Decimal("-100.00"),
            )
        )
        == RawTransactionStatus.NORMALIZED
    )
