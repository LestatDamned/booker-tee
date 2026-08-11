from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from app.api.schemas import ApiModel
from app.features.ledger.domain.types import OperationSource, OperationStatus, OperationType


class OperationNamedReferenceApiResponse(ApiModel):
    id: UUID
    name: str


class OperationAccountReferenceApiResponse(OperationNamedReferenceApiResponse):
    currency: str


class OperationFilterAccountOptionApiResponse(OperationAccountReferenceApiResponse):
    can_record_income: bool
    can_record_expense: bool
    can_transfer: bool


class OperationMoneyApiResponse(ApiModel):
    amount: str
    currency: str


class ImportOperationProvenanceApiResponse(ApiModel):
    kind: Literal["import"]
    uploaded_document_id: UUID | None
    raw_transaction_id: UUID | None


class DebtOperationProvenanceApiResponse(ApiModel):
    kind: Literal["debt"]
    debt_account_id: UUID | None


class SystemOperationProvenanceApiResponse(ApiModel):
    kind: Literal["system"]


OperationProvenanceApiResponse = Annotated[
    ImportOperationProvenanceApiResponse
    | DebtOperationProvenanceApiResponse
    | SystemOperationProvenanceApiResponse,
    Field(discriminator="kind"),
]


class OperationCapabilitiesApiResponse(ApiModel):
    can_edit: bool
    edit_kind: Literal["manual", "imported", "none"]
    can_cancel: bool
    can_restore: bool
    can_delete: bool
    readonly_reason: (
        Literal[
            "financial_write_forbidden",
            "operation_state_readonly",
            "source_workflow_required",
            "system_operation",
        ]
        | None
    )


class OperationApiResponse(ApiModel):
    id: UUID
    version: int
    operation_type: OperationType
    source: OperationSource
    status: OperationStatus
    operation_date: date
    description: str
    money: OperationMoneyApiResponse | None
    account: OperationAccountReferenceApiResponse | None
    source_account: OperationAccountReferenceApiResponse | None
    destination_account: OperationAccountReferenceApiResponse | None
    category: OperationNamedReferenceApiResponse | None
    property: OperationNamedReferenceApiResponse | None
    provenance: OperationProvenanceApiResponse | None
    capabilities: OperationCapabilitiesApiResponse


class OperationsPaginationApiResponse(ApiModel):
    page: int
    per_page: int
    total: int
    total_pages: int
    has_previous: bool
    has_next: bool


class OperationsFilterOptionsApiResponse(ApiModel):
    accounts: list[OperationFilterAccountOptionApiResponse]
    categories: list[OperationNamedReferenceApiResponse]
    properties: list[OperationNamedReferenceApiResponse]
    sources: list[OperationSource]
    per_page: list[int]


class OperationsCapabilitiesApiResponse(ApiModel):
    can_create: bool
    readonly_reason: str | None = None


class OperationsListApiResponse(ApiModel):
    items: list[OperationApiResponse]
    pagination: OperationsPaginationApiResponse
    filter_options: OperationsFilterOptionsApiResponse
    capabilities: OperationsCapabilitiesApiResponse
    target_operation_id: UUID | None = None
    target_operation: OperationApiResponse | None = None
