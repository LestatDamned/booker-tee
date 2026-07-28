from dataclasses import dataclass
from enum import StrEnum

from app.features.imports.domain.control_totals import StatementControlTotals


@dataclass(frozen=True)
class UnknownStatementColumnCandidate:
    field: str
    column_index: int
    header: str
    confidence: float

    def as_json(self) -> dict[str, object]:
        return {
            "field": self.field,
            "column_index": self.column_index,
            "header": self.header,
            "confidence": self.confidence,
        }


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

    def as_json(self) -> dict[str, object]:
        return {
            "column_index": self.column_index,
            "header": self.header,
            "sample_count": self.sample_count,
            "non_empty_count": self.non_empty_count,
            "date_like_count": self.date_like_count,
            "money_like_count": self.money_like_count,
            "currency_like_count": self.currency_like_count,
            "description_like_count": self.description_like_count,
            "header_matches": self.header_matches,
        }


@dataclass(frozen=True)
class UnknownStatementMappingSuggestionWarning:
    code: str
    fields: list[str]

    def as_json(self) -> dict[str, object]:
        return {
            "code": self.code,
            "fields": self.fields,
        }


@dataclass(frozen=True)
class UnknownStatementMappingSuggestionReason:
    field: str
    column_index: int
    header: str
    evidence: str
    matched_count: int | None = None
    sample_count: int | None = None

    def as_json(self) -> dict[str, object]:
        return {
            "field": self.field,
            "column_index": self.column_index,
            "header": self.header,
            "evidence": self.evidence,
            "matched_count": self.matched_count,
            "sample_count": self.sample_count,
        }


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
    confidence: float
    reasons: list[UnknownStatementMappingSuggestionReason]
    warnings: list[UnknownStatementMappingSuggestionWarning]

    def as_json(self) -> dict[str, object]:
        return {
            "operation_date_column": self.operation_date_column,
            "posting_date_column": self.posting_date_column,
            "description_column": self.description_column,
            "amount_column": self.amount_column,
            "debit_amount_column": self.debit_amount_column,
            "credit_amount_column": self.credit_amount_column,
            "currency_column": self.currency_column,
            "balance_after_column": self.balance_after_column,
            "first_data_row": self.first_data_row,
            "confidence": self.confidence,
            "reasons": [reason.as_json() for reason in self.reasons],
            "warnings": [warning.as_json() for warning in self.warnings],
        }


@dataclass(frozen=True)
class UnknownStatementContinuationMappingField:
    field: str
    column_index: int

    def as_json(self) -> dict[str, object]:
        return {
            "field": self.field,
            "column_index": self.column_index,
        }


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

    def as_json(self) -> dict[str, object]:
        return {
            "page_number": self.page_number,
            "table_index": self.table_index,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "preview_row_count": self.preview_row_count,
            "rows": self.rows,
            "column_candidates": [candidate.as_json() for candidate in self.column_candidates],
            "column_profiles": [profile.as_json() for profile in self.column_profiles],
            "mapping_suggestions": [
                suggestion.as_json() for suggestion in self.mapping_suggestions
            ],
            "source_type": self.source_type,
            "is_continuation": self.is_continuation,
            "continued_from_page_number": self.continued_from_page_number,
            "continued_from_table_index": self.continued_from_table_index,
            "continuation_mapping_fields": [
                mapping_field.as_json() for mapping_field in self.continuation_mapping_fields or []
            ],
        }


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
            "table_previews": [preview.as_json() for preview in self.table_previews],
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
