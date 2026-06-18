from app.features.imports.application.unknown_statements.header_keywords import (
    header_matches_for_cell,
)
from app.features.imports.application.unknown_statements.value_detectors import (
    cell_has_letters,
    is_date_like_cell,
    is_money_like_cell,
)


def row_looks_like_header(row: list[str]) -> bool:
    if row_looks_like_transaction(row):
        return False
    return any(header_matches_for_cell(cell) for cell in row)


def row_looks_like_transaction(row: list[str]) -> bool:
    return (
        any(is_date_like_cell(cell) for cell in row)
        and any(is_money_like_cell(cell) for cell in row)
        and any(cell_has_letters(cell) for cell in row)
    )


def clean_row(row: list[str | None]) -> list[str]:
    return [cell.strip() if cell else "" for cell in row]


def row_has_text(row: list[str]) -> bool:
    return any(cell for cell in row)
