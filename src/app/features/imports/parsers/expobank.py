from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.features.imports.extraction.pdfplumber_extractor import ExtractedPdf
from app.features.imports.models import RawTransactionStatus
from app.features.imports.parser_types import RawTransactionDraft, StatementControlTotals
from app.features.imports.parsers.normalization import (
    build_dedupe_hash,
    clean_cell,
    normalize_currency,
    normalize_description,
    parse_bank_date,
    parse_money_amount,
)


@dataclass(frozen=True)
class ExpobankCardStatementParser:
    bank_code: str = "expobank"
    statement_type: str = "card_statement"
    parser_name: str = "expobank_card_statement_v1"
    parser_version: str = "0.1"

    def can_parse(self, extracted: ExtractedPdf) -> bool:
        for page_tables in extracted.tables_by_page:
            for table in page_tables.tables:
                if table and _is_header_row(table[0]):
                    return True
        return False

    def extract_raw_transactions(
        self,
        extracted: ExtractedPdf,
        *,
        account_id: UUID | None,
        currency: str,
    ) -> list[RawTransactionDraft]:
        drafts: list[RawTransactionDraft] = []
        for page_tables in extracted.tables_by_page:
            for table_index, table in enumerate(page_tables.tables):
                for row_index, row in enumerate(table):
                    row_cells = [clean_cell(cell) for cell in row]
                    if not _looks_like_transaction_row(row_cells):
                        continue
                    drafts.append(
                        _build_draft(
                            row_cells,
                            row_index=len(drafts),
                            page_number=page_tables.page_number,
                            table_index=table_index,
                            source_row_index=row_index,
                            account_id=account_id,
                            currency=currency,
                        )
                    )
        return drafts

    def extract_control_totals(
        self,
        extracted: ExtractedPdf,
        *,
        currency: str,
    ) -> StatementControlTotals | None:
        for page_tables in extracted.tables_by_page:
            for table in page_tables.tables:
                for row in table:
                    row_cells = [clean_cell(cell) for cell in row]
                    if _cell(row_cells, 0) != "Total":
                        continue
                    return StatementControlTotals(
                        currency=normalize_currency(None, currency),
                        total_outflow=parse_money_amount(_cell(row_cells, 2)),
                        total_inflow=parse_money_amount(_cell(row_cells, 3)),
                    )
        return None


def _is_header_row(row: list[str | None]) -> bool:
    cleaned = [clean_cell(cell) for cell in row]
    return {"document", "processed at", "debiting", "crediting"}.issubset(
        {cell.lower() for cell in cleaned if cell}
    )


def _looks_like_transaction_row(row: list[str | None]) -> bool:
    document_number = _cell(row, 0)
    if document_number is None or document_number.lower() == "total":
        return False
    if document_number.lower() == "document":
        return False
    has_amount = _cell(row, 2) is not None or _cell(row, 3) is not None
    return document_number.startswith("№") and has_amount


def _build_draft(
    row: list[str | None],
    *,
    row_index: int,
    page_number: int,
    table_index: int,
    source_row_index: int,
    account_id: UUID | None,
    currency: str,
) -> RawTransactionDraft:
    source_row_id = _cell(row, 0)
    operation_date_raw = _cell(row, 1)
    debit_raw = _cell(row, 2)
    credit_raw = _cell(row, 3)
    counterparty_raw = _cell(row, 4)
    account_hint_raw = _cell(row, 5)
    purpose_raw = _cell(row, 6)
    description_raw = normalize_description(purpose_raw, counterparty_raw)
    currency_normalized = normalize_currency(None, currency)

    normalization_errors: list[str] = []
    operation_date = _parse_with_error(parse_bank_date, operation_date_raw, normalization_errors)
    amount = _signed_amount(debit_raw, credit_raw, normalization_errors)
    description_normalized = normalize_description(description_raw)
    dedupe_hash = build_dedupe_hash(
        account_id=account_id,
        operation_date=operation_date,
        amount=amount,
        currency=currency_normalized,
        description_normalized=description_normalized,
        source_row_id=source_row_id,
    )
    is_normalized = bool(operation_date and amount is not None and description_normalized)

    return RawTransactionDraft(
        row_index=row_index,
        status=RawTransactionStatus.NORMALIZED
        if is_normalized
        else RawTransactionStatus.NEEDS_REVIEW,
        raw_payload={
            "bank_code": "expobank",
            "source_row_id": source_row_id,
            "page_number": page_number,
            "table_index": table_index,
            "source_row_index": source_row_index,
            "cells": row,
        },
        operation_date_raw=operation_date_raw,
        posting_date_raw=None,
        description_raw=description_raw,
        amount_raw=credit_raw or debit_raw,
        currency_raw=None,
        balance_after_raw=None,
        account_hint_raw=account_hint_raw,
        account_id=account_id,
        operation_date=operation_date,
        posting_date=None,
        description_normalized=description_normalized,
        amount=amount,
        currency=currency_normalized,
        balance_after=None,
        dedupe_hash=dedupe_hash,
        confidence_score=Decimal("0.9500") if is_normalized else Decimal("0.5000"),
        normalization_error="; ".join(normalization_errors) if normalization_errors else None,
    )


def _cell(row: list[str | None], index: int) -> str | None:
    if index >= len(row):
        return None
    return row[index]


def _signed_amount(
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


def _parse_with_error[T](
    parser: Callable[[str | None], T | None],
    raw: str | None,
    normalization_errors: list[str],
) -> T | None:
    try:
        return parser(raw)
    except ValueError as exc:
        normalization_errors.append(str(exc))
        return None
