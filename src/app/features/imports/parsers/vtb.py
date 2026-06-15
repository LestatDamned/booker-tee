import re
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
PERIOD_RE = re.compile(
    r"Период выписки\s+(?P<date_from>\d{2}\.\d{2}\.\d{4})\s+-\s+"
    r"(?P<date_to>\d{2}\.\d{2}\.\d{4})"
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
        default_currency = statement_currency or currency
        drafts: list[RawTransactionDraft] = []
        for source_line_index, row_text in extract_operation_rows(text):
            drafts.append(
                build_vtb_draft(
                    row_text,
                    row_index=len(drafts),
                    source_line_index=source_line_index,
                    account_id=account_id,
                    account_hint=account_hint,
                    currency=default_currency,
                    statement_period=statement_period,
                )
            )
        return drafts

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


def extracted_text(extracted: ExtractedPdf) -> str:
    return "\n".join(page_text or "" for page_text in extracted.text_by_page)


def extract_operation_rows(text: str) -> list[tuple[int, str]]:
    rows: list[tuple[int, str]] = []
    current_line_index: int | None = None
    current_parts: list[str] = []

    for line_index, raw_line in enumerate(text.splitlines()):
        line = clean_cell(raw_line)
        if line is None:
            continue
        if ROW_START_RE.match(line):
            if current_line_index is not None and current_parts:
                rows.append((current_line_index, normalize_description(*current_parts) or ""))
            current_line_index = line_index
            current_parts = [line]
            continue
        if current_line_index is not None:
            current_parts.append(line)

    if current_line_index is not None and current_parts:
        rows.append((current_line_index, normalize_description(*current_parts) or ""))
    return rows


def build_vtb_draft(
    row_text: str,
    *,
    row_index: int,
    source_line_index: int,
    account_id: UUID | None,
    account_hint: str | None,
    currency: str,
    statement_period: tuple[str, str] | None,
) -> RawTransactionDraft:
    match = ROW_START_RE.match(row_text)
    normalization_errors: list[str] = []
    if match is None:
        normalization_errors.append("VTB row format was not recognized.")
        return RawTransactionDraft(
            row_index=row_index,
            status=RawTransactionStatus.NEEDS_REVIEW,
            raw_payload=raw_payload(row_text, source_line_index, statement_period),
            operation_date_raw=None,
            posting_date_raw=None,
            description_raw=row_text,
            amount_raw=None,
            currency_raw=None,
            balance_after_raw=None,
            account_hint_raw=account_hint,
            account_id=account_id,
            operation_date=None,
            posting_date=None,
            description_normalized=normalize_description(row_text),
            amount=None,
            currency=normalize_currency(None, currency),
            balance_after=None,
            dedupe_hash=None,
            confidence_score=Decimal("0.4000"),
            normalization_error="; ".join(normalization_errors),
        )

    data = match.groupdict()
    operation_date = parse_with_error(parse_bank_date, data["operation_date"], normalization_errors)
    posting_date = parse_with_error(parse_bank_date, data["posting_date"], normalization_errors)
    amount = signed_vtb_amount(data["inflow"], data["outflow"], normalization_errors)
    row_currency = normalize_currency(data["operation_currency"], currency)
    description = normalize_description(data["description"])
    source_row_id = stable_source_row_id(source_line_index, statement_period)
    dedupe_hash = build_dedupe_hash(
        account_id=account_id,
        operation_date=operation_date,
        amount=amount,
        currency=row_currency,
        description_normalized=description,
        source_row_id=source_row_id,
    )
    is_normalized = bool(operation_date and amount is not None and description)

    return RawTransactionDraft(
        row_index=row_index,
        status=RawTransactionStatus.NORMALIZED
        if is_normalized
        else RawTransactionStatus.NEEDS_REVIEW,
        raw_payload={
            **raw_payload(row_text, source_line_index, statement_period),
            "source_row_id": source_row_id,
            "operation_amount": data["operation_amount"],
            "operation_currency": data["operation_currency"],
            "inflow_raw": data["inflow"],
            "outflow_raw": data["outflow"],
        },
        operation_date_raw=data["operation_date"],
        posting_date_raw=data["posting_date"],
        description_raw=data["description"],
        amount_raw=data["operation_amount"],
        currency_raw=data["operation_currency"],
        balance_after_raw=None,
        account_hint_raw=account_hint,
        account_id=account_id,
        operation_date=operation_date,
        posting_date=posting_date,
        description_normalized=description,
        amount=amount,
        currency=row_currency,
        balance_after=None,
        dedupe_hash=dedupe_hash,
        confidence_score=Decimal("0.9300") if is_normalized else Decimal("0.5000"),
        normalization_error="; ".join(normalization_errors) if normalization_errors else None,
    )


def signed_vtb_amount(
    inflow_raw: str,
    outflow_raw: str,
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


def extract_statement_period(text: str) -> tuple[str, str] | None:
    match = PERIOD_RE.search(text)
    if match is None:
        return None
    return (match.group("date_from"), match.group("date_to"))


def extract_account_hint(text: str) -> tuple[str | None, str | None]:
    match = ACCOUNT_HINT_RE.search(text)
    if match is None:
        return None, None
    return match.group("account"), match.group("currency")


def parse_with_error[T](
    parser: Callable[[str | None], T | None],
    raw: str | None,
    normalization_errors: list[str],
) -> T | None:
    try:
        return parser(raw)
    except ValueError as exc:
        normalization_errors.append(str(exc))
        return None
