from datetime import date, datetime
from typing import Literal
from uuid import UUID

from app.api.schemas import ApiModel
from app.features.imports.application.documents.detail_reading import (
    ImportDocumentActionBlockingReason,
    ImportDocumentDetailNextStep,
    ImportDocumentDetailValidationReasonCode,
    ImportDocumentWorkflowStepState,
)
from app.features.imports.application.documents.listing import (
    ImportDocumentListReadonlyReasonCode,
    ImportDocumentNextStepKind,
)
from app.features.imports.models import (
    ParseAttemptStatus,
    RawTransactionStatus,
    UploadedDocumentStatus,
)


class ImportDocumentListAccountApiResponse(ApiModel):
    id: UUID
    name: str
    currency: str
    bank_name: str | None


class ImportDocumentStatementPeriodApiResponse(ApiModel):
    start: date
    end: date


class ImportDocumentListItemCapabilitiesApiResponse(ApiModel):
    can_open_detail: bool
    can_map: bool
    can_review: bool


class ImportDocumentListItemApiResponse(ApiModel):
    id: UUID
    filename: str
    status: UploadedDocumentStatus
    created_at: datetime
    file_size_bytes: int | None
    detected_bank_name: str | None
    statement_period: ImportDocumentStatementPeriodApiResponse | None
    account: ImportDocumentListAccountApiResponse | None
    total_row_count: int
    reviewable_row_count: int
    capabilities: ImportDocumentListItemCapabilitiesApiResponse
    next_step_kind: ImportDocumentNextStepKind


class ImportDocumentListCapabilitiesApiResponse(ApiModel):
    can_upload: bool
    readonly_reason_code: ImportDocumentListReadonlyReasonCode | None


class ImportDocumentListPaginationApiResponse(ApiModel):
    page: int
    per_page: int
    total: int
    total_pages: int
    has_previous: bool
    has_next: bool


class ImportDocumentListFilterOptionsApiResponse(ApiModel):
    accounts: list[ImportDocumentListAccountApiResponse]
    per_page: list[int]


class ImportDocumentListSummaryApiResponse(ApiModel):
    total_document_count: int
    attention_document_count: int


class ImportDocumentListApiResponse(ApiModel):
    workspace_id: UUID
    workspace_name: str
    items: list[ImportDocumentListItemApiResponse]
    pagination: ImportDocumentListPaginationApiResponse
    filter_options: ImportDocumentListFilterOptionsApiResponse
    summary: ImportDocumentListSummaryApiResponse
    capabilities: ImportDocumentListCapabilitiesApiResponse


class ImportUploadReferenceAccountApiResponse(ApiModel):
    id: UUID
    name: str
    currency: str
    bank_name: str | None


class ImportUploadReferenceApiResponse(ApiModel):
    accounts: list[ImportUploadReferenceAccountApiResponse]
    accepted_extensions: list[str]
    accepted_content_types: list[str]
    max_file_size_bytes: int
    can_upload: bool


class ImportDocumentUploadApiResponse(ApiModel):
    id: UUID
    status: UploadedDocumentStatus
    replayed: bool
    navigation_target: Literal["document_detail"]
    next_step: ImportDocumentDetailNextStep


class ImportDocumentDetailAccountApiResponse(ApiModel):
    id: UUID
    name: str
    currency: str


class ImportDocumentDetailWorkflowApiResponse(ApiModel):
    upload: ImportDocumentWorkflowStepState
    extract: ImportDocumentWorkflowStepState
    mapping: ImportDocumentWorkflowStepState
    review: ImportDocumentWorkflowStepState
    ledger: ImportDocumentWorkflowStepState


class ImportDocumentDetailValidationApiResponse(ApiModel):
    status: str
    reason_code: ImportDocumentDetailValidationReasonCode
    message: str
    extracted_count: int | None
    calculated_total_inflow: str | None
    calculated_total_outflow: str | None
    ignored_row_count: int
    ignored_total_inflow: str | None
    ignored_total_outflow: str | None
    currency: str | None
    table_count: int | None
    needs_mapping: bool


class ImportDocumentDetailRawRowApiResponse(ApiModel):
    row_index: int
    status: RawTransactionStatus
    display_date: date | str | None
    amount: str | None
    amount_raw: str | None
    currency: str | None
    description: str
    normalization_error: str


class ImportDocumentDetailAttemptApiResponse(ApiModel):
    id: UUID
    status: ParseAttemptStatus
    parser_name: str
    parser_version: str | None
    started_at: datetime
    finished_at: datetime | None
    message: str


class ImportDocumentDetailCollectionApiResponse[T](ApiModel):
    items: list[T]
    total: int
    limit: int


class ImportDocumentActionCapabilityApiResponse(ApiModel):
    allowed: bool
    blocking_reason_codes: list[ImportDocumentActionBlockingReason]


class ImportDocumentDetailCapabilitiesApiResponse(ApiModel):
    can_manage: bool
    reparse: ImportDocumentActionCapabilityApiResponse
    ignore: ImportDocumentActionCapabilityApiResponse
    delete: ImportDocumentActionCapabilityApiResponse


class ImportDocumentDetailApiResponse(ApiModel):
    id: UUID
    filename: str
    status: UploadedDocumentStatus
    bank_name: str | None
    statement_type: str | None
    statement_period_start: date | None
    statement_period_end: date | None
    file_size_bytes: int | None
    created_at: datetime | None
    updated_at: datetime | None
    account: ImportDocumentDetailAccountApiResponse | None
    workflow: ImportDocumentDetailWorkflowApiResponse
    next_step: ImportDocumentDetailNextStep
    validation: ImportDocumentDetailValidationApiResponse | None
    raw_rows: ImportDocumentDetailCollectionApiResponse[ImportDocumentDetailRawRowApiResponse]
    parse_attempts: ImportDocumentDetailCollectionApiResponse[
        ImportDocumentDetailAttemptApiResponse
    ]
    capabilities: ImportDocumentDetailCapabilitiesApiResponse


class ImportDocumentMutationApiRequest(ApiModel):
    expected_status: UploadedDocumentStatus


class ImportDocumentDeleteApiResponse(ApiModel):
    id: UUID
    deleted: bool
    navigation_target: str
