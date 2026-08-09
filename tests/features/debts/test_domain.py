from datetime import date
from decimal import Decimal

import pytest

from app.features.debts.domain import (
    DebtBalance,
    DebtCurrencyTotals,
    DebtKind,
    DebtPaymentBlockedReason,
    DebtPaymentPlanner,
    DebtPolicy,
    DebtPortfolio,
    DebtStatus,
    DebtValidationError,
)
from app.features.ledger.domain.money import affects_profit_for_operation_type
from app.features.ledger.domain.types import OperationType


@pytest.mark.parametrize(
    ("kind", "balance"),
    [
        (DebtKind.LOAN_RECEIVABLE, Decimal("70000.00")),
        (DebtKind.LOAN_PAYABLE, Decimal("-70000.00")),
        (DebtKind.CREDIT_CARD, Decimal("-25000.00")),
        (DebtKind.MORTGAGE, Decimal("-4200000.00")),
    ],
)
def test_debt_kinds_use_expected_balance_direction(
    kind: DebtKind,
    balance: Decimal,
) -> None:
    assert DebtPolicy.outstanding(kind, balance) == abs(balance)


@pytest.mark.parametrize(
    ("kind", "balance"),
    [
        (DebtKind.LOAN_RECEIVABLE, Decimal("-1.00")),
        (DebtKind.LOAN_PAYABLE, Decimal("1.00")),
        (DebtKind.CREDIT_CARD, Decimal("1.00")),
        (DebtKind.MORTGAGE, Decimal("1.00")),
    ],
)
def test_debt_balance_cannot_cross_to_the_other_direction(
    kind: DebtKind,
    balance: Decimal,
) -> None:
    with pytest.raises(DebtValidationError):
        DebtPolicy.ensure_balance(kind, balance)


@pytest.mark.parametrize(
    ("kind", "balance", "is_active", "expected"),
    [
        (DebtKind.LOAN_RECEIVABLE, Decimal("1.00"), True, DebtStatus.ACTIVE),
        (DebtKind.LOAN_PAYABLE, Decimal("0.00"), True, DebtStatus.SETTLED),
        (DebtKind.MORTGAGE, Decimal("0.00"), True, DebtStatus.SETTLED),
        (DebtKind.CREDIT_CARD, Decimal("0.00"), True, DebtStatus.NO_DEBT),
        (DebtKind.CREDIT_CARD, Decimal("-1.00"), False, DebtStatus.ARCHIVED),
    ],
)
def test_debt_status_comes_from_lifecycle_kind_and_balance(
    kind: DebtKind,
    balance: Decimal,
    is_active: bool,
    expected: DebtStatus,
) -> None:
    assert (
        DebtPolicy.resolve_status(
            kind=kind,
            balance=balance,
            is_active=is_active,
        )
        is expected
    )


def test_available_credit_uses_current_principal() -> None:
    assert DebtPolicy.calculate_available_credit(
        credit_limit=Decimal("300000.00"),
        balance=Decimal("-120000.00"),
    ) == Decimal("180000.00")


def test_currency_totals_group_same_currency_without_mixing_currencies() -> None:
    totals = DebtPortfolio.summarize(
        [
            DebtBalance(DebtKind.LOAN_RECEIVABLE, "rub", Decimal("70000.00")),
            DebtBalance(DebtKind.CREDIT_CARD, "RUB", Decimal("-120000.00")),
            DebtBalance(DebtKind.MORTGAGE, "RUB", Decimal("-4200000.00")),
            DebtBalance(DebtKind.LOAN_PAYABLE, "USD", Decimal("-100.00")),
        ]
    )

    assert totals == [
        DebtCurrencyTotals(
            currency="RUB",
            receivable=Decimal("70000.00"),
            payable=Decimal("4320000.00"),
            net_position=Decimal("-4250000.00"),
        ),
        DebtCurrencyTotals(
            currency="USD",
            receivable=Decimal("0.00"),
            payable=Decimal("100.00"),
            net_position=Decimal("-100.00"),
        ),
    ]


def test_payable_payment_separates_principal_transfer_and_interest_expense() -> None:
    plan = DebtPaymentPlanner.build(
        kind=DebtKind.MORTGAGE,
        balance=Decimal("-4200000.00"),
        principal_amount=Decimal("12000.00"),
        interest_amount=Decimal("38000.00"),
    )

    assert plan.principal_operation_type is OperationType.TRANSFER
    assert plan.debt_principal_amount == Decimal("12000.00")
    assert plan.settlement_principal_amount == Decimal("-12000.00")
    assert plan.debt_principal_amount + plan.settlement_principal_amount == Decimal("0.00")
    assert affects_profit_for_operation_type(plan.principal_operation_type) is False
    assert plan.interest_operation_type is OperationType.EXPENSE
    assert affects_profit_for_operation_type(plan.interest_operation_type) is True
    assert plan.settlement_interest_amount == Decimal("-38000.00")


