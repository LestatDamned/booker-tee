"""Stored schema for statement validation and unknown-statement analysis."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from app.features.imports.statements.validation import StatementValidationStatus


class _StoredReportModel(BaseModel):
    """Immutable, forward-compatible value read from a JSONB report."""

    model_config = ConfigDict(
        coerce_numbers_to_str=True,
        extra="ignore",
        frozen=True,
    )


class StoredBalanceChainMismatch(_StoredReportModel):
    row_index: int
    previous_row_index: int
    previous_balance_after: str
    previous_amount: str
    amount: str
    expected_balance_after: str
    actual_balance_after: str


class StoredBalanceChain(_StoredReportModel):
    status: str = ""
    direction: str | None = None
    checked_pair_count: int = 0
    mismatch_count: int = 0
    mismatches: tuple[StoredBalanceChainMismatch, ...] = ()


class StoredColumnCandidate(_StoredReportModel):
    field: str
    column_index: int
    header: str = ""


class StoredSuggestionReason(_StoredReportModel):
    field: str
    column_index: int
    header: str = ""
    evidence: str = ""
    matched_count: int | None = None
    sample_count: int | None = None


class StoredSuggestionWarning(_StoredReportModel):
    code: str
    fields: tuple[str, ...] = ()


class StoredMappingSuggestion(_StoredReportModel):
    operation_date_column: int = 0
    description_column: int = 0
    first_data_row: int = 1
    posting_date_column: int | None = None
    amount_column: int | None = None
    debit_amount_column: int | None = None
    credit_amount_column: int | None = None
    currency_column: int | None = None
    balance_after_column: int | None = None
    reasons: tuple[StoredSuggestionReason, ...] = ()
    warnings: tuple[StoredSuggestionWarning, ...] = ()


class StoredContinuationField(_StoredReportModel):
    field: str
    column_index: int


class StoredTablePreview(_StoredReportModel):
    page_number: int = 1
    table_index: int = 0
    row_count: int = 0
    column_count: int = 0
    preview_row_count: int = 0
    rows: tuple[tuple[str, ...], ...] = ()
    column_candidates: tuple[StoredColumnCandidate, ...] = ()
    mapping_suggestions: tuple[StoredMappingSuggestion, ...] = ()
    source_type: str = "pdf_table"
    is_continuation: bool = False
    continued_from_page_number: int | None = None
    continued_from_table_index: int | None = None
    continuation_mapping_fields: tuple[StoredContinuationField, ...] = ()


class StoredValidationReport(_StoredReportModel):
    """Union-shaped stored report decoded into one stable read projection."""

    status: str = ""
    message: str = ""
    parser_message: str = ""
    source: str | None = None
    template_auto_apply_error: str | None = None

    detected_bank_name: str | None = None
    detected_statement_type: str | None = None
    text_based: bool | None = None
    page_count: int | None = None
    table_count: int | None = None
    table_previews: tuple[StoredTablePreview, ...] = ()

    extracted_count: int | None = None
    normalized_count: int | None = None
    needs_review_count: int | None = None
    calculated_total_inflow: str | None = None
    calculated_total_outflow: str | None = None
    ignored_total_inflow: str | None = None
    ignored_total_outflow: str | None = None
    statement_total_inflow: str | None = None
    statement_total_outflow: str | None = None
    opening_balance: str | None = None
    closing_balance: str | None = None
    balance_chain: StoredBalanceChain | None = None
    inflow_difference: Decimal | None = None
    outflow_difference: Decimal | None = None
    unexplained_inflow_difference: Decimal | None = None
    unexplained_outflow_difference: Decimal | None = None
    currency: str | None = None

    @field_validator(
        "inflow_difference",
        "outflow_difference",
        "unexplained_inflow_difference",
        "unexplained_outflow_difference",
        mode="before",
    )
    @classmethod
    def empty_decimal_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @property
    def statement_status(self) -> StatementValidationStatus | None:
        return _validation_status(self.status)

    @property
    def balance_chain_status(self) -> StatementValidationStatus | None:
        if self.balance_chain is None:
            return None
        return _validation_status(self.balance_chain.status)

    @property
    def needs_mapping(self) -> bool:
        return self.status == "needs_mapping"


def _validation_status(value: str) -> StatementValidationStatus | None:
    try:
        return StatementValidationStatus(value)
    except ValueError:
        return None
