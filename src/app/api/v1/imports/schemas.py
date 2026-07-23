from datetime import date, datetime
from uuid import UUID

from app.api.schemas import ApiModel
from app.features.imports.application.documents.listing import (
    ImportDocumentListReadonlyReasonCode,
    ImportDocumentNextStepKind,
)
from app.features.imports.models import UploadedDocumentStatus


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
