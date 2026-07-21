from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.features.ledger.domain.types import OperationStatus, OperationType


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


CreateManualOperationCommand = CreateManualIncomeExpenseCommand | CreateManualTransferCommand


@dataclass(frozen=True)
class UpdateManualOperationCommandBase:
    operation_id: UUID
    amount: Decimal
    operation_date: date
    description: str | None
    expected_version: int


@dataclass(frozen=True)
class UpdateManualIncomeExpenseCommand(UpdateManualOperationCommandBase):
    operation_type: OperationType
    account_id: UUID
    category_id: UUID | None
    property_id: UUID | None


@dataclass(frozen=True)
class UpdateManualTransferCommand(UpdateManualOperationCommandBase):
    source_account_id: UUID
    destination_account_id: UUID


UpdateManualOperationCommand = UpdateManualIncomeExpenseCommand | UpdateManualTransferCommand


@dataclass(frozen=True)
class UpdateImportedOperationReviewFieldsCommand:
    operation_id: UUID
    category_id: UUID | None
    property_id: UUID | None
    description: str | None
    status: OperationStatus
