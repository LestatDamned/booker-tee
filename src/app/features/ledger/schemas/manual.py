from datetime import date
from decimal import Decimal
from uuid import UUID

from app.features.ledger.domain.types import OperationStatus, OperationType
from app.shared.schemas import ApplicationModel


class CreateManualIncomeExpenseCommand(ApplicationModel):
    operation_type: OperationType
    account_id: UUID
    amount: Decimal
    operation_date: date
    description: str | None
    category_id: UUID | None
    property_id: UUID | None
    idempotency_key: UUID | None = None


class CreateManualTransferCommand(ApplicationModel):
    source_account_id: UUID
    destination_account_id: UUID
    amount: Decimal
    operation_date: date
    description: str | None
    idempotency_key: UUID | None = None


CreateManualOperationCommand = CreateManualIncomeExpenseCommand | CreateManualTransferCommand


class UpdateManualOperationCommandBase(ApplicationModel):
    operation_id: UUID
    amount: Decimal
    operation_date: date
    description: str | None
    expected_version: int


class UpdateManualIncomeExpenseCommand(UpdateManualOperationCommandBase):
    operation_type: OperationType
    account_id: UUID
    category_id: UUID | None
    property_id: UUID | None


class UpdateManualTransferCommand(UpdateManualOperationCommandBase):
    source_account_id: UUID
    destination_account_id: UUID


UpdateManualOperationCommand = UpdateManualIncomeExpenseCommand | UpdateManualTransferCommand


class NamedReferenceReadDto(ApplicationModel):
    id: UUID
    name: str


class AccountReferenceReadDto(NamedReferenceReadDto):
    currency: str


class ManualOperationMoneyReadDto(ApplicationModel):
    amount: Decimal
    currency: str


class ManualOperationReadDto(ApplicationModel):
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
