import re
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.features.imports.extraction.pdfplumber_extractor import ExtractedPdf
from app.features.imports.parser_types import RawTransactionDraft, StatementControlTotals
from app.features.imports.parsers.common import (
    build_raw_transaction_draft,
    extracted_text,
    parse_with_error,
)
from app.features.imports.parsers.normalization import (
    build_dedupe_hash,
    clean_cell,
    normalize_currency,
    normalize_description,
    parse_bank_date,
    parse_money_amount,
)
from app.features.imports.parsers.vtb_shared import extract_statement_period

VTB_DEPOSIT_MARKERS = (
    "Период выписки",
    "Баланс на начало периода",
    "Баланс на конец периода",
    "Операции по счету",
)
ROW_START_RE = re.compile(
    r"^(?P<operation_date>\d{2}\.\d{2}\.\d{4})\s+"
    r"(?P<posting_date>\d{2}\.\d{2}\.\d{4})\s+"
    r"(?P<operation_amount>[+-]?\d[\d,.]*[.,]\d{2})\s+"
    r"(?P<operation_currency>[A-Z]{3})\s+"
    r"(?P<inflow>[+-]?\d[\d,.]*[.,]\d{2})\s+"
    r"(?P<inflow_currency>[A-Z]{3})\s+"
    r"(?P<outflow>[+-]?\d[\d,.]*[.,]\d{2})\s+"
    r"(?P<outflow_currency>[A-Z]{3})\s+"
    r"(?P<description>.+)$"
)
OPENING_TOTALS_RE = re.compile(
    r"Баланс на начало периода\s+(?P<opening>[+-]?\d[\d,.]*[.,]\d{2})\s+"
    r"(?P<currency>[A-Z]{3})\s+Поступления\s+"
    r"(?P<inflow>[+-]?\d[\d,.]*[.,]\d{2})\s+[A-Z]{3}"
)
CLOSING_TOTALS_RE = re.compile(
    r"Баланс на конец периода\s+(?P<closing>[+-]?\d[\d,.]*[.,]\d{2})\s+"
    r"(?P<currency>[A-Z]{3})\s+Расходные операции\s+"
    r"(?P<outflow>[+-]?\d[\d,.]*[.,]\d{2})\s+[A-Z]{3}"
)
ACCOUNT_HINT_RE = re.compile(r"(?P<account>\d{20})\s+\((?P<currency>[A-Z]{3})\)")


@dataclass(frozen=True)
class VtbDepositRawRow:
    source_line_index: int
    row_text: str


@dataclass(frozen=True)
class VtbDepositParserContext:
    account_id: UUID | None
    account_hint: str | None
    currency: str
    statement_period: tuple[str, str] | None


@dataclass(frozen=True)
class VtbDepositParsedRow:
    operation_date_raw: str | None
    posting_date_raw: str | None
    operation_amount_raw: str | None
    operation_currency_raw: str | None
    inflow_raw: str | None
    outflow_raw: str | None
    description_raw: str | None
    raw_row: VtbDepositRawRow


