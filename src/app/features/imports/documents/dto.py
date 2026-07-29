"""Data transfer objects for imported document reads."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from math import ceil
from uuid import UUID

from app.features.imports.documents.types import ParseAttemptStatus, UploadedDocumentStatus
from app.features.imports.documents.validation_report import (
    StoredValidationReport,
)
from app.features.imports.statements.types import RawTransactionStatus
from app.shared.schemas import ApplicationModel

DEFAULT_IMPORT_DOCUMENTS_PER_PAGE = 25
IMPORT_DOCUMENTS_PER_PAGE_OPTIONS = (25, 50, 100)


class ImportDocumentAccountDto(ApplicationModel):
    id: UUID
    name: str
    currency: str
    bank_name: str | None = None


class ImportRawTransactionRow(ApplicationModel):
    row_index: int
    status: RawTransactionStatus
    display_date: date | str | None
    amount: Decimal | None
    amount_raw: str | None
    currency: str | None
    description: str
    normalization_error: str
    linked_operation_id: UUID | None = None


class ImportParseAttemptSnapshot(ApplicationModel):
    id: UUID
    status: ParseAttemptStatus
    parser_name: str
    parser_version: str | None
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None
    validation: StoredValidationReport | None
    raw_tables: list[dict[str, object]] | None

    @property
    def message(self) -> str:
        if self.error_message:
            return self.error_message
        if self.validation is None:
            return ""
        return self.validation.message


class ImportDocumentSnapshot(ApplicationModel):
    id: UUID
    status: UploadedDocumentStatus
    original_filename: str
    bank_name: str | None
    statement_type: str | None
    account: ImportDocumentAccountDto | None
    validation: StoredValidationReport | None
    raw_transactions: list[ImportRawTransactionRow]
    parse_attempts: list[ImportParseAttemptSnapshot]
    statement_period_start: date | None = None
    statement_period_end: date | None = None
    file_size_bytes: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ImportDocumentNextStepKind(StrEnum):
    DETAIL = "detail"
    MAPPING = "mapping"
    REVIEW = "review"


class ImportDocumentListReadonlyReasonCode(StrEnum):
    IMPORT_MANAGEMENT_FORBIDDEN = "import_management_forbidden"


class ImportDocumentListState(StrEnum):
    ATTENTION = "attention"
    PROCESSING = "processing"
    COMPLETED = "completed"


class ImportDocumentListSort(StrEnum):
    CREATED_AT_DESC = "created_at_desc"
    CREATED_AT_ASC = "created_at_asc"


class ImportDocumentListFilters(ApplicationModel):
    state: ImportDocumentListState | None = None
    account_id: UUID | None = None
    period_from: date | None = None
    period_to: date | None = None
    sort: ImportDocumentListSort = ImportDocumentListSort.CREATED_AT_DESC

    @property
    def is_active(self) -> bool:
        return any((self.state, self.account_id, self.period_from, self.period_to))


class ImportDocumentListPagination(ApplicationModel):
    page: int = 1
    per_page: int = DEFAULT_IMPORT_DOCUMENTS_PER_PAGE

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


class ImportDocumentListPageDto(ApplicationModel):
    page: int
    per_page: int
    total: int

    @property
    def total_pages(self) -> int:
        return max(1, ceil(self.total / self.per_page))

    @property
    def has_previous(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages


class ImportDocumentListRow(ApplicationModel):
    id: UUID
    filename: str
    status: UploadedDocumentStatus
    created_at: datetime
    file_size_bytes: int | None
    detected_bank_name: str | None
    statement_period_start: date | None
    statement_period_end: date | None
    account_id: UUID | None
    account_name: str | None
    account_currency: str | None
    account_bank_name: str | None
    total_row_count: int
    reviewable_row_count: int
    latest_parse_attempt_status: ParseAttemptStatus | None


class ImportDocumentStatementPeriodDto(ApplicationModel):
    start: date
    end: date


class ImportDocumentListItemCapabilitiesDto(ApplicationModel):
    can_open_detail: bool
    can_map: bool
    can_review: bool


class ImportDocumentListItemDto(ApplicationModel):
    id: UUID
    filename: str
    status: UploadedDocumentStatus
    created_at: datetime
    file_size_bytes: int | None
    detected_bank_name: str | None
    statement_period: ImportDocumentStatementPeriodDto | None
    account: ImportDocumentAccountDto | None
    total_row_count: int
    reviewable_row_count: int
    capabilities: ImportDocumentListItemCapabilitiesDto
    next_step_kind: ImportDocumentNextStepKind


class ImportDocumentListCapabilitiesDto(ApplicationModel):
    can_upload: bool
    readonly_reason_code: ImportDocumentListReadonlyReasonCode | None


class ImportDocumentListFilterOptionsDto(ApplicationModel):
    accounts: tuple[ImportDocumentAccountDto, ...]
    per_page: tuple[int, ...]


class ImportDocumentListSummaryDto(ApplicationModel):
    total_document_count: int
    attention_document_count: int


class ImportDocumentListReadModel(ApplicationModel):
    workspace_id: UUID
    workspace_name: str
    items: tuple[ImportDocumentListItemDto, ...]
    pagination: ImportDocumentListPageDto
    filter_options: ImportDocumentListFilterOptionsDto
    summary: ImportDocumentListSummaryDto
    capabilities: ImportDocumentListCapabilitiesDto


class ImportDocumentWorkflowStepState(StrEnum):
    PENDING = "pending"
    CURRENT = "current"
    DONE = "done"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class ImportDocumentDetailNextStep(StrEnum):
    MAPPING = "mapping"
    REVIEW = "review"
    UPLOAD = "upload"
    DOCUMENT_LIST = "document_list"


class ImportDocumentActionBlockingReason(StrEnum):
    IMPORT_MANAGEMENT_FORBIDDEN = "import_management_forbidden"
    LINKED_OPERATIONS_EXIST = "linked_operations_exist"
    ALREADY_IGNORED = "already_ignored"


class ImportDocumentDetailValidationReasonCode(StrEnum):
    TOTALS_MATCH = "totals_match"
    ROWS_NEED_REVIEW = "rows_need_review"
    BALANCE_CHAIN_MISMATCH = "balance_chain_mismatch"
    CONTROL_TOTALS_UNAVAILABLE = "control_totals_unavailable"
    CONTROL_TOTALS_MISMATCH = "control_totals_mismatch"
    IGNORED_ROWS_EXPLAIN_MISMATCH = "ignored_rows_explain_mismatch"
    NEEDS_MAPPING = "needs_mapping"
    VALIDATION_FAILED = "validation_failed"


class ImportDocumentDetailWorkflowDto(ApplicationModel):
    upload: ImportDocumentWorkflowStepState
    extract: ImportDocumentWorkflowStepState
    mapping: ImportDocumentWorkflowStepState
    review: ImportDocumentWorkflowStepState
    ledger: ImportDocumentWorkflowStepState


class ImportDocumentDetailValidationDto(ApplicationModel):
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


class ImportDocumentDetailRawRowDto(ApplicationModel):
    row_index: int
    status: RawTransactionStatus
    display_date: date | str | None
    amount: Decimal | None
    amount_raw: str | None
    currency: str | None
    description: str
    normalization_error: str


class ImportDocumentDetailAttemptDto(ApplicationModel):
    id: UUID
    status: ParseAttemptStatus
    parser_name: str
    parser_version: str | None
    started_at: datetime
    finished_at: datetime | None
    message: str


class ImportDocumentDetailCollectionDto[T](ApplicationModel):
    items: tuple[T, ...]
    total: int
    limit: int


class ImportDocumentActionCapabilityDto(ApplicationModel):
    allowed: bool
    blocking_reason_codes: tuple[ImportDocumentActionBlockingReason, ...]


class ImportDocumentDetailCapabilitiesDto(ApplicationModel):
    can_manage: bool
    ignore: ImportDocumentActionCapabilityDto
    delete: ImportDocumentActionCapabilityDto


class ImportDocumentDetailReadModel(ApplicationModel):
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
    account: ImportDocumentAccountDto | None
    workflow: ImportDocumentDetailWorkflowDto
    next_step: ImportDocumentDetailNextStep
    validation: ImportDocumentDetailValidationDto | None
    raw_rows: ImportDocumentDetailCollectionDto[ImportDocumentDetailRawRowDto]
    parse_attempts: ImportDocumentDetailCollectionDto[ImportDocumentDetailAttemptDto]
    capabilities: ImportDocumentDetailCapabilitiesDto
