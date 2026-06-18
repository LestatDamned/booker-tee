from dataclasses import dataclass


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
    reasons: list["UnknownStatementMappingSuggestionReason"]
    warnings: list["UnknownStatementMappingSuggestionWarning"]

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
