from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from app.features.imports.documents.types import UploadedDocumentStatus


class UnsignedAmountDirection(StrEnum):
    REQUIRE_SIGN = "require_sign"
    INCOME = "income"
    EXPENSE = "expense"


class MappingDefaultSource(StrEnum):
    TEMPLATE = "template"
    ANALYZER = "analyzer"
    FALLBACK = "fallback"


class MappingControlTotalKind(StrEnum):
    OPENING_BALANCE = "opening_balance"
    CLOSING_BALANCE = "closing_balance"


class MappingBlockingReasonCode(StrEnum):
    ACCOUNT_REQUIRED = "account_required"
    RAW_TABLES_UNAVAILABLE = "raw_tables_unavailable"
    MAPPING_NOT_REQUIRED = "mapping_not_required"
    CONFIRMED_ROWS_EXIST = "confirmed_rows_exist"


class MappingRowErrorCode(StrEnum):
    OPERATION_DATE_REQUIRED = "operation_date_required"
    OPERATION_DATE_INVALID = "operation_date_invalid"
    POSTING_DATE_INVALID = "posting_date_invalid"
    AMOUNT_REQUIRED = "amount_required"
    AMOUNT_INVALID = "amount_invalid"
    UNSIGNED_AMOUNT_DIRECTION_REQUIRED = "unsigned_amount_direction_required"
    DEBIT_INVALID = "debit_invalid"
    CREDIT_INVALID = "credit_invalid"
    DEBIT_AND_CREDIT_PRESENT = "debit_and_credit_present"
    BALANCE_AFTER_INVALID = "balance_after_invalid"
    DESCRIPTION_REQUIRED = "description_required"


@dataclass(frozen=True)
class MappingControlTotalCellRef:
    page_number: int
    table_index: int
    row_number: int
    column_index: int


@dataclass(frozen=True)
class StatementMappingSpec:
    page_number: int
    table_index: int
    operation_date_column: int
    description_column: int
    amount_column: int | None
    currency_column: int | None
    first_data_row: int
    default_currency: str
    unsigned_amount_direction: UnsignedAmountDirection
    posting_date_column: int | None = None
    debit_amount_column: int | None = None
    credit_amount_column: int | None = None
    balance_after_column: int | None = None
    opening_balance_cell: MappingControlTotalCellRef | None = None
    closing_balance_cell: MappingControlTotalCellRef | None = None


@dataclass(frozen=True)
class MappingTemplateSnapshot:
    id: UUID
    name: str
    bank_name: str | None
    statement_type: str | None
    default_currency: str
    column_mapping: dict[str, object]


@dataclass(frozen=True)
class ResolvedMappingDefault:
    spec: StatementMappingSpec
    source: MappingDefaultSource
    template_id: UUID | None


@dataclass(frozen=True)
class MappedStatementRow:
    page_number: int
    table_index: int
    source_row_number: int
    operation_date_raw: str
    operation_date: date | None
    description_raw: str
    description: str | None
    amount_raw: str
    amount: Decimal | None
    currency_raw: str
    currency: str
    status: str
    error: str
    posting_date_raw: str = ""
    posting_date: date | None = None
    balance_after_raw: str = ""
    balance_after: Decimal | None = None


@dataclass(frozen=True)
class UnknownStatementMappingWarning:
    code: str
    severity: str
    fields: list[str] = field(default_factory=list)
    affected_row_count: int | None = None


@dataclass(frozen=True)
class StatementMappingResult:
    rows: list[MappedStatementRow]
    warnings: list[UnknownStatementMappingWarning] = field(default_factory=list)

    @property
    def valid_count(self) -> int:
        return sum(1 for row in self.rows if row.status == "valid")

    @property
    def error_count(self) -> int:
        return sum(1 for row in self.rows if row.status == "error")


@dataclass(frozen=True)
class MappingTableRefDto:
    page_number: int
    table_index: int


@dataclass(frozen=True)
class MappingAccountDto:
    id: UUID
    name: str
    currency: str


