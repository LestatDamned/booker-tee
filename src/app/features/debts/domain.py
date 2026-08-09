from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from app.features.ledger.domain.types import OperationType

ZERO = Decimal("0.00")
MONEY_QUANTUM = Decimal("0.01")


class DebtValidationError(ValueError):
    pass


class DebtKind(StrEnum):
    LOAN_RECEIVABLE = "loan_receivable"
    LOAN_PAYABLE = "loan_payable"
    CREDIT_CARD = "credit_card"
    MORTGAGE = "mortgage"


class DebtStatus(StrEnum):
    ACTIVE = "active"
    SETTLED = "settled"
    NO_DEBT = "no_debt"
    ARCHIVED = "archived"


class DebtPaymentBlockedReason(StrEnum):
    FINANCIAL_WRITE_FORBIDDEN = "financial_write_forbidden"
    DEBT_ARCHIVED = "debt_archived"
    DEBT_SETTLED = "debt_settled"
    NO_PAYMENT_ACCOUNT = "no_payment_account"


class DebtDeleteBlockedReason(StrEnum):
    FINANCIAL_WRITE_FORBIDDEN = "financial_write_forbidden"
    FINANCIAL_HISTORY = "financial_history"


@dataclass(frozen=True)
class DebtBalance:
    kind: DebtKind
    currency: str
    balance: Decimal


@dataclass(frozen=True)
class DebtCurrencyTotals:
    currency: str
    receivable: Decimal
    payable: Decimal
    net_position: Decimal


@dataclass(frozen=True)
class DebtPaymentPlan:
    principal_operation_type: OperationType | None
    debt_principal_amount: Decimal
    settlement_principal_amount: Decimal
    interest_operation_type: OperationType | None
    settlement_interest_amount: Decimal


@dataclass(frozen=True)
class DebtCapabilities:
    can_record_payment: bool
    can_archive: bool
    can_restore: bool
    can_update: bool
    can_delete: bool
    payment_blocked_reason: DebtPaymentBlockedReason | None
    delete_blocked_reason: DebtDeleteBlockedReason | None


class DebtPolicy:
    @staticmethod
    def ensure_balance(kind: DebtKind, balance: Decimal) -> Decimal:
        normalized = _normalize_amount(balance)
        if kind is DebtKind.LOAN_RECEIVABLE and normalized < ZERO:
            raise DebtValidationError("A receivable balance cannot be negative.")
        if kind is not DebtKind.LOAN_RECEIVABLE and normalized > ZERO:
            raise DebtValidationError("A payable balance cannot be positive.")
        return normalized

    @staticmethod
    def outstanding(kind: DebtKind, balance: Decimal) -> Decimal:
        return abs(DebtPolicy.ensure_balance(kind, balance))

    @staticmethod
    def resolve_status(
        *,
        kind: DebtKind,
        balance: Decimal,
        is_active: bool,
    ) -> DebtStatus:
        normalized = DebtPolicy.ensure_balance(kind, balance)
        if not is_active:
            return DebtStatus.ARCHIVED
        if normalized != ZERO:
            return DebtStatus.ACTIVE
        if kind is DebtKind.CREDIT_CARD:
            return DebtStatus.NO_DEBT
        return DebtStatus.SETTLED

    @staticmethod
    def calculate_available_credit(*, credit_limit: Decimal, balance: Decimal) -> Decimal:
        limit = _normalize_positive_amount(credit_limit)
        outstanding = DebtPolicy.outstanding(DebtKind.CREDIT_CARD, balance)
        return (limit - outstanding).quantize(MONEY_QUANTUM)

    @staticmethod
    def validate_terms(
        *,
        kind: DebtKind,
        opening_balance: Decimal,
        opened_on: date | None,
        maturity_date: date | None,
        original_principal: Decimal | None,
        credit_limit: Decimal | None,
    ) -> None:
        balance = DebtPolicy.ensure_balance(kind, opening_balance)
        if opened_on is not None and maturity_date is not None and maturity_date < opened_on:
            raise DebtValidationError("Maturity date cannot be before the opening date.")

        if kind is DebtKind.CREDIT_CARD:
            if credit_limit is None:
                raise DebtValidationError("A credit card requires a credit limit.")
            limit = _normalize_positive_amount(credit_limit)
            if abs(balance) > limit:
                raise DebtValidationError("Opening debt cannot exceed the credit limit.")
        elif credit_limit is not None:
            raise DebtValidationError("Credit limit is only valid for a credit card.")

        if kind is not DebtKind.CREDIT_CARD and original_principal is None:
            raise DebtValidationError("A loan or mortgage requires original principal.")
        if original_principal is not None:
            _normalize_positive_amount(original_principal)

    @staticmethod
    def resolve_capabilities(
        *,
        kind: DebtKind,
        balance: Decimal,
        can_write: bool,
        is_active: bool,
        has_payment_account: bool,
        has_delete_blockers: bool,
    ) -> DebtCapabilities:
        outstanding = DebtPolicy.outstanding(kind, balance)
        payment_blocked_reason = _payment_blocked_reason(
            can_write=can_write,
            is_active=is_active,
            outstanding=outstanding,
            has_payment_account=has_payment_account,
        )
        return DebtCapabilities(
            can_record_payment=payment_blocked_reason is None,
            can_archive=can_write and is_active and outstanding == ZERO,
            can_restore=can_write and not is_active,
            can_update=can_write,
            can_delete=can_write and not has_delete_blockers,
            payment_blocked_reason=payment_blocked_reason,
            delete_blocked_reason=(
                DebtDeleteBlockedReason.FINANCIAL_WRITE_FORBIDDEN
                if not can_write
                else (DebtDeleteBlockedReason.FINANCIAL_HISTORY if has_delete_blockers else None)
            ),
        )


