from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.features.imports.application.unknown_statements.header_keywords import (
    header_matches_for_cell,
)
from app.features.imports.infrastructure.extraction.extracted_statement import ExtractedStatement
from app.features.imports.parsing.parser_types import RawTransactionDraft, StatementControlTotals
from app.features.imports.parsing.support.common import (
    build_raw_transaction_draft,
    cell,
    extracted_text,
    parse_with_error,
)
from app.features.imports.parsing.support.normalization import (
    build_dedupe_hash,
    clean_cell,
    normalize_currency,
    normalize_description,
    parse_bank_date,
    parse_money_amount,
)

ALFABANK_MARKERS = ("альфа", "alfa")
CONTROL_TOTAL_LABELS = {
    "opening_balance": ("Входящий остаток",),
    "closing_balance": ("Текущий баланс",),
    "total_inflow": ("Поступления",),
    "total_outflow": ("Расходы",),
}


@dataclass(frozen=True)
class AlfabankXlsxHeader:
    row_index: int
    operation_date_column: int
    posting_date_column: int | None
    description_column: int
    amount_column: int
    currency_column: int | None


@dataclass(frozen=True)
class AlfabankXlsxRawRow:
    page_number: int
    table_index: int
    source_row_index: int
    cells: tuple[str | None, ...]


@dataclass(frozen=True)
class AlfabankXlsxParserContext:
    account_id: UUID | None
    currency: str
    account_hint: str | None


@dataclass(frozen=True)
class AlfabankXlsxParsedRow:
    source_row_id: str
    operation_date_raw: str | None
    posting_date_raw: str | None
    description_raw: str | None
    amount_raw: str | None
    currency_raw: str | None
    raw_row: AlfabankXlsxRawRow


@dataclass(frozen=True)
class AlfabankXlsxStatementParser:
    bank_code: str = "alfabank"
    statement_type: str = "card_statement"
    parser_name: str = "alfabank_xlsx_statement_v1"
    parser_version: str = "0.1"

    def can_parse(self, extracted: ExtractedStatement) -> bool:
        if extracted.metadata.get("source_format") != "xlsx":
            return False
        if not contains_alfabank_marker(extracted):
            return False
        return any(find_alfabank_header(table) is not None for table in extracted_tables(extracted))

    def extract_raw_transactions(
        self,
        extracted: ExtractedStatement,
        *,
        account_id: UUID | None,
        currency: str,
    ) -> list[RawTransactionDraft]:
        context = AlfabankXlsxParserContext(
            account_id=account_id,
            currency=extract_statement_currency(extracted) or currency,
            account_hint=extract_account_hint(extracted),
        )
        return [
            build_alfabank_xlsx_draft(
                parse_alfabank_xlsx_row(row, header),
                row_index=row_index,
                context=context,
            )
            for row_index, (row, header) in enumerate(extract_alfabank_xlsx_rows(extracted))
        ]

    def extract_control_totals(
        self,
        extracted: ExtractedStatement,
        *,
        currency: str,
    ) -> StatementControlTotals | None:
        totals = extract_control_total_values(extracted)
        if not totals:
            return None
        return StatementControlTotals(
            currency=normalize_currency(extract_statement_currency(extracted), currency),
            opening_balance=totals.get("opening_balance"),
            closing_balance=totals.get("closing_balance"),
            total_inflow=totals.get("total_inflow"),
            total_outflow=totals.get("total_outflow"),
        )


def contains_alfabank_marker(extracted: ExtractedStatement) -> bool:
    text = extracted_text(extracted).casefold()
    return any(marker in text for marker in ALFABANK_MARKERS)


def extracted_tables(extracted: ExtractedStatement) -> list[list[list[str | None]]]:
    return [table for page_tables in extracted.tables_by_page for table in page_tables.tables]


def find_alfabank_header(table: list[list[str | None]]) -> AlfabankXlsxHeader | None:
    for row_index, row in enumerate(table[:30]):
        fields = header_fields_by_column(row)
        operation_date_column = first_column_for_field(fields, "operation_date")
        description_column = first_column_for_field(fields, "description")
        amount_column = first_column_for_field(fields, "amount")
        if operation_date_column is None or description_column is None or amount_column is None:
            continue
        return AlfabankXlsxHeader(
            row_index=row_index,
            operation_date_column=operation_date_column,
            posting_date_column=first_column_for_field(fields, "posting_date"),
            description_column=description_column,
            amount_column=amount_column,
            currency_column=first_column_for_field(fields, "currency"),
        )
    return None


def header_fields_by_column(row: Sequence[str | None]) -> dict[str, int]:
    fields: dict[str, int] = {}
    for column_index, value in enumerate(row):
        for field in header_matches_for_cell(clean_cell(value) or ""):
            fields.setdefault(field, column_index)
    return fields


def first_column_for_field(fields: dict[str, int], field: str) -> int | None:
    return fields.get(field)


