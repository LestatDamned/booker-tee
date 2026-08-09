from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from app.api.schemas import ApiModel, ApiRequestModel
from app.features.debts.domain import (
    DebtDeleteBlockedReason,
    DebtKind,
    DebtPaymentBlockedReason,
    DebtStatus,
)
from app.features.ledger.domain.types import OperationStatus, OperationType


def _money_string(value: str, *, allow_zero: bool) -> str:
    normalized = value.strip().replace(",", ".")
    try:
        amount = Decimal(normalized)
    except InvalidOperation as error:
        raise PydanticCustomError("decimal_amount", "Введите корректную сумму.") from error
    if not amount.is_finite() or amount < 0 or (not allow_zero and amount == 0):
        message = (
            "Сумма не может быть отрицательной." if allow_zero else "Сумма должна быть больше нуля."
        )
        raise PydanticCustomError("money_amount", message)
    return normalized


class DebtCreateApiRequestBase(ApiRequestModel):
    name: str
    currency: str
    opened_on: date | None = None
    notes: str | None = None


class AddExistingDebtApiRequest(DebtCreateApiRequestBase):
    action: Literal["add_existing"]
    kind: Literal[DebtKind.LOAN_RECEIVABLE, DebtKind.LOAN_PAYABLE, DebtKind.MORTGAGE]
    opening_balance: str
    original_principal: str
    maturity_date: date | None = None

    @field_validator("opening_balance", "original_principal")
    @classmethod
    def require_positive_money(cls, value: str) -> str:
        return _money_string(value, allow_zero=False)


class GiveLoanApiRequest(DebtCreateApiRequestBase):
    action: Literal["give_loan"]
    amount: str
    funding_account_id: UUID
    operation_date: date
    maturity_date: date | None = None
    description: str | None = None

    @field_validator("amount")
    @classmethod
    def require_positive_money(cls, value: str) -> str:
        return _money_string(value, allow_zero=False)


class TakeLoanApiRequest(DebtCreateApiRequestBase):
    action: Literal["take_loan"]
    kind: Literal[DebtKind.LOAN_PAYABLE, DebtKind.MORTGAGE]
    amount: str
    receiving_account_id: UUID
    operation_date: date
    maturity_date: date | None = None
    description: str | None = None

    @field_validator("amount")
    @classmethod
    def require_positive_money(cls, value: str) -> str:
        return _money_string(value, allow_zero=False)


class OpenCreditCardApiRequest(DebtCreateApiRequestBase):
    action: Literal["open_credit_card"]
    credit_limit: str
    opening_debt: str = "0.00"

    @field_validator("credit_limit")
    @classmethod
    def require_positive_limit(cls, value: str) -> str:
        return _money_string(value, allow_zero=False)

    @field_validator("opening_debt")
    @classmethod
    def require_nonnegative_debt(cls, value: str) -> str:
        return _money_string(value, allow_zero=True)


DebtCreateApiRequest = Annotated[
    AddExistingDebtApiRequest | GiveLoanApiRequest | TakeLoanApiRequest | OpenCreditCardApiRequest,
    Field(discriminator="action"),
]


class RecordDebtPaymentApiRequest(ApiRequestModel):
    settlement_account_id: UUID
    principal_amount: str = "0.00"
    interest_amount: str = "0.00"
    operation_date: date
    interest_category_id: UUID | None = None
    description: str | None = None
    notes: str | None = None

    @field_validator("principal_amount", "interest_amount")
    @classmethod
    def require_nonnegative_money(cls, value: str) -> str:
        return _money_string(value, allow_zero=True)

    @model_validator(mode="after")
    def require_payment_amount(self) -> "RecordDebtPaymentApiRequest":
        if self.decimal_principal == 0 and self.decimal_interest == 0:
            raise PydanticCustomError(
                "debt_payment_amount",
                "Укажите сумму основного долга или процентов.",
            )
        return self

    @property
    def decimal_principal(self) -> Decimal:
        return Decimal(self.principal_amount)

    @property
    def decimal_interest(self) -> Decimal:
        return Decimal(self.interest_amount)


class UndoDebtPaymentApiRequest(ApiRequestModel):
    expected_principal_operation_version: int | None = Field(default=None, ge=1)
    expected_interest_operation_version: int | None = Field(default=None, ge=1)


class DebtLifecycleApiRequest(ApiRequestModel):
    expected_active: bool
    expected_updated_at: datetime


class UpdateDebtApiRequest(ApiRequestModel):
    name: str
    opened_on: date | None = None
    maturity_date: date | None = None
    credit_limit: str | None = None
    notes: str | None = None
    expected_updated_at: datetime

    @field_validator("credit_limit")
    @classmethod
    def require_positive_optional_money(cls, value: str | None) -> str | None:
        return None if value is None else _money_string(value, allow_zero=False)


class DeleteDebtApiRequest(ApiRequestModel):
    expected_updated_at: datetime


class DeleteDebtApiResponse(ApiModel):
    deleted_id: UUID
    name: str


class DebtCapabilitiesApiResponse(ApiModel):
    can_record_payment: bool
    can_archive: bool
    can_restore: bool
    can_update: bool
    can_delete: bool
    payment_blocked_reason: DebtPaymentBlockedReason | None
    delete_blocked_reason: DebtDeleteBlockedReason | None


class DebtSummaryApiResponse(ApiModel):
    account_id: UUID
    name: str
    kind: DebtKind
    currency: str
    balance: str
    outstanding: str
    status: DebtStatus
    opened_on: date | None
    original_principal: str | None
    maturity_date: date | None
    credit_limit: str | None
    available_credit: str | None
    is_active: bool
    updated_at: datetime
    capabilities: DebtCapabilitiesApiResponse


class DebtCurrencyTotalsApiResponse(ApiModel):
    currency: str
    receivable: str
    payable: str
    net_position: str


class DebtPortfolioCapabilitiesApiResponse(ApiModel):
    can_create: bool
    readonly_reason_code: Literal["financial_write_forbidden"] | None


class DebtPortfolioApiResponse(ApiModel):
    items: list[DebtSummaryApiResponse]
    totals: list[DebtCurrencyTotalsApiResponse]
    capabilities: DebtPortfolioCapabilitiesApiResponse


class DebtPaymentOperationApiResponse(ApiModel):
    operation_id: UUID
    version: int
    operation_date: date
    operation_type: OperationType
    status: OperationStatus
    description: str | None
    amount: str


class DebtPaymentHistoryItemApiResponse(ApiModel):
    payment_id: UUID
    principal: DebtPaymentOperationApiResponse | None
    interest: DebtPaymentOperationApiResponse | None
    notes: str | None
    created_at: datetime
    reversed_at: datetime | None
    can_undo: bool


class DebtPaymentHistoryPageApiResponse(ApiModel):
    items: list[DebtPaymentHistoryItemApiResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
    has_previous: bool
    has_next: bool


class DebtPaymentTotalsApiResponse(ApiModel):
    principal: str
    interest: str


class DebtDetailApiResponse(ApiModel):
    debt: DebtSummaryApiResponse
    notes: str | None
    payment_totals: DebtPaymentTotalsApiResponse
    payments: DebtPaymentHistoryPageApiResponse
