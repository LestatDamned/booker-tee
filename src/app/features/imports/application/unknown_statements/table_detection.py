from app.features.imports.application.unknown_statements.header_keywords import (
    AMOUNT_HEADER_KEYWORDS,
    CREDIT_HEADER_KEYWORDS,
    DATE_HEADER_KEYWORDS,
    DEBIT_HEADER_KEYWORDS,
    DESCRIPTION_HEADER_KEYWORDS,
    contains_any,
    header_matches_for_cell,
)
from app.features.imports.application.unknown_statements.row_detection import (
    clean_row,
    row_has_text,
    row_looks_like_transaction,
)
from app.features.imports.application.unknown_statements.value_detectors import (
    is_date_like_cell,
    is_description_like_cell,
    is_money_like_cell,
    normalize_cell,
)

MAX_PREVIEW_ROWS = 5
MAX_PREVIEW_COLUMNS = 5
MAX_HEADER_SCAN_ROWS = 25


def looks_like_transaction_table(table: list[list[str | None]]) -> bool:
    rows = [clean_row(row) for row in table if row_has_text(clean_row(row))]
    if not rows:
        return False
    if best_header_row_index(rows) > 0:
        return True

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
    for row in table_from_best_header_row(table):
        cleaned = clean_row(row)
        if not row_has_text(cleaned):
            continue
        rows.append([compact_cell(cell) for cell in cleaned[:MAX_PREVIEW_COLUMNS]])
        if len(rows) >= MAX_PREVIEW_ROWS:
            break
    return rows


def compact_cell(value: str) -> str:
    return normalize_cell(value)


def table_from_best_header_row(table: list[list[str | None]]) -> list[list[str | None]]:
    rows = [clean_row(row) for row in table]
    header_row_index = best_header_row_index(rows)
    return table[header_row_index:] if header_row_index > 0 else table


def best_header_row_index(rows: list[list[str]]) -> int:
    best_index = 0
    best_score = 0
    for row_index, row in enumerate(rows[:MAX_HEADER_SCAN_ROWS]):
        score = header_row_score(row)
        if score > best_score:
            best_index = row_index
            best_score = score
    return best_index if best_score >= 2 else 0


def header_row_score(row: list[str]) -> int:
    if not row_has_text(row) or row_looks_like_transaction(row):
        return 0

    matched_fields = {field for cell in row for field in header_matches_for_cell(cell)}
    has_date = bool(matched_fields.intersection({"operation_date", "posting_date"}))
    has_amount = bool(matched_fields.intersection({"amount", "debit_amount", "credit_amount"}))
    if not has_date or not has_amount:
        return 0

    score = len(matched_fields)
    if "description" in matched_fields:
        score += 1
    return score
