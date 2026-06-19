import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

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
    normalize_description,
    parse_money_amount,
)

OZON_BANK_MARKERS = ("озон банк", "ozon bank", "ozon банк")
OZON_TABLE_HEADERS = ("Дата операции", "Назначение платежа", "Сумма операции")
CONTROL_TOTAL_PATTERNS = {
    "opening_balance": re.compile(r"Входящий остаток:\s*(?P<amount>[^\n]+)"),
    "closing_balance": re.compile(r"Исходящий остаток:\s*(?P<amount>[^\n]+)"),
    "total_inflow": re.compile(r"Итого зачислений за период:\s*(?P<amount>[^\n]+)"),
    "total_outflow": re.compile(r"Итого списаний за период:\s*(?P<amount>[^\n]+)"),
}


@dataclass(frozen=True)
class OzonBankCardRawRow:
    page_number: int
    table_index: int
    source_row_index: int
    cells: tuple[str | None, ...]


@dataclass(frozen=True)
class OzonBankCardParserContext:
    account_id: UUID | None
    currency: str
    account_hint: str | None


@dataclass(frozen=True)
class OzonBankCardParsedRow:
    source_row_id: str
    operation_date_raw: str | None
    document_raw: str | None
    description_raw: str | None
    amount_raw: str | None
    currency_raw: str | None
    raw_row: OzonBankCardRawRow


@dataclass(frozen=True)
class OzonBankCardStatementParser:
    bank_code: str = "ozon_bank"
    statement_type: str = "card_statement"
    parser_name: str = "ozon_bank_card_statement_v1"
    parser_version: str = "0.1"

    def can_parse(self, extracted: ExtractedStatement) -> bool:
        if extracted.metadata.get("source_format") != "pdf":
            return False
        text = extracted_text(extracted).casefold()
        if not any(marker in text for marker in OZON_BANK_MARKERS):
            return False
        return any(table_has_ozon_header(table) for table in extracted_tables(extracted))

    def extract_raw_transactions(
        self,
        extracted: ExtractedStatement,
        *,
        account_id: UUID | None,
        currency: str,
    ) -> list[RawTransactionDraft]:
        context = OzonBankCardParserContext(
            account_id=account_id,
            currency=currency,
            account_hint=extract_card_hint(extracted),
        )
        return [
            build_ozon_bank_card_draft(
                parse_ozon_bank_card_row(row),
                row_index=row_index,
                context=context,
            )
            for row_index, row in enumerate(extract_ozon_bank_card_rows(extracted))
        ]

    def extract_control_totals(
        self,
        extracted: ExtractedStatement,
        *,
        currency: str,
    ) -> StatementControlTotals | None:
        totals = extract_control_total_values(extracted_text(extracted))
        if not totals:
            return None
        return StatementControlTotals(
            currency=currency.upper(),
            opening_balance=totals.get("opening_balance"),
            closing_balance=totals.get("closing_balance"),
            total_inflow=totals.get("total_inflow"),
            total_outflow=totals.get("total_outflow"),
        )


def extracted_tables(extracted: ExtractedStatement) -> list[list[list[str | None]]]:
    return [table for page_tables in extracted.tables_by_page for table in page_tables.tables]


def table_has_ozon_header(table: list[list[str | None]]) -> bool:
    if not table:
        return False
    text = " ".join(clean_cell(cell) or "" for row in table[:2] for cell in row)
    return all(header in text for header in OZON_TABLE_HEADERS)


def extract_ozon_bank_card_rows(extracted: ExtractedStatement) -> list[OzonBankCardRawRow]:
    rows: list[OzonBankCardRawRow] = []
    for page_tables in extracted.tables_by_page:
        for table_index, table in enumerate(page_tables.tables):
            for source_row_index, row in enumerate(table):
                row_cells = tuple(clean_cell(value) for value in row)
                raw_row = OzonBankCardRawRow(
                    page_number=page_tables.page_number,
                    table_index=table_index,
                    source_row_index=source_row_index,
                    cells=row_cells,
                )
                if looks_like_ozon_transaction_row(raw_row):
                    rows.append(raw_row)
    return rows