class DebtPaymentPlanner:
    @staticmethod
    def build(
        *,
        kind: DebtKind,
        balance: Decimal,
        principal_amount: Decimal,
        interest_amount: Decimal,
    ) -> DebtPaymentPlan:
        outstanding = DebtPolicy.outstanding(kind, balance)
        principal = _normalize_nonnegative_amount(principal_amount)
        interest = _normalize_nonnegative_amount(interest_amount)
        if principal == ZERO and interest == ZERO:
            raise DebtValidationError("Principal or interest must be greater than zero.")
        if outstanding == ZERO:
            raise DebtValidationError("A settled debt cannot receive a payment.")
        if principal > outstanding:
            raise DebtValidationError("Principal payment exceeds the outstanding debt.")

        receivable = kind is DebtKind.LOAN_RECEIVABLE
        return DebtPaymentPlan(
            principal_operation_type=OperationType.TRANSFER if principal else None,
            debt_principal_amount=-principal if receivable else principal,
            settlement_principal_amount=principal if receivable else -principal,
            interest_operation_type=(OperationType.INCOME if receivable else OperationType.EXPENSE)
            if interest
            else None,
            settlement_interest_amount=interest if receivable else -interest,
        )


class DebtPortfolio:
    @staticmethod
    def summarize(balances: Iterable[DebtBalance]) -> list[DebtCurrencyTotals]:
        amounts: dict[str, tuple[Decimal, Decimal]] = {}
        for debt in balances:
            balance = DebtPolicy.ensure_balance(debt.kind, debt.balance)
            currency = debt.currency.strip().upper()
            if len(currency) != 3:
                raise DebtValidationError("Currency must be a three-letter code.")
            receivable, payable = amounts.get(currency, (ZERO, ZERO))
            if balance > ZERO:
                receivable += balance
            elif balance < ZERO:
                payable += abs(balance)
            amounts[currency] = receivable, payable

        return [
            DebtCurrencyTotals(
                currency=currency,
                receivable=receivable,
                payable=payable,
                net_position=(receivable - payable).quantize(MONEY_QUANTUM),
            )
            for currency, (receivable, payable) in sorted(amounts.items())
        ]


def _normalize_positive_amount(amount: Decimal) -> Decimal:
    normalized = _normalize_amount(amount)
    if normalized <= ZERO:
        raise DebtValidationError("Amount must be greater than zero.")
    return normalized


def _normalize_nonnegative_amount(amount: Decimal) -> Decimal:
    normalized = _normalize_amount(amount)
    if normalized < ZERO:
        raise DebtValidationError("Amount cannot be negative.")
    return normalized


def _normalize_amount(amount: Decimal) -> Decimal:
    if not amount.is_finite():
        raise DebtValidationError("Amount must be finite.")
    try:
        return amount.quantize(MONEY_QUANTUM)
    except InvalidOperation as error:
        raise DebtValidationError("Amount cannot be represented as money.") from error


def _payment_blocked_reason(
    *,
    can_write: bool,
    is_active: bool,
    outstanding: Decimal,
    has_payment_account: bool,
) -> DebtPaymentBlockedReason | None:
    if not can_write:
        return DebtPaymentBlockedReason.FINANCIAL_WRITE_FORBIDDEN
    if not is_active:
        return DebtPaymentBlockedReason.DEBT_ARCHIVED
    if outstanding == ZERO:
        return DebtPaymentBlockedReason.DEBT_SETTLED
    if not has_payment_account:
        return DebtPaymentBlockedReason.NO_PAYMENT_ACCOUNT
    return None
