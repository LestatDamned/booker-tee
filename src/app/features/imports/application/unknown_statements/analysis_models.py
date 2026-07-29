from dataclasses import asdict, dataclass
from enum import StrEnum

from app.features.imports.statements.dto import StatementControlTotals


@dataclass(frozen=True)
class UnknownStatementColumnCandidate:
    field: str
    column_index: int
    header: str


@dataclass(frozen=True)
class UnknownStatementColumnProfile:
    column_index: int
    header: str
    sample_count: int
    non_empty_count: int
    date_like_count: int
    money_like_count: int
    currency_like_count: int
    description_like_count: int
    header_matches: list[str]


@dataclass(frozen=True)
class UnknownStatementMappingSuggestionWarning:
    code: str
    fields: list[str]


@dataclass(frozen=True)
class UnknownStatementMappingSuggestionReason:
    field: str
    column_index: int
    header: str
    evidence: str
    matched_count: int | None = None
    sample_count: int | None = None


@dataclass(frozen=True)
class UnknownStatementMappingSuggestion:
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


@dataclass(frozen=True)
class UnknownStatementContinuationMappingField:
    field: str
    column_index: int


@dataclass(frozen=True)
class TextCandidateTable:
    page_number: int
    table_index: int
    rows: list[list[str]]


@dataclass(frozen=True)
class UnknownStatementTablePreview:
    page_number: int
    table_index: int
    row_count: int
    column_count: int
    preview_row_count: int
    rows: list[list[str]]
    column_candidates: list[UnknownStatementColumnCandidate]
    column_profiles: list[UnknownStatementColumnProfile]
    mapping_suggestions: list[UnknownStatementMappingSuggestion]
    source_type: str = "pdf_table"
    is_continuation: bool = False
    continued_from_page_number: int | None = None
    continued_from_table_index: int | None = None
    continuation_mapping_fields: list[UnknownStatementContinuationMappingField] | None = None

    def as_validation_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload.pop("column_profiles")
        payload["continuation_mapping_fields"] = payload["continuation_mapping_fields"] or []
        return payload


class UnknownStatementStatus(StrEnum):
    NEEDS_MAPPING = "needs_mapping"


@dataclass(frozen=True)
class UnknownStatementAnalysis:
    status: UnknownStatementStatus
    message: str
    detected_bank_name: str | None
    detected_statement_type: str | None
    text_based: bool
    page_count: int
    table_count: int
    table_previews: list[UnknownStatementTablePreview]
    generated_text_tables: list[TextCandidateTable]
    control_totals: StatementControlTotals | None

    def as_validation_report(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "message": self.message,
            "detected_bank_name": self.detected_bank_name,
            "detected_statement_type": self.detected_statement_type,
            "text_based": self.text_based,
            "page_count": self.page_count,
            "table_count": self.table_count,
            "table_previews": [preview.as_validation_payload() for preview in self.table_previews],
            "statement_total_inflow": str(self.control_totals.total_inflow)
            if self.control_totals and self.control_totals.total_inflow is not None
            else None,
            "statement_total_outflow": str(self.control_totals.total_outflow)
            if self.control_totals and self.control_totals.total_outflow is not None
            else None,
            "opening_balance": str(self.control_totals.opening_balance)
            if self.control_totals and self.control_totals.opening_balance is not None
            else None,
            "closing_balance": str(self.control_totals.closing_balance)
            if self.control_totals and self.control_totals.closing_balance is not None
            else None,
        }