def extract_alfabank_xlsx_rows(
    extracted: ExtractedStatement,
) -> list[tuple[AlfabankXlsxRawRow, AlfabankXlsxHeader]]:
    rows: list[tuple[AlfabankXlsxRawRow, AlfabankXlsxHeader]] = []
    for page_tables in extracted.tables_by_page:
        for table_index, table in enumerate(page_tables.tables):
            header = find_alfabank_header(table)
            if header is None:
                continue
            for source_row_index, row in enumerate(
                table[header.row_index + 1 :], start=header.row_index + 1
            ):
                row_cells = tuple(clean_cell(value) for value in row)
                raw_row = AlfabankXlsxRawRow(
                    page_number=page_tables.page_number,
                    table_index=table_index,
                    source_row_index=source_row_index,
                    cells=row_cells,
                )
                if looks_like_alfabank_transaction_row(raw_row, header):
                    rows.append((raw_row, header))
    return rows


def looks_like_alfabank_transaction_row(
    row: AlfabankXlsxRawRow,
    header: AlfabankXlsxHeader,
) -> bool:
    return (
        cell(row.cells, header.operation_date_column) is not None
        and cell(row.cells, header.description_column) is not None
        and cell(row.cells, header.amount_column) is not None
    )


def parse_alfabank_xlsx_row(
    row: AlfabankXlsxRawRow,
    header: AlfabankXlsxHeader,
) -> AlfabankXlsxParsedRow:
    return AlfabankXlsxParsedRow(
        source_row_id=stable_source_row_id(row),
        operation_date_raw=cell(row.cells, header.operation_date_column),
        posting_date_raw=cell(row.cells, header.posting_date_column)
        if header.posting_date_column is not None
        else None,
        description_raw=cell(row.cells, header.description_column),
        amount_raw=cell(row.cells, header.amount_column),
        currency_raw=cell(row.cells, header.currency_column)
        if header.currency_column is not None
        else None,
        raw_row=row,
    )


def build_alfabank_xlsx_draft(
    parsed_row: AlfabankXlsxParsedRow,
    *,
    row_index: int,
    context: AlfabankXlsxParserContext,
) -> RawTransactionDraft:
    normalization_errors: list[str] = []
    operation_date = parse_with_error(
        parse_bank_date,
        parsed_row.operation_date_raw,
        normalization_errors,
    )
    posting_date = parse_with_error(
        parse_bank_date,
        parsed_row.posting_date_raw,
        normalization_errors,
    )
    amount = parse_with_error(
        parse_money_amount,
        parsed_row.amount_raw,
        normalization_errors,
    )
    row_currency = normalize_currency(parsed_row.currency_raw, context.currency)
    description = normalize_description(parsed_row.description_raw)
    dedupe_hash = build_dedupe_hash(
        account_id=context.account_id,
        operation_date=operation_date,
        amount=amount,
        currency=row_currency,
        description_normalized=description,
        source_row_id=parsed_row.source_row_id,
    )
    is_normalized = bool(operation_date and amount is not None and description)

    return build_raw_transaction_draft(
        row_index=row_index,
        raw_payload={
            "bank_code": "alfabank",
            "statement_type": "card_statement",
            "source_row_id": parsed_row.source_row_id,
            "page_number": parsed_row.raw_row.page_number,
            "table_index": parsed_row.raw_row.table_index,
            "source_row_index": parsed_row.raw_row.source_row_index,
            "cells": list(parsed_row.raw_row.cells),
        },
        operation_date_raw=parsed_row.operation_date_raw,
        posting_date_raw=parsed_row.posting_date_raw,
        description_raw=parsed_row.description_raw,
        amount_raw=parsed_row.amount_raw,
        currency_raw=parsed_row.currency_raw,
        balance_after_raw=None,
        account_hint_raw=context.account_hint,
        account_id=context.account_id,
        operation_date=operation_date,
        posting_date=posting_date,
        description_normalized=description,
        amount=amount,
        currency=row_currency,
        balance_after=None,
        dedupe_hash=dedupe_hash,
        is_normalized=is_normalized,
        normalized_confidence=Decimal("0.9300"),
        normalization_errors=normalization_errors,
    )


def stable_source_row_id(row: AlfabankXlsxRawRow) -> str:
    return f"alfabank-xlsx:{row.page_number}:{row.table_index}:{row.source_row_index}"


def extract_statement_currency(extracted: ExtractedStatement) -> str | None:
    for table in extracted_tables(extracted):
        for row in table[:15]:
            for column_index, value in enumerate(row):
                if clean_cell(value) == "Валюта счета":
                    return cell(row, column_index + 1)
    return None


def extract_account_hint(extracted: ExtractedStatement) -> str | None:
    text = extracted_text(extracted).casefold()
    if "счет" in text or "счёт" in text:
        return "счет ****"
    return None


def extract_control_total_values(
    extracted: ExtractedStatement,
) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for table in extracted_tables(extracted):
        for row in table[:15]:
            for column_index, value in enumerate(row):
                field = control_total_field_for_label(clean_cell(value))
                if field is None:
                    continue
                amount = first_money_after_column(row, column_index)
                if amount is not None:
                    totals[field] = amount
    return totals


def control_total_field_for_label(label: str | None) -> str | None:
    if label is None:
        return None
    for field, labels in CONTROL_TOTAL_LABELS.items():
        if label in labels:
            return field
    return None


def first_money_after_column(row: Sequence[str | None], column_index: int) -> Decimal | None:
    for value in row[column_index + 1 :]:
        try:
            amount = parse_money_amount(value)
        except ValueError:
            continue
        if amount is not None:
            return amount
    return None
