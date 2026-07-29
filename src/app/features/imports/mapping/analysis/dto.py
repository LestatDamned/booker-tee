from enum import StrEnum

from pydantic import Field

from app.features.imports.documents.validation_report import StoredValidationReport
from app.features.imports.statements.dto import StatementControlTotals
from app.shared.schemas import ApplicationModel


class UnknownStatementColumnCandidate(ApplicationModel):
    field: str
    column_index: int
    header: str


class UnknownStatementColumnProfile(ApplicationModel):
    column_index: int
    header: str
    sample_count: int
    non_empty_count: int
    date_like_count: int
    money_like_count: int
    currency_like_count: int
    description_like_count: int
    header_matches: list[str]


class UnknownStatementMappingSuggestionWarning(ApplicationModel):
    code: str
    fields: list[str]


class UnknownStatementMappingSuggestionReason(ApplicationModel):
    field: str
    column_index: int
    header: str
    evidence: str
    matched_count: int | None = None
    sample_count: int | None = None


class UnknownStatementMappingSuggestion(ApplicationModel):
    operation_date_column: int
    posting_date_column: int | None
    description_column: int
    amount_column: int | None
    debit_amount_column: int | None
    credit_amount_column: int | None
    currency_column: int | None
    balance_after_column: int | None
    first_data_row: int
    reasons: list[UnknownStatementMappingSuggestionReason]
    warnings: list[UnknownStatementMappingSuggestionWarning]


class UnknownStatementContinuationMappingField(ApplicationModel):
    field: str
    column_index: int


class TextCandidateTable(ApplicationModel):
    page_number: int
    table_index: int
    rows: list[list[str]]


class UnknownStatementTablePreview(ApplicationModel):
    page_number: int
    table_index: int
    row_count: int
    column_count: int
    preview_row_count: int
    rows: list[list[str]]
    column_candidates: list[UnknownStatementColumnCandidate]
    column_profiles: list[UnknownStatementColumnProfile] = Field(exclude=True)
    mapping_suggestions: list[UnknownStatementMappingSuggestion]
    source_type: str = "pdf_table"
    is_continuation: bool = False
    continued_from_page_number: int | None = None
    continued_from_table_index: int | None = None
    continuation_mapping_fields: list[UnknownStatementContinuationMappingField] = Field(
        default_factory=list
    )


class UnknownStatementStatus(StrEnum):
    NEEDS_MAPPING = "needs_mapping"


class UnknownStatementAnalysis(ApplicationModel):
    status: UnknownStatementStatus
    message: str
    detected_bank_name: str | None
    detected_statement_type: str | None
    text_based: bool
    page_count: int
    table_count: int
    table_previews: list[UnknownStatementTablePreview]
    generated_text_tables: list[TextCandidateTable] = Field(exclude=True)
    control_totals: StatementControlTotals | None = Field(exclude=True)

    def stored_report(self) -> StoredValidationReport:
        payload = self.model_dump(mode="json")
        totals = self.control_totals
        payload.update(
            statement_total_inflow=totals.total_inflow if totals else None,
            statement_total_outflow=totals.total_outflow if totals else None,
            opening_balance=totals.opening_balance if totals else None,
            closing_balance=totals.closing_balance if totals else None,
        )
        return StoredValidationReport.model_validate(payload)