@dataclass(frozen=True)
class MappingCapabilityDto:
    allowed: bool
    blocking_reason_codes: tuple[MappingBlockingReasonCode, ...]


@dataclass(frozen=True)
class MappingColumnCandidateDto:
    field: str
    column_index: int
    header: str


@dataclass(frozen=True)
class MappingSuggestionReasonDto:
    field: str
    column_index: int
    header: str
    evidence: str
    matched_count: int | None
    sample_count: int | None


@dataclass(frozen=True)
class MappingSuggestionDto:
    spec: StatementMappingSpec
    reasons: tuple[MappingSuggestionReasonDto, ...]
    warning_codes: tuple[str, ...]


@dataclass(frozen=True)
class MappingSourceRowDto:
    row_number: int
    cells: tuple[str, ...]


@dataclass(frozen=True)
class MappingSourceTableDto:
    ref: MappingTableRefDto
    source_type: str
    row_count: int
    column_count: int
    is_continuation: bool
    sample_rows: tuple[MappingSourceRowDto, ...]
    candidates: tuple[MappingColumnCandidateDto, ...]
    suggestion: MappingSuggestionDto | None


@dataclass(frozen=True)
class MappingControlTotalCandidateDto:
    kind: MappingControlTotalKind
    cell: MappingControlTotalCellRef
    label: str
    raw_value: str
    amount: str
    currency: str
    confidence: float


@dataclass(frozen=True)
class MappingSourceRowsDto:
    table_ref: MappingTableRefDto
    rows: tuple[MappingSourceRowDto, ...]
    total_row_count: int
    start_row_number: int
    row_limit: int
    has_previous: bool
    has_next: bool


@dataclass(frozen=True)
class MappingTemplateDto:
    id: UUID
    name: str


@dataclass(frozen=True)
class StatementMappingOverview:
    document_id: UUID
    filename: str
    status: UploadedDocumentStatus
    bank_name: str | None
    statement_type: str | None
    account: MappingAccountDto | None
    default_currency: str
    capability: MappingCapabilityDto
    default_mapping: StatementMappingSpec
    default_source: MappingDefaultSource
    selected_template_id: UUID | None
    templates: tuple[MappingTemplateDto, ...]
    tables: tuple[MappingSourceTableDto, ...]
    total_table_count: int
    tables_truncated: bool
    control_total_candidates: tuple[MappingControlTotalCandidateDto, ...] = ()


@dataclass(frozen=True)
class MappingPreviewRowDto:
    table_ref: MappingTableRefDto
    source_row_number: int
    operation_date: date | None
    operation_date_raw: str
    posting_date: date | None
    posting_date_raw: str
    description: str
    amount: str | None
    amount_raw: str
    currency: str
    balance_after: str | None
    balance_after_raw: str
    status: str
    error_codes: tuple[MappingRowErrorCode, ...]


@dataclass(frozen=True)
class MappingResolvedControlTotalDto:
    kind: MappingControlTotalKind
    cell: MappingControlTotalCellRef
    raw_value: str
    amount: str
    currency: str


@dataclass(frozen=True)
class MappingBalanceReconciliationDto:
    opening_balance: str
    movement: str
    calculated_closing_balance: str
    statement_closing_balance: str
    difference: str
    matches: bool


@dataclass(frozen=True)
class StatementMappingPreview:
    rows: tuple[MappingPreviewRowDto, ...]
    total_row_count: int
    valid_row_count: int
    invalid_row_count: int
    row_limit: int
    rows_truncated: bool
    compatible_tables: tuple[MappingTableRefDto, ...]
    warnings: tuple[UnknownStatementMappingWarning, ...]
    can_import: bool
    control_totals: tuple[MappingResolvedControlTotalDto, ...] = ()
    reconciliation: MappingBalanceReconciliationDto | None = None


@dataclass(frozen=True)
class StatementMappingImportResult:
    document_id: UUID
    document_status: UploadedDocumentStatus
    imported_row_count: int
    template_id: UUID | None
    replayed: bool
