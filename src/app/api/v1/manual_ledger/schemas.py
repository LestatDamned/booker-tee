from typing import Literal
from uuid import UUID

from app.api.schemas import ApiModel
from app.features.ledger.models import OperationStatus, OperationType

EntryDirection = Literal["inflow", "outflow", "transfer"]


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
