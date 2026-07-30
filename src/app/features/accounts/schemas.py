from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from app.features.accounts.models import AccountType
from app.shared.schemas import ApplicationModel


class AccountBalanceDirection(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    ZERO = "zero"


class AccountDirectoryReadonlyReason(StrEnum):
    FINANCIAL_WRITE_FORBIDDEN = "financial_write_forbidden"


class CreateAccountCommand(ApplicationModel):
    name: str
    account_type: AccountType
    currency: str
    initial_balance: Decimal


class AccountSummaryDto(ApplicationModel):
    id: UUID
    name: str
    account_type: AccountType
    currency: str
    initial_balance: Decimal
    balance: Decimal
    balance_direction: AccountBalanceDirection
    movement_count: int
    is_active: bool
    updated_at: datetime


class AccountDirectoryCapabilitiesDto(ApplicationModel):
    can_create: bool
    readonly_reason_code: AccountDirectoryReadonlyReason | None


class AccountDirectoryDto(ApplicationModel):
    items: list[AccountSummaryDto]
    account_types: list[AccountType]
    capabilities: AccountDirectoryCapabilitiesDto
