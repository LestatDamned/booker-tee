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
        pytest.param(DebtKind.LOAN_RECEIVABLE, Decimal("70000.00"), id="receivable"),
        pytest.param(DebtKind.LOAN_PAYABLE, Decimal("-70000.00"), id="loan-payable"),
        pytest.param(DebtKind.CREDIT_CARD, Decimal("-25000.00"), id="credit-card"),
        pytest.param(DebtKind.MORTGAGE, Decimal("-4200000.00"), id="mortgage"),
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
        pytest.param(DebtKind.LOAN_RECEIVABLE, Decimal("-1.00"), id="receivable"),
        pytest.param(DebtKind.LOAN_PAYABLE, Decimal("1.00"), id="loan-payable"),
        pytest.param(DebtKind.CREDIT_CARD, Decimal("1.00"), id="credit-card"),
        pytest.param(DebtKind.MORTGAGE, Decimal("1.00"), id="mortgage"),
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
        pytest.param(
            DebtKind.LOAN_RECEIVABLE,
            Decimal("1.00"),
            True,
            DebtStatus.ACTIVE,
            id="active-receivable",
        ),
        pytest.param(
            DebtKind.LOAN_PAYABLE,
            Decimal("0.00"),
            True,
            DebtStatus.SETTLED,
            id="settled-payable",
        ),
        pytest.param(
            DebtKind.MORTGAGE,
            Decimal("0.00"),
            True,
            DebtStatus.SETTLED,
            id="settled-mortgage",
        ),
        pytest.param(
            DebtKind.CREDIT_CARD,
            Decimal("0.00"),
            True,
            DebtStatus.NO_DEBT,
            id="credit-card-without-debt",
        ),
        pytest.param(
            DebtKind.CREDIT_CARD,
            Decimal("-1.00"),
            False,
            DebtStatus.ARCHIVED,
            id="archived-credit-card",
        ),
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
        pytest.param(Decimal("101.00"), Decimal("0.00"), id="principal-exceeds-debt"),
        pytest.param(Decimal("0.00"), Decimal("0.00"), id="zero-total"),
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


@pytest.mark.parametrize(
    (
        "kind",
        "opening_balance",
        "opened_on",
        "maturity_date",
        "original_principal",
        "credit_limit",
    ),
    [
        pytest.param(
            DebtKind.MORTGAGE,
            Decimal("-100.00"),
            date(2026, 1, 2),
            date(2026, 1, 1),
            Decimal("100.00"),
            None,
            id="maturity-before-opening",
        ),
        pytest.param(
            DebtKind.CREDIT_CARD,
            Decimal("-101.00"),
            None,
            None,
            None,
            Decimal("100.00"),
            id="opening-debt-exceeds-credit-limit",
        ),
        pytest.param(
            DebtKind.LOAN_PAYABLE,
            Decimal("-100.00"),
            None,
            None,
            None,
            None,
            id="loan-without-original-principal",
        ),
    ],
)
def test_terms_reject_invalid_configuration(
    kind: DebtKind,
    opening_balance: Decimal,
    opened_on: date | None,
    maturity_date: date | None,
    original_principal: Decimal | None,
    credit_limit: Decimal | None,
) -> None:
    with pytest.raises(DebtValidationError):
        DebtPolicy.validate_terms(
            kind=kind,
            opening_balance=opening_balance,
            opened_on=opened_on,
            maturity_date=maturity_date,
            original_principal=original_principal,
            credit_limit=credit_limit,
        )


def test_readonly_capabilities_block_financial_mutations() -> None:
    capabilities = DebtPolicy.resolve_capabilities(
        kind=DebtKind.LOAN_PAYABLE,
        balance=Decimal("-100.00"),
        can_write=False,
        is_active=True,
        has_payment_account=True,
        has_delete_blockers=True,
    )

    assert capabilities.can_record_payment is False
    assert capabilities.payment_blocked_reason is DebtPaymentBlockedReason.FINANCIAL_WRITE_FORBIDDEN
    assert capabilities.can_update is False
    assert capabilities.can_delete is False


def test_settled_debt_capabilities_allow_safe_maintenance() -> None:
    capabilities = DebtPolicy.resolve_capabilities(
        kind=DebtKind.LOAN_PAYABLE,
        balance=Decimal("0.00"),
        can_write=True,
        is_active=True,
        has_payment_account=True,
        has_delete_blockers=False,
    )

    assert capabilities.can_archive is True
    assert capabilities.can_update is True
    assert capabilities.can_delete is True
    assert capabilities.payment_blocked_reason is DebtPaymentBlockedReason.DEBT_SETTLED