@dataclass(frozen=True)
class VtbDepositStatementParser:
    bank_code: str = "vtb"
    statement_type: str = "deposit_statement"
    parser_name: str = "vtb_deposit_statement_v1"
    parser_version: str = "0.1"

    def can_parse(self, extracted: ExtractedPdf) -> bool:
        text = extracted_text(extracted)
        return all(marker in text for marker in VTB_DEPOSIT_MARKERS)

    def extract_raw_transactions(
        self,
        extracted: ExtractedPdf,
        *,
        account_id: UUID | None,
        currency: str,
    ) -> list[RawTransactionDraft]:
        text = extracted_text(extracted)
        statement_period = extract_statement_period(text)
        account_hint, statement_currency = extract_account_hint(text)
        context = VtbDepositParserContext(
            account_id=account_id,
            account_hint=account_hint,
            currency=statement_currency or currency,
            statement_period=statement_period,
        )
        return [
            build_vtb_draft(
                parse_vtb_deposit_row(row),
                row_index=row_index,
                context=context,
            )
            for row_index, row in enumerate(extract_operation_rows(text))
        ]

    def extract_control_totals(
        self,
        extracted: ExtractedPdf,
        *,
        currency: str,
    ) -> StatementControlTotals | None:
        text = extracted_text(extracted)
        opening_match = OPENING_TOTALS_RE.search(text)
        closing_match = CLOSING_TOTALS_RE.search(text)
        if opening_match is None and closing_match is None:
            return None

        detected_currency = (
            (opening_match.group("currency") if opening_match else None)
            or (closing_match.group("currency") if closing_match else None)
            or currency
        )
        total_outflow = (
            parse_money_amount(closing_match.group("outflow")) if closing_match else None
        )
        return StatementControlTotals(
            currency=normalize_currency(detected_currency, currency),
            opening_balance=parse_money_amount(opening_match.group("opening"))
            if opening_match
            else None,
            closing_balance=parse_money_amount(closing_match.group("closing"))
            if closing_match
            else None,
            total_inflow=parse_money_amount(opening_match.group("inflow"))
            if opening_match
            else None,
            total_outflow=abs(total_outflow) if total_outflow is not None else None,
        )


def extract_operation_rows(text: str) -> list[VtbDepositRawRow]:
    rows: list[VtbDepositRawRow] = []
    current_line_index: int | None = None
    current_parts: list[str] = []

    for line_index, raw_line in enumerate(text.splitlines()):
        line = clean_cell(raw_line)
        if line is None:
            continue
        if ROW_START_RE.match(line):
            if current_line_index is not None and current_parts:
                rows.append(
                    VtbDepositRawRow(
                        source_line_index=current_line_index,
                        row_text=normalize_description(*current_parts) or "",
                    )
                )
            current_line_index = line_index
            current_parts = [line]
            continue
        if current_line_index is not None:
            current_parts.append(line)

    if current_line_index is not None and current_parts:
        rows.append(
            VtbDepositRawRow(
                source_line_index=current_line_index,
                row_text=normalize_description(*current_parts) or "",
            )
        )
    return rows


def parse_vtb_deposit_row(row: VtbDepositRawRow) -> VtbDepositParsedRow:
    match = ROW_START_RE.match(row.row_text)
    if match is None:
        return VtbDepositParsedRow(
            operation_date_raw=None,
            posting_date_raw=None,
            operation_amount_raw=None,
            operation_currency_raw=None,
            inflow_raw=None,
            outflow_raw=None,
            description_raw=row.row_text,
            raw_row=row,
        )

    data = match.groupdict()
    return VtbDepositParsedRow(
        operation_date_raw=data["operation_date"],
        posting_date_raw=data["posting_date"],
        operation_amount_raw=data["operation_amount"],
        operation_currency_raw=data["operation_currency"],
        inflow_raw=data["inflow"],
        outflow_raw=data["outflow"],
        description_raw=data["description"],
        raw_row=row,
    )


