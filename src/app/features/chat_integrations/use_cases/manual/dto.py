from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.features.ledger.models import OperationType


@dataclass(frozen=True)
class ChatManualAccountChoice:
    name: str
    currency: str


@dataclass(frozen=True)
class StartedChatManualAccountSelection:
    action_token: str
    operation_type: OperationType
    account_choices: tuple[ChatManualAccountChoice, ...]
    source_account_name: str | None = None


@dataclass(frozen=True)
class StartedChatManualAmountInput:
    operation_type: OperationType
    account_name: str
    currency: str
    destination_account_name: str | None = None


@dataclass(frozen=True)
class StartedChatManualDateSelection:
    action_token: str
    operation_type: OperationType
    amount: Decimal
    currency: str
    account_name: str
    destination_account_name: str | None = None


@dataclass(frozen=True)
class StartedChatManualDateInput:
    operation_type: OperationType
    amount: Decimal
    currency: str
    account_name: str
    destination_account_name: str | None = None


@dataclass(frozen=True)
class StartedChatManualDescriptionInput:
    action_token: str
    operation_type: OperationType
    amount: Decimal
    operation_date: date
    currency: str
    account_name: str
    category_name: str | None = None
    destination_account_name: str | None = None


@dataclass(frozen=True)
class ChatManualCategoryChoice:
    id: UUID | None
    name: str


@dataclass(frozen=True)
class StartedChatManualCategorySelection:
    action_token: str
    operation_type: OperationType
    amount: Decimal
    currency: str
    account_name: str
    category_choices: tuple[ChatManualCategoryChoice, ...]


@dataclass(frozen=True)
class ChatManualOperationConfirmation:
    action_token: str
    operation_type: OperationType
    amount: Decimal
    operation_date: date
    account_name: str
    currency: str
    category_name: str | None = None
    description: str | None = None
    destination_account_name: str | None = None


@dataclass(frozen=True)
class StartedChatManualCorrectionSelection:
    action_token: str
    confirmation: ChatManualOperationConfirmation


@dataclass(frozen=True)
class ChatManualOperationResult:
    operation_id: UUID
    operation_type: OperationType
    amount: Decimal
    currency: str
    operation_date: date


@dataclass(frozen=True)
class ChatManualStoredAccount:
    id: UUID
    name: str
    currency: str


@dataclass(frozen=True)
class ChatManualStoredCategory:
    id: UUID | None
    name: str
