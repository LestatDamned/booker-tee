from datetime import date
from typing import Literal
from uuid import UUID

from app.features.imports.documents.types import UploadedDocumentStatus
from app.features.imports.mapping.dto import (
    MappingBlockingReasonCode,
    MappingControlTotalCellRef,
    MappingControlTotalKind,
    MappingDefaultSource,
    MappingRowErrorCode,
    StatementMappingSpec,
    UnknownStatementMappingWarning,
    UnsignedAmountDirection,
)
from app.shared.schemas import ApplicationModel


class MappingTableRefDto(ApplicationModel):
    page_number: int
    table_index: int


class MappingControlTotalCellDto(ApplicationModel):
    table_ref: MappingTableRefDto
    row_number: int
    column_index: int

    @classmethod
    def from_ref(cls, cell: MappingControlTotalCellRef) -> "MappingControlTotalCellDto":
        return cls(
            table_ref=MappingTableRefDto(
                page_number=cell.page_number,
                table_index=cell.table_index,
            ),
            row_number=cell.row_number + 1,
            column_index=cell.column_index,
        )


class MappingCommandDto(ApplicationModel):
    table_ref: MappingTableRefDto
    operation_date_column: int
    posting_date_column: int | None
    description_column: int
    amount_column: int | None
    debit_amount_column: int | None
    credit_amount_column: int | None
    currency_column: int | None
    balance_after_column: int | None
    first_data_row_number: int
    default_currency: str
    unsigned_amount_direction: UnsignedAmountDirection
    opening_balance_cell: MappingControlTotalCellDto | None
    closing_balance_cell: MappingControlTotalCellDto | None

    @classmethod
    def from_spec(cls, spec: StatementMappingSpec) -> "MappingCommandDto":
        return cls(
            table_ref=MappingTableRefDto(
                page_number=spec.page_number,
                table_index=spec.table_index,
            ),
            operation_date_column=spec.operation_date_column,
            posting_date_column=spec.posting_date_column,
            description_column=spec.description_column,
            amount_column=spec.amount_column,
            debit_amount_column=spec.debit_amount_column,
            credit_amount_column=spec.credit_amount_column,
            currency_column=spec.currency_column,
            balance_after_column=spec.balance_after_column,
            first_data_row_number=spec.first_data_row + 1,
            default_currency=spec.default_currency,
            unsigned_amount_direction=spec.unsigned_amount_direction,
            opening_balance_cell=(
                MappingControlTotalCellDto.from_ref(spec.opening_balance_cell)
                if spec.opening_balance_cell is not None
                else None
            ),
            closing_balance_cell=(
                MappingControlTotalCellDto.from_ref(spec.closing_balance_cell)
                if spec.closing_balance_cell is not None
                else None
            ),
        )


class MappingAccountDto(ApplicationModel):
    id: UUID
    name: str
    currency: str


class MappingCapabilityDto(ApplicationModel):
    allowed: bool
    blocking_reason_codes: tuple[MappingBlockingReasonCode, ...]


class MappingColumnCandidateDto(ApplicationModel):
    field: str
    column_index: int
    header: str


class MappingSuggestionReasonDto(ApplicationModel):
    field: str
    column_index: int
    header: str
    evidence: str
    matched_count: int | None
    sample_count: int | None


class MappingSuggestionDto(ApplicationModel):
    mapping: MappingCommandDto
    reasons: tuple[MappingSuggestionReasonDto, ...]
    warning_codes: tuple[str, ...]


class MappingSourceRowDto(ApplicationModel):
    row_number: int
    cells: tuple[str, ...]


class MappingSourceTableDto(ApplicationModel):
    ref: MappingTableRefDto
    source_type: str
    row_count: int
    column_count: int
    is_continuation: bool
    sample_rows: tuple[MappingSourceRowDto, ...]
    candidates: tuple[MappingColumnCandidateDto, ...]
    suggestion: MappingSuggestionDto | None


class MappingControlTotalCandidateDto(ApplicationModel):
    kind: MappingControlTotalKind
    cell: MappingControlTotalCellDto
    label: str
    raw_value: str
    amount: str
    currency: str
    confidence: float


class MappingSourceRowsDto(ApplicationModel):
    table_ref: MappingTableRefDto
    rows: tuple[MappingSourceRowDto, ...]
    total_row_count: int
    start_row_number: int
    row_limit: int
    has_previous: bool
    has_next: bool


class MappingTemplateDto(ApplicationModel):
    id: UUID
    name: str


class StatementMappingOverview(ApplicationModel):
    document_id: UUID
    filename: str
    status: UploadedDocumentStatus
    bank_name: str | None
    statement_type: str | None
    account: MappingAccountDto | None
    default_currency: str
    capability: MappingCapabilityDto
    default_mapping: MappingCommandDto
    default_source: MappingDefaultSource
    selected_template_id: UUID | None
    templates: tuple[MappingTemplateDto, ...]
    tables: tuple[MappingSourceTableDto, ...]
    total_table_count: int
    tables_truncated: bool
    control_total_candidates: tuple[MappingControlTotalCandidateDto, ...] = ()


class MappingPreviewRowDto(ApplicationModel):
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
    status: Literal["valid", "error"]
    error_codes: tuple[MappingRowErrorCode, ...]


class MappingResolvedControlTotalDto(ApplicationModel):
    kind: MappingControlTotalKind
    cell: MappingControlTotalCellDto
    raw_value: str
    amount: str
    currency: str


class MappingBalanceReconciliationDto(ApplicationModel):
    opening_balance: str
    movement: str
    calculated_closing_balance: str
    statement_closing_balance: str
    difference: str
    matches: bool


class MappingWarningDto(ApplicationModel):
    code: str
    severity: Literal["warning", "error"]
    fields: tuple[str, ...]
    affected_row_count: int | None

    @classmethod
    def from_mapping_warning(
        cls,
        warning: UnknownStatementMappingWarning,
    ) -> "MappingWarningDto":
        return cls(
            code=warning.code,
            severity=warning.severity,
            fields=tuple(_warning_field(field) for field in warning.fields),
            affected_row_count=warning.affected_row_count,
        )


class StatementMappingPreview(ApplicationModel):
    rows: tuple[MappingPreviewRowDto, ...]
    total_row_count: int
    valid_row_count: int
    invalid_row_count: int
    row_limit: int
    rows_truncated: bool
    compatible_tables: tuple[MappingTableRefDto, ...]
    warnings: tuple[MappingWarningDto, ...]
    can_import: bool
    control_totals: tuple[MappingResolvedControlTotalDto, ...] = ()
    reconciliation: MappingBalanceReconciliationDto | None = None


def _warning_field(field: str) -> str:
    return {
        "operation_date": "operationDateColumn",
        "posting_date": "postingDateColumn",
        "description": "descriptionColumn",
        "amount": "amountColumn",
        "debit_amount": "debitAmountColumn",
        "credit_amount": "creditAmountColumn",
        "currency": "currencyColumn",
        "balance_after": "balanceAfterColumn",
        "unsigned_amount_direction": "unsignedAmountDirection",
    }.get(field, field)