def build_vtb_draft(
    parsed_row: VtbDepositParsedRow,
    *,
    row_index: int,
    context: VtbDepositParserContext,
) -> RawTransactionDraft:
    if not is_recognized_vtb_deposit_row(parsed_row):
        return build_unrecognized_vtb_draft(parsed_row, row_index=row_index, context=context)

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
    amount = signed_vtb_amount(parsed_row.inflow_raw, parsed_row.outflow_raw, normalization_errors)
    row_currency = normalize_currency(parsed_row.operation_currency_raw, context.currency)
    description = normalize_description(parsed_row.description_raw)
    source_row_id = stable_source_row_id(
        parsed_row.raw_row.source_line_index,
        context.statement_period,
    )
    dedupe_hash = build_dedupe_hash(
        account_id=context.account_id,
        operation_date=operation_date,
        amount=amount,
        currency=row_currency,
        description_normalized=description,
        source_row_id=source_row_id,
    )
    is_normalized = bool(operation_date and amount is not None and description)

    return build_raw_transaction_draft(
        row_index=row_index,
        raw_payload={
            **raw_payload(
                parsed_row.raw_row.row_text,
                parsed_row.raw_row.source_line_index,
                context.statement_period,
            ),
            "source_row_id": source_row_id,
            "operation_amount": parsed_row.operation_amount_raw,
            "operation_currency": parsed_row.operation_currency_raw,
            "inflow_raw": parsed_row.inflow_raw,
            "outflow_raw": parsed_row.outflow_raw,
        },
        operation_date_raw=parsed_row.operation_date_raw,
        posting_date_raw=parsed_row.posting_date_raw,
        description_raw=parsed_row.description_raw,
        amount_raw=parsed_row.operation_amount_raw,
        currency_raw=parsed_row.operation_currency_raw,
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


def is_recognized_vtb_deposit_row(parsed_row: VtbDepositParsedRow) -> bool:
    return parsed_row.operation_date_raw is not None and parsed_row.operation_amount_raw is not None


def build_unrecognized_vtb_draft(
    parsed_row: VtbDepositParsedRow,
    *,
    row_index: int,
    context: VtbDepositParserContext,
) -> RawTransactionDraft:
    return build_raw_transaction_draft(
        row_index=row_index,
        raw_payload=raw_payload(
            parsed_row.raw_row.row_text,
            parsed_row.raw_row.source_line_index,
            context.statement_period,
        ),
        operation_date_raw=None,
        posting_date_raw=None,
        description_raw=parsed_row.description_raw,
        amount_raw=None,
        currency_raw=None,
        balance_after_raw=None,
        account_hint_raw=context.account_hint,
        account_id=context.account_id,
        operation_date=None,
        posting_date=None,
        description_normalized=normalize_description(parsed_row.description_raw),
        amount=None,
        currency=normalize_currency(None, context.currency),
        balance_after=None,
        dedupe_hash=None,
        is_normalized=False,
        normalized_confidence=Decimal("0.9300"),
        review_confidence=Decimal("0.4000"),
        normalization_errors=("VTB row format was not recognized.",),
    )


def signed_vtb_amount(
    inflow_raw: str | None,
    outflow_raw: str | None,
    normalization_errors: list[str],
) -> Decimal | None:
    try:
        inflow = parse_money_amount(inflow_raw) or Decimal("0.00")
        outflow = parse_money_amount(outflow_raw) or Decimal("0.00")
    except ValueError as exc:
        normalization_errors.append(str(exc))
        return None

    has_inflow = inflow != Decimal("0.00")
    has_outflow = outflow != Decimal("0.00")
    if has_inflow and has_outflow:
        normalization_errors.append("Both VTB inflow and outflow are present.")
        return None
    if has_inflow:
        return abs(inflow)
    if has_outflow:
        return -abs(outflow)
    normalization_errors.append("No VTB inflow or outflow amount found.")
    return None


def raw_payload(
    row_text: str,
    source_line_index: int,
    statement_period: tuple[str, str] | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "bank_code": "vtb",
        "statement_type": "deposit_statement",
        "source_line_index": source_line_index,
        "row_text": row_text,
    }
    if statement_period is not None:
        payload["statement_period"] = {
            "date_from": statement_period[0],
            "date_to": statement_period[1],
        }
    return payload


def stable_source_row_id(
    source_line_index: int,
    statement_period: tuple[str, str] | None,
) -> str:
    period_key = "-".join(statement_period) if statement_period is not None else "unknown-period"
    return f"vtb-deposit:{period_key}:{source_line_index}"


def extract_account_hint(text: str) -> tuple[str | None, str | None]:
    match = ACCOUNT_HINT_RE.search(text)
    if match is None:
        return None, None
    return match.group("account"), match.group("currency")
