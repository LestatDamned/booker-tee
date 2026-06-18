"""Compatibility facade for unknown statement detection heuristics."""

# ruff: noqa: F401

from app.features.imports.application.unknown_statements.header_keywords import (
    AMOUNT_HEADER_KEYWORDS,
    BALANCE_AFTER_HEADER_KEYWORDS,
    CREDIT_HEADER_KEYWORDS,
    CURRENCY_HEADER_KEYWORDS,
    DATE_HEADER_KEYWORDS,
    DEBIT_HEADER_KEYWORDS,
    DESCRIPTION_HEADER_KEYWORDS,
    GENERIC_DATE_HEADER_KEYWORDS,
    OPERATION_DATE_HEADER_KEYWORDS,
    POSTING_DATE_HEADER_KEYWORDS,
    contains_any,
    header_matches_for_cell,
)
from app.features.imports.application.unknown_statements.row_detection import (
    clean_row,
    row_has_text,
    row_looks_like_header,
    row_looks_like_transaction,
)
from app.features.imports.application.unknown_statements.value_detectors import (
    CURRENCY_PATTERN,
    DATE_PATTERNS,
    MONEY_PATTERN,
    SIGNED_INTEGER_MONEY_PATTERN,
    cell_has_letters,
    is_currency_like_cell,
    is_date_like_cell,
    is_description_like_cell,
    is_money_like_cell,
    normalize_cell,
)
