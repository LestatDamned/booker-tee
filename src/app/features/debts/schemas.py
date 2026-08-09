from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from app.features.debts.domain import (
    DebtDeleteBlockedReason,
    DebtKind,
    DebtPaymentBlockedReason,
    DebtStatus,
)
from app.features.ledger.domain.types import OperationStatus, OperationType
from app.shared.schemas import ApplicationModel


class AddExistingDebtCommand(ApplicationModel):
    name: str
    kind: DebtKind
    currency: str
    opening_balance: Decimal
    original_principal: Decimal
    opened_on: date | None
    maturity_date: date | None
    notes: str | None
    idempotency_key: UUID


class GiveLoanCommand(ApplicationModel):
    name: str
    currency: str
    amount: Decimal
    funding_account_id: UUID
    operation_date: date
    opened_on: date | None
    maturity_date: date | None
    description: str | None
    notes: str | None
    idempotency_key: UUID


class TakeLoanCommand(ApplicationModel):
    name: str
    kind: DebtKind
    currency: str
    amount: Decimal
    receiving_account_id: UUID
    operation_date: date
    opened_on: date | None
    maturity_date: date | None
    description: str | None
    notes: str | None
    idempotency_key: UUID


class OpenCreditCardCommand(ApplicationModel):
    name: str
    currency: str
    credit_limit: Decimal
    opening_debt: Decimal
    opened_on: date | None
    notes: str | None
    idempotency_key: UUID


DebtCreateCommand = (
    AddExistingDebtCommand | GiveLoanCommand | TakeLoanCommand | OpenCreditCardCommand
)


class RecordDebtPaymentCommand(ApplicationModel):
    debt_account_id: UUID
    settlement_account_id: UUID
    principal_amount: Decimal
    interest_amount: Decimal
    operation_date: date
    interest_category_id: UUID | None
    description: str | None
    notes: str | None
    idempotency_key: UUID


class UndoDebtPaymentCommand(ApplicationModel):
    payment_id: UUID
    expected_principal_operation_version: int | None
    expected_interest_operation_version: int | None


class DebtLifecycleCommand(ApplicationModel):
    debt_account_id: UUID
    expected_active: bool
    expected_updated_at: datetime


class UpdateDebtCommand(ApplicationModel):
    debt_account_id: UUID
    name: str
    opened_on: date | None
    maturity_date: date | None
    credit_limit: Decimal | None
    notes: str | None
    expected_updated_at: datetime


class DeleteDebtCommand(ApplicationModel):
    debt_account_id: UUID
    expected_updated_at: datetime


class DebtCapabilitiesDto(ApplicationModel):
    can_record_payment: bool
    can_archive: bool
    can_restore: bool
    can_update: bool
    can_delete: bool
    payment_blocked_reason: DebtPaymentBlockedReason | None
    delete_blocked_reason: DebtDeleteBlockedReason | None


class DebtSummaryDto(ApplicationModel):
    account_id: UUID
    name: str
    kind: DebtKind
    currency: str
    balance: Decimal
    outstanding: Decimal
    status: DebtStatus
    opened_on: date | None
    original_principal: Decimal | None
    maturity_date: date | None
    credit_limit: Decimal | None
    available_credit: Decimal | None
    is_active: bool
    updated_at: datetime
    capabilities: DebtCapabilitiesDto


class DebtCurrencyTotalsDto(ApplicationModel):
    currency: str
    receivable: Decimal
    payable: Decimal
    net_position: Decimal


class DebtPortfolioDto(ApplicationModel):
    items: list[DebtSummaryDto]
    totals: list[DebtCurrencyTotalsDto]


class DebtPaymentOperationDto(ApplicationModel):
    operation_id: UUID
    version: int
    operation_date: date
    operation_type: OperationType
    status: OperationStatus
    description: str | None
    amount: Decimal


class DebtPaymentHistoryItemDto(ApplicationModel):
    payment_id: UUID
    principal: DebtPaymentOperationDto | None
    interest: DebtPaymentOperationDto | None
    notes: str | None
    created_at: datetime
    reversed_at: datetime | None
    can_undo: bool


class DebtPaymentHistoryPageDto(ApplicationModel):
    items: list[DebtPaymentHistoryItemDto]
    page: int
    page_size: int
    total: int
    total_pages: int
    has_previous: bool
    has_next: bool


class DebtPaymentTotalsDto(ApplicationModel):
    principal: Decimal
    interest: Decimal


class DebtDetailDto(ApplicationModel):
    debt: DebtSummaryDto
    notes: str | None
    payment_totals: DebtPaymentTotalsDto
    payments: DebtPaymentHistoryPageDto
