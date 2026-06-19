from datetime import date
from decimal import Decimal

from app.features.imports.application.unknown_statement_mappings.dto import (
    UnknownStatementMappedRow,
    UnknownStatementMappingCommand,
)
from app.features.imports.parsing.support.normalization import (
    normalize_currency,
    normalize_description,
    parse_bank_date,
    parse_money_amount,
)


def map_table_rows(
    table: list[list[str]],
    *,
    page_number: int,
    table_index: int,
    start_row: int,
    command: UnknownStatementMappingCommand,
    max_rows: int | None,
) -> list[UnknownStatementMappedRow]:
    rows: list[UnknownStatementMappedRow] = []
    for source_row_number, row in enumerate(table[start_row:], start=start_row):
        if not row_has_text(row):
            continue
        mapped_row = map_row(
            row,
            page_number=page_number,
            table_index=table_index,
            source_row_number=source_row_number,
            command=command,
        )
        if is_mapping_header_or_noise(mapped_row):
            continue
        rows.append(mapped_row)
        if max_rows is not None and len(rows) >= max_rows:
            break
    return rows


def row_has_text(row: list[str]) -> bool:
    return any(cell.strip() for cell in row)


def is_mapping_header_or_noise(row: UnknownStatementMappedRow) -> bool:
    if row.operation_date is not None or row.amount is not None:
        return False
    text = " ".join(
        [
            row.operation_date_raw,
            row.posting_date_raw,
            row.description_raw,
            row.amount_raw,
            row.currency_raw,
        ]
    ).casefold()
    header_markers = (
        "дата",
        "документ",
        "назначение",
        "сумма",
        "валюта",
        "российские рубли",
        "operation",
        "date",
        "description",
        "amount",
        "debit",
        "credit",
        "currency",
    )
    return any(marker in text for marker in header_markers)


def map_row(
    row: list[str],
    *,
    page_number: int,
    table_index: int,
    source_row_number: int,
    command: UnknownStatementMappingCommand,
) -> UnknownStatementMappedRow:
    operation_date_raw = cell_at(row, command.operation_date_column)
    posting_date_raw = cell_at(row, command.posting_date_column)
    description_raw = cell_at(row, command.description_column)
    amount_raw = cell_at(row, command.amount_column)
    debit_raw = cell_at(row, command.debit_amount_column)
    credit_raw = cell_at(row, command.credit_amount_column)
    currency_raw = cell_at(row, command.currency_column)
    balance_after_raw = cell_at(row, command.balance_after_column)

    operation_date, date_error = parse_mapped_date(operation_date_raw)
    posting_date, posting_date_error = parse_optional_mapped_date(posting_date_raw)
    amount, amount_error = parse_mapped_amount_for_command(
        amount_raw=amount_raw,
        debit_raw=debit_raw,
        credit_raw=credit_raw,
        command=command,
    )
    balance_after, balance_after_error = parse_optional_mapped_amount(balance_after_raw)
    currency = normalize_currency(currency_raw, command.default_currency)
    description = normalize_description(description_raw)
    errors = [
        error
        for error in (
            date_error,
            f"дата проводки: {posting_date_error}" if posting_date_error else "",
            amount_error,
            f"остаток: {balance_after_error}" if balance_after_error else "",
            "нет описания" if description is None else "",
        )
        if error
    ]

    return UnknownStatementMappedRow(
        page_number=page_number,
        table_index=table_index,
        source_row_number=source_row_number,
        operation_date_raw=operation_date_raw,
        operation_date=operation_date,
        posting_date_raw=posting_date_raw,
        posting_date=posting_date,
        description_raw=description_raw,
        description=description,
        amount_raw=display_amount_raw(
            amount_raw=amount_raw,
            debit_raw=debit_raw,
            credit_raw=credit_raw,
            command=command,
        ),
        amount=amount,
        currency_raw=currency_raw,
        currency=currency,
        balance_after_raw=balance_after_raw,
        balance_after=balance_after,
        status="error" if errors else "valid",
        error="; ".join(errors),
    )


def parse_mapped_date(raw: str) -> tuple[date | None, str]:
    if not raw.strip():
        return None, "нет даты"
    date_part = raw.strip().split()[0]
    try:
        return parse_bank_date(date_part), ""
    except ValueError:
        return None, "дата не распознана"


def parse_optional_mapped_date(raw: str) -> tuple[date | None, str]:
    if not raw.strip():
        return None, ""
    return parse_mapped_date(raw)


def parse_mapped_amount(raw: str) -> tuple[Decimal | None, str]:
    if not raw.strip():
        return None, "нет суммы"
    try:
        amount = parse_money_amount(raw)
    except ValueError:
        return None, "сумма не распознана"
    if amount is None:
        return None, "нет суммы"
    return amount, ""


def parse_mapped_amount_for_command(
    *,
    amount_raw: str,
    debit_raw: str,
    credit_raw: str,
    command: UnknownStatementMappingCommand,
) -> tuple[Decimal | None, str]:
    if command.amount_column is not None:
        return parse_mapped_amount(amount_raw)
    if command.debit_amount_column is None and command.credit_amount_column is None:
        return None, "нет колонки суммы"

    debit, debit_error = parse_optional_mapped_amount(debit_raw)
    credit, credit_error = parse_optional_mapped_amount(credit_raw)
    errors = [
        error
        for error in (
            f"списание: {debit_error}" if debit_error else "",
            f"зачисление: {credit_error}" if credit_error else "",
        )
        if error
    ]
    if errors:
        return None, "; ".join(errors)
    if debit is not None and credit is not None:
        return None, "заполнены и списание, и зачисление"
    if credit is not None:
        return credit, ""
    if debit is not None:
        return -abs(debit), ""
    return None, "нет суммы"


def parse_optional_mapped_amount(raw: str) -> tuple[Decimal | None, str]:
    if not raw.strip():
        return None, ""
    return parse_mapped_amount(raw)


def display_amount_raw(
    *,
    amount_raw: str,
    debit_raw: str,
    credit_raw: str,
    command: UnknownStatementMappingCommand,
) -> str:
    if command.amount_column is not None:
        return amount_raw
    parts = []
    if debit_raw.strip():
        parts.append(f"debit: {debit_raw}")
    if credit_raw.strip():
        parts.append(f"credit: {credit_raw}")
    return " / ".join(parts)


def cell_at(row: list[str], index: int | None) -> str:
    if index is None or index < 0 or index >= len(row):
        return ""
    return row[index]
