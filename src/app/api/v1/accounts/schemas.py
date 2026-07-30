from datetime import datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

from pydantic import Field, field_validator
from pydantic_core import PydanticCustomError

from app.api.schemas import ApiModel, ApiRequestModel
from app.features.accounts.models import AccountType
from app.features.accounts.schemas import (
    AccountBalanceDirection,
    AccountDirectoryReadonlyReason,
)

MAX_ACCOUNT_ABSOLUTE_BALANCE = Decimal("999999999999.99")


class AccountSummaryApiResponse(ApiModel):
    id: UUID
    name: str
    account_type: AccountType
    currency: str
    initial_balance: str
    balance: str
    balance_direction: AccountBalanceDirection
    movement_count: int
    is_active: bool
    updated_at: datetime
    capabilities: "AccountSummaryCapabilitiesApiResponse"


class AccountSummaryCapabilitiesApiResponse(ApiModel):
    can_archive: bool
    can_restore: bool


class AccountDirectoryCapabilitiesApiResponse(ApiModel):
    can_create: bool
    readonly_reason_code: AccountDirectoryReadonlyReason | None


class AccountDirectoryApiResponse(ApiModel):
    items: list[AccountSummaryApiResponse]
    account_types: list[AccountType]
    capabilities: AccountDirectoryCapabilitiesApiResponse


class CreateAccountApiRequest(ApiRequestModel):
    name: str = Field(max_length=255)
    account_type: AccountType
    currency: str
    initial_balance: str = "0.00"

    @field_validator("name")
    @classmethod
    def require_name(cls, name: str) -> str:
        cleaned = " ".join(name.split())
        if not cleaned:
            raise PydanticCustomError(
                "account_name_required",
                "Название счета обязательно.",
            )
        return cleaned

    @field_validator("currency")
    @classmethod
    def require_currency(cls, currency: str) -> str:
        normalized = currency.strip().upper()
        if len(normalized) != 3:
            raise PydanticCustomError(
                "account_currency",
                "Валюта должна быть трехбуквенным кодом.",
            )
        return normalized

    @field_validator("initial_balance")
    @classmethod
    def require_decimal_balance(cls, initial_balance: str) -> str:
        normalized = initial_balance.strip().replace(",", ".")
        try:
            amount = Decimal(normalized)
        except InvalidOperation as error:
            raise PydanticCustomError(
                "decimal_initial_balance",
                "Введите корректный начальный баланс.",
            ) from error
        if not amount.is_finite() or abs(amount) > MAX_ACCOUNT_ABSOLUTE_BALANCE:
            raise PydanticCustomError(
                "bounded_initial_balance",
                "Начальный баланс выходит за допустимый диапазон.",
            )
        return normalized

    @property
    def decimal_initial_balance(self) -> Decimal:
        return Decimal(self.initial_balance)


class AccountLifecycleApiRequest(ApiRequestModel):
    expected_active: bool
    expected_updated_at: datetime
