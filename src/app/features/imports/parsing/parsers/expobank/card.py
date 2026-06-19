from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.features.imports.infrastructure.extraction.extracted_statement import ExtractedStatement
from app.features.imports.parsing.parser_types import RawTransactionDraft, StatementControlTotals
from app.features.imports.parsing.support.common import (
    build_raw_transaction_draft,
    cell,
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


@dataclass(frozen=True)
class ExpobankTableRow:
    page_number: int
    table_index: int
    source_row_index: int
    cells: tuple[str | None, ...]


@dataclass(frozen=True)
class ExpobankParserContext:
    account_id: UUID | None
    currency: str


@dataclass(frozen=True)
class ExpobankParsedRow:
    source_row_id: str | None
    operation_date_raw: str | None
    debit_raw: str | None
    credit_raw: str | None
    counterparty_raw: str | None
    account_hint_raw: str | None
    purpose_raw: str | None
    description_raw: str | None
    raw_row: ExpobankTableRow


@dataclass(frozen=True)
class ExpobankCardStatementParser:
    bank_code: str = "expobank"
    statement_type: str = "card_statement"
    parser_name: str = "expobank_card_statement_v1"
    parser_version: str = "0.1"

    def can_parse(self, extracted: ExtractedStatement) -> bool:
        for page_tables in extracted.tables_by_page:
            for table in page_tables.tables:
                if table and _is_header_row(table[0]):
                    return True
        return False

    def extract_raw_transactions(
        self,
        extracted: ExtractedStatement,
        *,
        account_id: UUID | None,
        currency: str,
    ) -> list[RawTransactionDraft]:
        context = ExpobankParserContext(account_id=account_id, currency=currency)
        return [
            build_expobank_draft(
                parse_expobank_row(row),
                row_index=row_index,
                context=context,
            )
            for row_index, row in enumerate(extract_expobank_rows(extracted))
        ]

    def extract_control_totals(
        self,
        extracted: ExtractedStatement,
        *,
        currency: str,
    ) -> StatementControlTotals | None:
        for page_tables in extracted.tables_by_page:
            for table in page_tables.tables:
                for row in table:
                    row_cells = [clean_cell(cell) for cell in row]
                    if cell(row_cells, 0) != "Total":
                        continue
                    return StatementControlTotals(
                        currency=normalize_currency(None, currency),
                        total_outflow=parse_money_amount(cell(row_cells, 2)),
                        total_inflow=parse_money_amount(cell(row_cells, 3)),
                    )
        return None


def _is_header_row(row: Sequence[str | None]) -> bool:
    cleaned = [clean_cell(cell) for cell in row]
    return {"document", "processed at", "debiting", "crediting"}.issubset(
        {cell.lower() for cell in cleaned if cell}
    )


def extract_expobank_rows(extracted: ExtractedStatement) -> list[ExpobankTableRow]:
    rows: list[ExpobankTableRow] = []
    for page_tables in extracted.tables_by_page:
        for table_index, table in enumerate(page_tables.tables):
            for source_row_index, row in enumerate(table):
                row_cells = tuple(clean_cell(value) for value in row)
                if not looks_like_expobank_transaction_row(row_cells):
                    continue
                rows.append(
                    ExpobankTableRow(
                        page_number=page_tables.page_number,
                        table_index=table_index,
                        source_row_index=source_row_index,
                        cells=row_cells,
                    )
                )
    return rows


def looks_like_expobank_transaction_row(row: Sequence[str | None]) -> bool:
    document_number = cell(row, 0)
    if document_number is None or document_number.lower() == "total":
        return False
    if document_number.lower() == "document":
        return False
    has_amount = cell(row, 2) is not None or cell(row, 3) is not None
    return document_number.startswith("№") and has_amount


def parse_expobank_row(row: ExpobankTableRow) -> ExpobankParsedRow:
    purpose_raw = cell(row.cells, 6)
    counterparty_raw = cell(row.cells, 4)
    return ExpobankParsedRow(
        source_row_id=cell(row.cells, 0),
        operation_date_raw=cell(row.cells, 1),
        debit_raw=cell(row.cells, 2),
        credit_raw=cell(row.cells, 3),
        counterparty_raw=counterparty_raw,
        account_hint_raw=cell(row.cells, 5),
        purpose_raw=purpose_raw,
        description_raw=normalize_description(purpose_raw, counterparty_raw),
        raw_row=row,
    )


def build_expobank_draft(
    parsed_row: ExpobankParsedRow,
    *,
    row_index: int,
    context: ExpobankParserContext,
) -> RawTransactionDraft:
    currency_normalized = normalize_currency(None, context.currency)

    normalization_errors: list[str] = []
    operation_date = parse_with_error(
        parse_bank_date,
        parsed_row.operation_date_raw,
        normalization_errors,
    )
    amount = signed_expobank_amount(
        parsed_row.debit_raw,
        parsed_row.credit_raw,
        normalization_errors,
    )
    description_normalized = normalize_description(parsed_row.description_raw)
    dedupe_hash = build_dedupe_hash(
        account_id=context.account_id,
        operation_date=operation_date,
        amount=amount,
        currency=currency_normalized,
        description_normalized=description_normalized,
        source_row_id=parsed_row.source_row_id,
    )
    is_normalized = bool(operation_date and amount is not None and description_normalized)

    return build_raw_transaction_draft(
        row_index=row_index,
        raw_payload={
            "bank_code": "expobank",
            "source_row_id": parsed_row.source_row_id,
            "page_number": parsed_row.raw_row.page_number,
            "table_index": parsed_row.raw_row.table_index,
            "source_row_index": parsed_row.raw_row.source_row_index,
            "cells": list(parsed_row.raw_row.cells),
        },
        operation_date_raw=parsed_row.operation_date_raw,
        posting_date_raw=None,
        description_raw=parsed_row.description_raw,
        amount_raw=parsed_row.credit_raw or parsed_row.debit_raw,
        currency_raw=None,
        balance_after_raw=None,
        account_hint_raw=parsed_row.account_hint_raw,
        account_id=context.account_id,
        operation_date=operation_date,
        posting_date=None,
        description_normalized=description_normalized,
        amount=amount,
        currency=currency_normalized,
        balance_after=None,
        dedupe_hash=dedupe_hash,
        is_normalized=is_normalized,
        normalized_confidence=Decimal("0.9500"),
        normalization_errors=normalization_errors,
    )


def signed_expobank_amount(
    debit_raw: str | None,
    credit_raw: str | None,
    normalization_errors: list[str],
) -> Decimal | None:
    try:
        debit = parse_money_amount(debit_raw)
        credit = parse_money_amount(credit_raw)
    except ValueError as exc:
        normalization_errors.append(str(exc))
        return None

    if debit is not None and credit is not None:
        normalization_errors.append("Both debit and credit are present.")
        return None
    if credit is not None:
        return credit
    if debit is not None:
        return -debit

    normalization_errors.append("No debit or credit amount found.")
    return None
