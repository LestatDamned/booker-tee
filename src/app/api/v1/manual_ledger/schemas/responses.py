from datetime import date
from uuid import UUID

from app.api.schemas import ApiModel
from app.features.ledger.domain.types import OperationStatus, OperationType


class ManualLedgerNamedReferenceApiResponse(ApiModel):
    id: UUID
    name: str


class ManualLedgerAccountReferenceApiResponse(ManualLedgerNamedReferenceApiResponse):
    currency: str


class ManualLedgerFilterOptionsApiResponse(ApiModel):
    accounts: list[ManualLedgerAccountReferenceApiResponse]
    categories: list[ManualLedgerNamedReferenceApiResponse]
    properties: list[ManualLedgerNamedReferenceApiResponse]
    per_page: list[int]


class ManualLedgerMoneyApiResponse(ApiModel):
    amount: str
    currency: str


class ManualOperationCapabilitiesApiResponse(ApiModel):
    can_edit: bool
    can_cancel: bool
    can_restore: bool
    can_delete: bool
    readonly_reason: str | None = None


class ManualOperationApiResponse(ApiModel):
    id: UUID
    version: int
    operation_type: OperationType
    operation_date: date
    description: str
    status: OperationStatus
    money: ManualLedgerMoneyApiResponse | None
    account: ManualLedgerNamedReferenceApiResponse | None
    source_account: ManualLedgerNamedReferenceApiResponse | None
    destination_account: ManualLedgerNamedReferenceApiResponse | None
    category: ManualLedgerNamedReferenceApiResponse | None
    property: ManualLedgerNamedReferenceApiResponse | None
    capabilities: ManualOperationCapabilitiesApiResponse


class ManualOperationEditApiResponse(ApiModel):
    operation: ManualOperationApiResponse
    filter_options: ManualLedgerFilterOptionsApiResponse


class ManualLedgerPaginationApiResponse(ApiModel):
    page: int
    per_page: int
    total: int
    total_pages: int
    has_previous: bool
    has_next: bool


class ManualLedgerCapabilitiesApiResponse(ApiModel):
    can_create: bool
    readonly_reason: str | None = None


class ManualLedgerListApiResponse(ApiModel):
    items: list[ManualOperationApiResponse]
    pagination: ManualLedgerPaginationApiResponse
    filter_options: ManualLedgerFilterOptionsApiResponse
    capabilities: ManualLedgerCapabilitiesApiResponse
    target_operation_id: UUID | None = None