def test_receivable_payment_separates_principal_transfer_and_interest_income() -> None:
    plan = DebtPaymentPlanner.build(
        kind=DebtKind.LOAN_RECEIVABLE,
        balance=Decimal("70000.00"),
        principal_amount=Decimal("20000.00"),
        interest_amount=Decimal("2000.00"),
    )

    assert plan.principal_operation_type is OperationType.TRANSFER
    assert plan.debt_principal_amount == Decimal("-20000.00")
    assert plan.settlement_principal_amount == Decimal("20000.00")
    assert plan.interest_operation_type is OperationType.INCOME
    assert plan.settlement_interest_amount == Decimal("2000.00")


def test_payment_may_contain_only_principal() -> None:
    plan = DebtPaymentPlanner.build(
        kind=DebtKind.LOAN_PAYABLE,
        balance=Decimal("-100.00"),
        principal_amount=Decimal("25.00"),
        interest_amount=Decimal("0.00"),
    )

    assert plan.principal_operation_type is OperationType.TRANSFER
    assert plan.interest_operation_type is None
    assert plan.settlement_interest_amount == Decimal("0.00")


def test_payment_may_contain_only_interest() -> None:
    plan = DebtPaymentPlanner.build(
        kind=DebtKind.LOAN_RECEIVABLE,
        balance=Decimal("100.00"),
        principal_amount=Decimal("0.00"),
        interest_amount=Decimal("5.00"),
    )

    assert plan.principal_operation_type is None
    assert plan.debt_principal_amount == Decimal("0.00")
    assert plan.interest_operation_type is OperationType.INCOME
    assert plan.settlement_interest_amount == Decimal("5.00")


@pytest.mark.parametrize(
    ("principal", "interest"),
    [
        (Decimal("101.00"), Decimal("0.00")),
        (Decimal("0.00"), Decimal("0.00")),
    ],
)
def test_invalid_payment_is_rejected(principal: Decimal, interest: Decimal) -> None:
    with pytest.raises(DebtValidationError):
        DebtPaymentPlanner.build(
            kind=DebtKind.LOAN_PAYABLE,
            balance=Decimal("-100.00"),
            principal_amount=principal,
            interest_amount=interest,
        )


def test_terms_accept_credit_card_without_original_principal() -> None:
    DebtPolicy.validate_terms(
        kind=DebtKind.CREDIT_CARD,
        opening_balance=Decimal("-25000.00"),
        opened_on=date(2025, 1, 1),
        maturity_date=None,
        original_principal=None,
        credit_limit=Decimal("300000.00"),
    )


def test_terms_reject_invalid_dates_limits_and_missing_principal() -> None:
    with pytest.raises(DebtValidationError):
        DebtPolicy.validate_terms(
            kind=DebtKind.MORTGAGE,
            opening_balance=Decimal("-100.00"),
            opened_on=date(2026, 1, 2),
            maturity_date=date(2026, 1, 1),
            original_principal=Decimal("100.00"),
            credit_limit=None,
        )
    with pytest.raises(DebtValidationError):
        DebtPolicy.validate_terms(
            kind=DebtKind.CREDIT_CARD,
            opening_balance=Decimal("-101.00"),
            opened_on=None,
            maturity_date=None,
            original_principal=None,
            credit_limit=Decimal("100.00"),
        )
    with pytest.raises(DebtValidationError):
        DebtPolicy.validate_terms(
            kind=DebtKind.LOAN_PAYABLE,
            opening_balance=Decimal("-100.00"),
            opened_on=None,
            maturity_date=None,
            original_principal=None,
            credit_limit=None,
        )


def test_capabilities_keep_financial_write_policy_on_server() -> None:
    readonly = DebtPolicy.resolve_capabilities(
        kind=DebtKind.LOAN_PAYABLE,
        balance=Decimal("-100.00"),
        can_write=False,
        is_active=True,
        has_payment_account=True,
        has_delete_blockers=True,
    )
    settled = DebtPolicy.resolve_capabilities(
        kind=DebtKind.LOAN_PAYABLE,
        balance=Decimal("0.00"),
        can_write=True,
        is_active=True,
        has_payment_account=True,
        has_delete_blockers=False,
    )

    assert readonly.can_record_payment is False
    assert readonly.payment_blocked_reason is DebtPaymentBlockedReason.FINANCIAL_WRITE_FORBIDDEN
    assert readonly.can_update is False
    assert readonly.can_delete is False
    assert settled.can_archive is True
    assert settled.can_update is True
    assert settled.can_delete is True
    assert settled.payment_blocked_reason is DebtPaymentBlockedReason.DEBT_SETTLED
