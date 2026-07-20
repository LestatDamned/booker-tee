from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.features.ledger.models import OperationStatus, OperationType


@dataclass(frozen=True)
class CreateManualIncomeExpenseCommand:
    operation_type: OperationType
    account_id: UUID
    amount: Decimal
    operation_date: date
    description: str | None
    category_id: UUID | None
    property_id: UUID | None
    idempotency_key: UUID | None = None


@dataclass(frozen=True)
class CreateManualTransferCommand:
    source_account_id: UUID
    destination_account_id: UUID
    amount: Decimal
    operation_date: date
    description: str | None
    idempotency_key: UUID | None = None


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
    expected_version: int | None = None


@dataclass(frozen=True)
class UpdateImportedOperationReviewFieldsCommand:
    operation_id: UUID
    category_id: UUID | None
    property_id: UUID | None
    description: str | None
    status: OperationStatus
