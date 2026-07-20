from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator
from pydantic_core import PydanticCustomError

from app.api.schemas import ApiModel
from app.features.ledger.models import OperationStatus, OperationType

EntryDirection = Literal["inflow", "outflow", "transfer"]


class ManualOperationCreateBase(ApiModel):
    amount: str
    operation_date: date
    description: str = ""

    @field_validator("amount")
    @classmethod
    def require_positive_decimal_string(cls, amount: str) -> str:
        normalized = amount.strip().replace(",", ".")
        try:
            decimal_amount = Decimal(normalized)
        except InvalidOperation as error:
            raise PydanticCustomError(
                "decimal_amount",
                "Введите корректную сумму.",
            ) from error
        if not decimal_amount.is_finite() or decimal_amount <= Decimal("0"):
            raise PydanticCustomError(
                "positive_amount",
                "Сумма должна быть больше нуля.",
            )
        return normalized

    @property
    def decimal_amount(self) -> Decimal:
        return Decimal(self.amount)


class ManualIncomeExpenseCreateRequest(ManualOperationCreateBase):
    operation_type: Literal[OperationType.INCOME, OperationType.EXPENSE]
    account_id: UUID
    category_id: UUID | None = None
    property_id: UUID | None = None


class ManualTransferCreateRequest(ManualOperationCreateBase):
    operation_type: Literal[OperationType.TRANSFER]
    source_account_id: UUID
    destination_account_id: UUID


ManualOperationCreateRequest = Annotated[
    ManualIncomeExpenseCreateRequest | ManualTransferCreateRequest,
    Field(discriminator="operation_type"),
]


class ManualOperationUpdateBase(ManualOperationCreateBase):
    version: int

    @field_validator("version")
    @classmethod
    def require_current_version(cls, version: int) -> int:
        if version < 1:
            raise PydanticCustomError(
                "current_operation_version",
                "Загрузите актуальную версию операции.",
            )
        return version


class ManualIncomeExpenseUpdateRequest(ManualOperationUpdateBase):
    operation_type: Literal[OperationType.INCOME, OperationType.EXPENSE]
    account_id: UUID
    category_id: UUID | None = None
    property_id: UUID | None = None


class ManualTransferUpdateRequest(ManualOperationUpdateBase):
    operation_type: Literal[OperationType.TRANSFER]
    source_account_id: UUID
    destination_account_id: UUID


ManualOperationUpdateRequest = Annotated[
    ManualIncomeExpenseUpdateRequest | ManualTransferUpdateRequest,
    Field(discriminator="operation_type"),
]


class ManualOperationLifecycleRequest(ApiModel):
    version: int = Field(ge=1)


class ManualLedgerNamedReference(ApiModel):
    id: UUID
    name: str


class ManualLedgerAccountReference(ManualLedgerNamedReference):
    currency: str


class ManualLedgerFilterOptions(ApiModel):
    accounts: list[ManualLedgerAccountReference]
    categories: list[ManualLedgerNamedReference]
    properties: list[ManualLedgerNamedReference]
    per_page: list[int]


class ManualLedgerMoney(ApiModel):
    amount: str
    currency: str
    operation_type: OperationType
    entry_direction: EntryDirection


class ManualOperationCapabilities(ApiModel):
    can_edit: bool
    can_cancel: bool
    can_restore: bool
    can_delete: bool
    readonly_reason: str | None = None


class ManualOperationResponse(ApiModel):
    id: UUID
    version: int
    operation_date: str
    description: str
    status: OperationStatus
    money: ManualLedgerMoney | None
    account: ManualLedgerNamedReference | None
    source_account: ManualLedgerNamedReference | None
    destination_account: ManualLedgerNamedReference | None
    category: ManualLedgerNamedReference | None
    property: ManualLedgerNamedReference | None
    capabilities: ManualOperationCapabilities


class ManualOperationEditResponse(ApiModel):
    operation: ManualOperationResponse
    filter_options: ManualLedgerFilterOptions


class ManualLedgerPaginationResponse(ApiModel):
    page: int
    per_page: int
    total: int
    total_pages: int
    has_previous: bool
    has_next: bool


class ManualLedgerCapabilities(ApiModel):
    can_create: bool
    readonly_reason: str | None = None


class ManualLedgerListResponse(ApiModel):
    items: list[ManualOperationResponse]
    pagination: ManualLedgerPaginationResponse
    filter_options: ManualLedgerFilterOptions
    capabilities: ManualLedgerCapabilities
    target_operation_id: UUID | None = None
