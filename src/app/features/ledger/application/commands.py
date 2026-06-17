from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.features.ledger.models import OperationType


@dataclass(frozen=True)
class CreateManualIncomeExpenseCommand:
    operation_type: OperationType
    account_id: UUID
    amount: Decimal
    operation_date: date
    description: str | None
    category_id: UUID | None
    property_id: UUID | None


@dataclass(frozen=True)
class CreateManualTransferCommand:
    source_account_id: UUID
    destination_account_id: UUID
    amount: Decimal
    operation_date: date
    description: str | None


@dataclass(frozen=True)
class UpdateManualOperationCommand:
    operation_id: UUID
    operation_type: OperationType
    account_id: UUID
    amount: Decimal
    operation_date: date
    description: str | None
    category_id: UUID | None
    property_id: UUID | None
    destination_account_id: UUID | None