def looks_like_ozon_transaction_row(row: OzonBankCardRawRow) -> bool:
    try:
        operation_date = parse_ozon_operation_date(cell(row.cells, 0))
    except ValueError:
        operation_date = None
    return (
        operation_date is not None
        and cell(row.cells, 2) is not None
        and cell(row.cells, 3) is not None
    )


def parse_ozon_bank_card_row(row: OzonBankCardRawRow) -> OzonBankCardParsedRow:
    amount_raw = cell(row.cells, 3)
    return OzonBankCardParsedRow(
        source_row_id=stable_source_row_id(row),
        operation_date_raw=cell(row.cells, 0),
        document_raw=cell(row.cells, 1),
        description_raw=cell(row.cells, 2),
        amount_raw=amount_raw,
        currency_raw=currency_from_amount(amount_raw),
        raw_row=row,
    )


def build_ozon_bank_card_draft(
    parsed_row: OzonBankCardParsedRow,
    *,
    row_index: int,
    context: OzonBankCardParserContext,
) -> RawTransactionDraft:
    normalization_errors: list[str] = []
    operation_date = parse_with_error(
        parse_ozon_operation_date,
        parsed_row.operation_date_raw,
        normalization_errors,
    )
    amount = parse_with_error(
        parse_money_amount,
        parsed_row.amount_raw,
        normalization_errors,
    )
    row_currency = parsed_row.currency_raw or context.currency.upper()
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
            "bank_code": "ozon_bank",
            "statement_type": "card_statement",
            "source_row_id": parsed_row.source_row_id,
            "page_number": parsed_row.raw_row.page_number,
            "table_index": parsed_row.raw_row.table_index,
            "source_row_index": parsed_row.raw_row.source_row_index,
            "document_raw": parsed_row.document_raw,
            "cells": list(parsed_row.raw_row.cells),
        },
        operation_date_raw=parsed_row.operation_date_raw,
        posting_date_raw=None,
        description_raw=parsed_row.description_raw,
        amount_raw=parsed_row.amount_raw,
        currency_raw=parsed_row.currency_raw,
        balance_after_raw=None,
        account_hint_raw=context.account_hint,
        account_id=context.account_id,
        operation_date=operation_date,
        posting_date=None,
        description_normalized=description,
        amount=amount,
        currency=row_currency,
        balance_after=None,
        dedupe_hash=dedupe_hash,
        is_normalized=is_normalized,
        normalized_confidence=Decimal("0.9300"),
        normalization_errors=normalization_errors,
    )


def parse_ozon_operation_date(raw: str | None) -> date | None:
    cleaned = clean_cell(raw)
    if cleaned is None:
        return None
    for date_format in ("%d.%m.%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, date_format).date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported Ozon operation date format: {cleaned}")


def currency_from_amount(raw: str | None) -> str | None:
    cleaned = clean_cell(raw)
    if cleaned is None:
        return None
    lowered = cleaned.casefold()
    if "₽" in cleaned or "руб" in lowered or "rub" in lowered:
        return "RUB"
    if "$" in cleaned or "usd" in lowered:
        return "USD"
    if "€" in cleaned or "eur" in lowered:
        return "EUR"
    return None


def stable_source_row_id(row: OzonBankCardRawRow) -> str:
    document = cell(row.cells, 1)
    document_key = document.replace("\n", "") if document is not None else None
    if document_key:
        return f"ozon-bank-card:{document_key}"
    return f"ozon-bank-card:{row.page_number}:{row.table_index}:{row.source_row_index}"


def extract_card_hint(extracted: ExtractedStatement) -> str | None:
    text = extracted_text(extracted).casefold()
    if "карте" in text or "карта" in text:
        return "карта ****"
    return None


def extract_control_total_values(text: str) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for field, pattern in CONTROL_TOTAL_PATTERNS.items():
        match = pattern.search(text)
        if match is None:
            continue
        try:
            amount = parse_money_amount(match.group("amount"))
        except ValueError:
            continue
        if amount is not None:
            totals[field] = amount
    return totals
