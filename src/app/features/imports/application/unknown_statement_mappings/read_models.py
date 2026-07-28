from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from uuid import UUID

from app.features.imports.application.unknown_statement_mappings.control_total_cells import (
    MappingControlTotalKind,
)
from app.features.imports.application.unknown_statement_mappings.dto import (
    MappedStatementRow,
    MappingControlTotalCellRef,
    StatementMappingSpec,
    UnknownStatementMappingWarning,
    UnsignedAmountDirection,
)
from app.features.imports.application.unknown_statement_mappings.mapping_defaults import (
    MappingDefaultSource,
)
from app.features.imports.application.unknown_statement_mappings.row_mapping import (
    explicit_amount_direction,
)
from app.features.imports.domain.types import UploadedDocumentStatus

MAX_MAPPING_PREVIEW_RAW_CHARS = 1_000
MAX_MAPPING_PREVIEW_DESCRIPTION_CHARS = 2_000


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
class UnknownStatementMappingReadModel:
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
class UnknownStatementMappingPreviewResult:
    rows: tuple[MappingPreviewRowDto, ...]
    total_row_count: int
    valid_row_count: int
    invalid_row_count: int
    row_limit: int
    rows_truncated: bool
    compatible_tables: tuple[MappingTableRefDto, ...]
    warnings: tuple[UnknownStatementMappingWarning, ...]
    can_import: bool
    control_totals: tuple["MappingResolvedControlTotalDto", ...] = ()
    reconciliation: "MappingBalanceReconciliationDto | None" = None


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


def mapping_preview_row(
    row: MappedStatementRow,
    spec: StatementMappingSpec,
) -> MappingPreviewRowDto:
    return MappingPreviewRowDto(
        table_ref=MappingTableRefDto(row.page_number, row.table_index),
        source_row_number=row.source_row_number + 1,
        operation_date=row.operation_date,
        operation_date_raw=_bounded_raw(row.operation_date_raw),
        posting_date=row.posting_date,
        posting_date_raw=_bounded_raw(row.posting_date_raw),
        description=(row.description or row.description_raw)[
            :MAX_MAPPING_PREVIEW_DESCRIPTION_CHARS
        ],
        amount=str(row.amount) if row.amount is not None else None,
        amount_raw=_bounded_raw(row.amount_raw),
        currency=row.currency,
        balance_after=(str(row.balance_after) if row.balance_after is not None else None),
        balance_after_raw=_bounded_raw(row.balance_after_raw),
        status=row.status,
        error_codes=mapping_row_error_codes(row, spec),
    )


def mapping_row_error_codes(
    row: MappedStatementRow,
    spec: StatementMappingSpec,
) -> tuple[MappingRowErrorCode, ...]:
    codes: list[MappingRowErrorCode] = []
    if row.operation_date is None:
        codes.append(
            MappingRowErrorCode.OPERATION_DATE_REQUIRED
            if not row.operation_date_raw.strip()
            else MappingRowErrorCode.OPERATION_DATE_INVALID
        )
    if row.posting_date_raw.strip() and row.posting_date is None:
        codes.append(MappingRowErrorCode.POSTING_DATE_INVALID)
    if row.amount is None:
        codes.extend(_amount_error_codes(row, spec))
    if row.balance_after_raw.strip() and row.balance_after is None:
        codes.append(MappingRowErrorCode.BALANCE_AFTER_INVALID)
    if row.description is None:
        codes.append(MappingRowErrorCode.DESCRIPTION_REQUIRED)
    return tuple(codes)


def _amount_error_codes(
    row: MappedStatementRow,
    spec: StatementMappingSpec,
) -> list[MappingRowErrorCode]:
    if spec.amount_column is not None:
        if (
            row.amount_raw.strip()
            and spec.unsigned_amount_direction is UnsignedAmountDirection.REQUIRE_SIGN
            and explicit_amount_direction(row.amount_raw) is None
        ):
            return [MappingRowErrorCode.UNSIGNED_AMOUNT_DIRECTION_REQUIRED]
        return [
            MappingRowErrorCode.AMOUNT_REQUIRED
            if not row.amount_raw.strip()
            else MappingRowErrorCode.AMOUNT_INVALID
        ]
    debit_raw, credit_raw = _split_amount_raw(row.amount_raw)
    if debit_raw and credit_raw:
        return [MappingRowErrorCode.DEBIT_AND_CREDIT_PRESENT]
    if debit_raw:
        return [MappingRowErrorCode.DEBIT_INVALID]
    if credit_raw:
        return [MappingRowErrorCode.CREDIT_INVALID]
    return [MappingRowErrorCode.AMOUNT_REQUIRED]


def _split_amount_raw(value: str) -> tuple[str, str]:
    debit = ""
    credit = ""
    for part in value.split(" / "):
        if part.startswith("debit: "):
            debit = part.removeprefix("debit: ").strip()
        elif part.startswith("credit: "):
            credit = part.removeprefix("credit: ").strip()
    return debit, credit


def _bounded_raw(value: str) -> str:
    return value[:MAX_MAPPING_PREVIEW_RAW_CHARS]
