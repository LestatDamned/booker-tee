from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.features.ledger.models import OperationStatus, OperationType


@dataclass(frozen=True)
class NamedReferenceReadDto:
    id: UUID
    name: str


@dataclass(frozen=True)
class AccountReferenceReadDto(NamedReferenceReadDto):
    currency: str


@dataclass(frozen=True)
class ManualOperationMoneyReadDto:
    amount: Decimal
    currency: str


@dataclass(frozen=True)
class ManualOperationReadDto:
    id: UUID
    version: int
    operation_type: OperationType
    status: OperationStatus
    operation_date: date
    description: str | None
    money: ManualOperationMoneyReadDto | None
    account: AccountReferenceReadDto | None
    source_account: AccountReferenceReadDto | None
    destination_account: AccountReferenceReadDto | None
    category: NamedReferenceReadDto | None
    property: NamedReferenceReadDto | None
