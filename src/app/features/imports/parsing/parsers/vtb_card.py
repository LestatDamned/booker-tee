import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from uuid import UUID

from app.features.imports.infrastructure.extraction.pdfplumber_extractor import ExtractedPdf
from app.features.imports.parsing.parser_types import RawTransactionDraft, StatementControlTotals
from app.features.imports.parsing.parsers.common import (
    build_raw_transaction_draft,
    cell,
    extracted_text,
    parse_with_error,
)
from app.features.imports.parsing.parsers.normalization import (
    build_dedupe_hash,
    clean_cell,
    normalize_currency,
    normalize_description,
    parse_bank_date,
)
from app.features.imports.parsing.parsers.vtb_shared import extract_statement_period

VTB_CARD_MARKERS = (
    "Номер карты",
    "Информация о балансе карты",
    "Операции по карте",
)
CARD_NUMBER_RE = re.compile(r"Номер карты\s+(?P<card>\S+)")
CARD_OPENING_TOTALS_RE = re.compile(
    r"Баланс на начало периода\s+(?P<opening>[+-]?\d[\d,.]*[.,]\d+)\s+"
    r"(?P<currency>[A-Z]{3})\s+В обработке\s+"
    r"(?P<pending>[+-]?\d[\d,.]*[.,]\d+)\s+[A-Z]{3}"
)
CARD_CLOSING_TOTALS_RE = re.compile(
    r"Баланс на конец периода\s+(?P<closing>[+-]?\d[\d,.]*[.,]\d+)\s+"
    r"(?P<currency>[A-Z]{3})\s+Расходные операции\s+"
    r"(?P<outflow>[+-]?\d[\d,.]*[.,]\d+)\s+[A-Z]{3}"
)
CARD_INFLOW_TOTALS_RE = re.compile(
    r"Поступления\s+(?P<inflow>[+-]?\d[\d,.]*[.,]\d+)\s+(?P<currency>[A-Z]{3})"
)
CARD_OPERATION_DATETIME_RE = re.compile(
    r"^(?P<operation_date>\d{2}\.\d{2}\.\d{4})\s+(?P<operation_time>\d{2}:\d{2}:\d{2})$"
)


@dataclass(frozen=True)
class VtbCardTableRow:
    page_number: int
    table_index: int
    source_row_index: int
    cells: tuple[str | None, ...]


@dataclass(frozen=True)
class VtbCardParserContext:
    account_id: UUID | None
    account_hint: str | None
    currency: str
    statement_period: tuple[str, str] | None


@dataclass(frozen=True)
class VtbCardParsedRow:
    operation_date_raw: str | None
    operation_time_raw: str | None
    posting_date_raw: str | None
    operation_amount_raw: str | None
    card_amount_raw: str | None
    fee_raw: str | None
    description_raw: str | None
    raw_row: VtbCardTableRow


@dataclass(frozen=True)
class VtbCardStatementParser:
    bank_code: str = "vtb"
    statement_type: str = "card_statement"
    parser_name: str = "vtb_card_statement_v1"
    parser_version: str = "0.1"

    def can_parse(self, extracted: ExtractedPdf) -> bool:
        text = extracted_text(extracted)
        return all(marker in text for marker in VTB_CARD_MARKERS)

    def extract_raw_transactions(
        self,
        extracted: ExtractedPdf,
        *,
        account_id: UUID | None,
        currency: str,
    ) -> list[RawTransactionDraft]:
        text = extracted_text(extracted)
        account_hint = extract_card_hint(text)
        statement_currency = extract_card_statement_currency(text) or currency
        context = VtbCardParserContext(
            account_id=account_id,
            account_hint=account_hint,
            currency=statement_currency,
            statement_period=extract_statement_period(text),
        )
        return [
            build_vtb_card_draft(
                parse_vtb_card_row(row),
                row_index=row_index,
                context=context,
            )
            for row_index, row in enumerate(extract_vtb_card_rows(extracted))
        ]

    def extract_control_totals(
        self,
        extracted: ExtractedPdf,
        *,
        currency: str,
    ) -> StatementControlTotals | None:
        text = extracted_text(extracted)
        opening_match = CARD_OPENING_TOTALS_RE.search(text)
        closing_match = CARD_CLOSING_TOTALS_RE.search(text)
        inflow_match = CARD_INFLOW_TOTALS_RE.search(text)
        if opening_match is None and closing_match is None and inflow_match is None:
            return None

        detected_currency = (
            (opening_match.group("currency") if opening_match else None)
            or (closing_match.group("currency") if closing_match else None)
            or (inflow_match.group("currency") if inflow_match else None)
            or currency
        )
        return StatementControlTotals(
            currency=normalize_currency(detected_currency, currency),
            opening_balance=parse_vtb_card_money(opening_match.group("opening"))
            if opening_match
            else None,
            closing_balance=parse_vtb_card_money(closing_match.group("closing"))
            if closing_match
            else None,
            total_inflow=parse_vtb_card_money(inflow_match.group("inflow"))
            if inflow_match
            else None,
            total_outflow=parse_vtb_card_money(closing_match.group("outflow"))
            if closing_match
            else None,
        )


def extract_vtb_card_rows(extracted: ExtractedPdf) -> list[VtbCardTableRow]:
    rows: list[VtbCardTableRow] = []
    for page_tables in extracted.tables_by_page:
        for table_index, table in enumerate(page_tables.tables):
            for source_row_index, row in enumerate(table):
                row_cells = tuple(clean_cell(value) for value in row)
                if not is_vtb_card_transaction_row(row_cells):
                    continue
                rows.append(
                    VtbCardTableRow(
                        page_number=page_tables.page_number,
                        table_index=table_index,
                        source_row_index=source_row_index,
                        cells=row_cells,
                    )
                )
    return rows


