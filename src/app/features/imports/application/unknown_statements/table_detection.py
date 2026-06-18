from app.features.imports.application.unknown_statements.header_keywords import (
    AMOUNT_HEADER_KEYWORDS,
    CREDIT_HEADER_KEYWORDS,
    DATE_HEADER_KEYWORDS,
    DEBIT_HEADER_KEYWORDS,
    DESCRIPTION_HEADER_KEYWORDS,
    contains_any,
)
from app.features.imports.application.unknown_statements.row_detection import (
    clean_row,
    row_has_text,
)
from app.features.imports.application.unknown_statements.value_detectors import (
    is_date_like_cell,
    is_description_like_cell,
    is_money_like_cell,
    normalize_cell,
)

MAX_PREVIEW_ROWS = 5
MAX_PREVIEW_COLUMNS = 5


def looks_like_transaction_table(table: list[list[str | None]]) -> bool:
    rows = [clean_row(row) for row in table if row_has_text(clean_row(row))]
    if not rows:
        return False

    header_text = " ".join(rows[0]).casefold()
    header_has_date = contains_any(header_text, DATE_HEADER_KEYWORDS)
    header_has_amount = contains_any(header_text, AMOUNT_HEADER_KEYWORDS) or contains_any(
        header_text, DEBIT_HEADER_KEYWORDS + CREDIT_HEADER_KEYWORDS
    )
    header_has_description = contains_any(header_text, DESCRIPTION_HEADER_KEYWORDS)

    if header_has_date and header_has_amount:
        return True

    header_score = sum([header_has_date, header_has_amount, header_has_description])
    date_like_rows = 0
    rich_transaction_rows = 0
    amount_like_rows = 0
    for row in rows[:15]:
        has_date = any(is_date_like_cell(cell) for cell in row)
        has_amount = any(is_money_like_cell(cell) for cell in row)
        has_text = any(is_description_like_cell(cell) for cell in row)
        if has_date:
            date_like_rows += 1
        if has_amount:
            amount_like_rows += 1
        if has_date and has_amount and has_text:
            rich_transaction_rows += 1

    if rich_transaction_rows >= 2:
        return True
    return header_score >= 1 and date_like_rows >= 2 and amount_like_rows >= 2


def compact_preview_rows(table: list[list[str | None]]) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in table:
        cleaned = clean_row(row)
        if not row_has_text(cleaned):
            continue
        rows.append([compact_cell(cell) for cell in cleaned[:MAX_PREVIEW_COLUMNS]])
        if len(rows) >= MAX_PREVIEW_ROWS:
            break
    return rows


def compact_cell(value: str) -> str:
    return normalize_cell(value)