def is_vtb_card_transaction_row(row: tuple[str | None, ...]) -> bool:
    return len(row) >= 6 and parse_vtb_card_operation_datetime(cell(row, 0))[0] is not None


def parse_vtb_card_row(row: VtbCardTableRow) -> VtbCardParsedRow:
    operation_date_raw, operation_time_raw = parse_vtb_card_operation_datetime(cell(row.cells, 0))
    return VtbCardParsedRow(
        operation_date_raw=operation_date_raw,
        operation_time_raw=operation_time_raw,
        posting_date_raw=cell(row.cells, 1),
        operation_amount_raw=cell(row.cells, 2),
        card_amount_raw=cell(row.cells, 3),
        fee_raw=cell(row.cells, 4),
        description_raw=cell(row.cells, 5),
        raw_row=row,
    )


def build_vtb_card_draft(
    parsed_row: VtbCardParsedRow,
    *,
    row_index: int,
    context: VtbCardParserContext,
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
    operation_amount, operation_currency = parse_vtb_card_amount_and_currency(
        parsed_row.operation_amount_raw,
        context.currency,
        normalization_errors,
    )
    card_amount = parse_with_error(
        parse_vtb_card_money,
        parsed_row.card_amount_raw,
        normalization_errors,
    )
    row_currency = normalize_currency(operation_currency, context.currency)
    amount = card_amount if card_amount is not None else operation_amount
    description = normalize_description(parsed_row.description_raw)
    source_row_id = stable_card_source_row_id(
        row_index=parsed_row.raw_row.source_row_index,
        operation_date_raw=parsed_row.operation_date_raw,
        operation_time_raw=parsed_row.operation_time_raw,
        statement_period=context.statement_period,
    )
    dedupe_hash = build_dedupe_hash(
        account_id=context.account_id,
        operation_date=operation_date,
        amount=amount,
        currency=row_currency,
        description_normalized=description,
        source_row_id=source_row_id,
    )
    is_normalized = bool(operation_date and posting_date and amount is not None and description)

    return build_raw_transaction_draft(
        row_index=row_index,
        raw_payload={
            "bank_code": "vtb",
            "statement_type": "card_statement",
            "source_row_id": source_row_id,
            "page_number": parsed_row.raw_row.page_number,
            "table_index": parsed_row.raw_row.table_index,
            "source_row_index": parsed_row.raw_row.source_row_index,
            "operation_time": parsed_row.operation_time_raw,
            "operation_amount_raw": parsed_row.operation_amount_raw,
            "card_amount_raw": parsed_row.card_amount_raw,
            "fee_raw": parsed_row.fee_raw,
            "cells": list(parsed_row.raw_row.cells),
        },
        operation_date_raw=parsed_row.operation_date_raw,
        posting_date_raw=parsed_row.posting_date_raw,
        description_raw=description,
        amount_raw=parsed_row.card_amount_raw or parsed_row.operation_amount_raw,
        currency_raw=operation_currency,
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


def parse_vtb_card_operation_datetime(raw: str | None) -> tuple[str | None, str | None]:
    cleaned = clean_cell(raw)
    if cleaned is None:
        return None, None
    match = CARD_OPERATION_DATETIME_RE.match(cleaned)
    if match is None:
        return None, None
    return match.group("operation_date"), match.group("operation_time")


def parse_vtb_card_amount_and_currency(
    raw: str | None,
    default_currency: str,
    normalization_errors: list[str],
) -> tuple[Decimal | None, str]:
    cleaned = clean_cell(raw)
    if cleaned is None:
        normalization_errors.append("No VTB card operation amount found.")
        return None, normalize_currency(None, default_currency)
    parts = cleaned.split()
    currency = normalize_currency(parts[-1] if len(parts) > 1 else None, default_currency)
    amount_raw = " ".join(parts[:-1]) if len(parts) > 1 else cleaned
    amount = parse_with_error(parse_vtb_card_money, amount_raw, normalization_errors)
    return amount, currency


def parse_vtb_card_money(raw: str | None) -> Decimal | None:
    cleaned = clean_cell(raw)
    if cleaned is None:
        return None
    normalized = cleaned.replace("RUB", "").replace(" ", "").replace(",", ".")
    if normalized in {"", "-", "+", ".", "-.", "+."}:
        return None
    try:
        return Decimal(normalized).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValueError(f"Unsupported VTB card amount format: {cleaned}") from exc


def stable_card_source_row_id(
    *,
    row_index: int,
    operation_date_raw: str | None,
    operation_time_raw: str | None,
    statement_period: tuple[str, str] | None,
) -> str:
    period_key = "-".join(statement_period) if statement_period is not None else "unknown-period"
    date_key = operation_date_raw or "unknown-date"
    time_key = operation_time_raw or "unknown-time"
    return f"vtb-card:{period_key}:{date_key}:{time_key}:{row_index}"


def extract_card_hint(text: str) -> str | None:
    match = CARD_NUMBER_RE.search(text)
    if match is None:
        return None
    return mask_card_number(match.group("card"))


def mask_card_number(_raw: str) -> str:
    return "карта ****"


def extract_card_statement_currency(text: str) -> str | None:
    opening_match = CARD_OPENING_TOTALS_RE.search(text)
    if opening_match is not None:
        return opening_match.group("currency")
    closing_match = CARD_CLOSING_TOTALS_RE.search(text)
    if closing_match is not None:
        return closing_match.group("currency")
    return None
