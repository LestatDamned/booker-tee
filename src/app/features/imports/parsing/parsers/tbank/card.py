import re
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.features.imports.application.unknown_statements.text_tables import (
    MoneyFragment,
    currency_from_money,
    date_fragments,
)
from app.features.imports.infrastructure.extraction.extracted_statement import ExtractedStatement
from app.features.imports.parsing.parser_types import RawTransactionDraft, StatementControlTotals
from app.features.imports.parsing.support.common import (
    build_raw_transaction_draft,
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

TBANK_MARKERS = (
    "выписка по договору",
    "операции по карте",
    "описание операции в валюте счёта",
)
SERVICE_LINE_KEYWORDS = (
    "баланс на",
    "выписка по договору",
    "операции по карте",
    "дата и время",
    "дата операции",
    "дата обработки",
    "описание операции",
    "сумма операции",
    "сумма в валюте",
)
BALANCE_RE = re.compile(r"Баланс на\s+\d{2}\.\d{2}\.\d{2,4}\s+(?P<amount>[^\n]+)")
TOTAL_INFLOW_RE = re.compile(r"Поступления\s+(?P<amount>[^\n]+)")
TOTAL_OUTFLOW_RE = re.compile(r"Расходы\s+(?P<amount>[-+]?\s*[^\n]+)")
TBANK_MONEY_PATTERN = re.compile(
    r"(?<![^\W_])"
    r"(?:[+-]\s*)?"
    r"(?:\d{1,3}(?:[\s\u00a0]\d{3})+|\d+)"
    r"(?:[,.]\d{2})?"
    r"\s*(?:₽|руб\.?|rub|rur)"
    r"(?![^\W_])",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class TbankCardRawRow:
    page_number: int
    source_line_index: int
    line: str
    operation_date_raw: str | None
    posting_date_raw: str | None
    description_raw: str | None
    operation_amount_raw: str | None
    account_amount_raw: str | None
    currency_raw: str | None
    direction: int | None
    continuation_lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class TbankCardParserContext:
    account_id: UUID | None
    currency: str
    account_hint: str | None


@dataclass(frozen=True)
class TbankCardParsedRow:
    source_row_id: str
    operation_date_raw: str | None
    posting_date_raw: str | None
    description_raw: str | None
    amount_raw: str | None
    currency_raw: str | None
    raw_row: TbankCardRawRow


@dataclass(frozen=True)
class TbankCardStatementParser:
    bank_code: str = "tbank"
    statement_type: str = "card_statement"
    parser_name: str = "tbank_card_statement_v1"
    parser_version: str = "0.1"

    def can_parse(self, extracted: ExtractedStatement) -> bool:
        if extracted.metadata.get("source_format") != "pdf":
            return False
        text = normalized_text(extracted)
        return all(marker in text for marker in TBANK_MARKERS)

    def extract_raw_transactions(
        self,
        extracted: ExtractedStatement,
        *,
        account_id: UUID | None,
        currency: str,
    ) -> list[RawTransactionDraft]:
        context = TbankCardParserContext(
            account_id=account_id,
            currency=currency,
            account_hint=extract_card_hint(extracted),
        )
        return [
            build_tbank_card_draft(
                parse_tbank_card_row(row),
                row_index=row_index,
                context=context,
            )
            for row_index, row in enumerate(extract_tbank_card_rows(extracted))
        ]

    def extract_control_totals(
        self,
        extracted: ExtractedStatement,
        *,
        currency: str,
    ) -> StatementControlTotals | None:
        text = extracted_text(extracted)
        balances = money_matches(BALANCE_RE, text)
        total_inflow = first_money_match(TOTAL_INFLOW_RE, text)
        total_outflow = first_money_match(TOTAL_OUTFLOW_RE, text)
        if not balances and total_inflow is None and total_outflow is None:
            return None
        return StatementControlTotals(
            currency=currency.upper(),
            opening_balance=balances[0] if balances else None,
            closing_balance=balances[-1] if balances else None,
            total_inflow=total_inflow,
            total_outflow=abs(total_outflow) if total_outflow is not None else None,
        )


def normalized_text(extracted: ExtractedStatement) -> str:
    return " ".join(extracted_text(extracted).casefold().split())


def extract_tbank_card_rows(extracted: ExtractedStatement) -> list[TbankCardRawRow]:
    rows: list[TbankCardRawRow] = []
    for page_number, page_text in enumerate(extracted.text_by_page, start=1):
        for source_line_index, line in enumerate(page_text.splitlines()):
            cleaned = clean_cell(line)
            if cleaned is None:
                continue

            row = parse_tbank_card_start_line(
                cleaned,
                page_number=page_number,
                source_line_index=source_line_index,
            )
            if row is not None:
                rows.append(row)
                continue

            if rows and tbank_description_continuation(cleaned):
                rows[-1] = append_description_continuation(rows[-1], cleaned)
    return rows


def parse_tbank_card_start_line(
    line: str,
    *,
    page_number: int,
    source_line_index: int,
) -> TbankCardRawRow | None:
    dates = date_fragments(line)
    if len(dates) < 2:
        return None

    money_fragments = tbank_money_fragments(line)
    if len(money_fragments) < 2:
        return None

    operation_amount = money_fragments[-2]
    account_amount = money_fragments[-1]
    description = tbank_description(line, operation_amount.start)
    if not description:
        return None

    return TbankCardRawRow(
        page_number=page_number,
        source_line_index=source_line_index,
        line=line,
        operation_date_raw=dates[0],
        posting_date_raw=dates[1],
        description_raw=description,
        operation_amount_raw=operation_amount.raw,
        account_amount_raw=account_amount.raw,
        currency_raw=currency_from_money(account_amount.raw or operation_amount.raw),
        direction=tbank_amount_direction(operation_amount.raw),
    )


def parse_tbank_card_row(row: TbankCardRawRow) -> TbankCardParsedRow:
    return TbankCardParsedRow(
        source_row_id=stable_source_row_id(row),
        operation_date_raw=row.operation_date_raw,
        posting_date_raw=row.posting_date_raw,
        description_raw=tbank_full_description(row),
        amount_raw=signed_tbank_amount_raw(row.operation_amount_raw),
        currency_raw=row.currency_raw,
        raw_row=row,
    )


def build_tbank_card_draft(
    parsed_row: TbankCardParsedRow,
    *,
    row_index: int,
    context: TbankCardParserContext,
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
    amount = parse_with_error(parse_money_amount, parsed_row.amount_raw, normalization_errors)
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
            "bank_code": "tbank",
            "statement_type": "card_statement",
            "source_row_id": parsed_row.source_row_id,
            "page_number": parsed_row.raw_row.page_number,
            "source_line_index": parsed_row.raw_row.source_line_index,
            "line": parsed_row.raw_row.line,
            "operation_amount_raw": parsed_row.raw_row.operation_amount_raw,
            "account_amount_raw": parsed_row.raw_row.account_amount_raw,
            "direction": tbank_direction_name(parsed_row.raw_row.direction),
            "continuation_lines": list(parsed_row.raw_row.continuation_lines),
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
        normalized_confidence=Decimal("0.8500"),
        normalization_errors=normalization_errors,
    )


def stable_source_row_id(row: TbankCardRawRow) -> str:
    return f"tbank-card:{row.page_number}:{row.source_line_index}"


def tbank_description(line: str, amount_start: int) -> str | None:
    without_amounts = line[:amount_start]
    for raw_date in date_fragments(without_amounts):
        without_amounts = without_amounts.replace(raw_date, " ", 1)
    return clean_cell(without_amounts)


def tbank_description_continuation(line: str) -> bool:
    lowered = line.casefold()
    if any(keyword in lowered for keyword in SERVICE_LINE_KEYWORDS):
        return False
    if len(date_fragments(line)) >= 2 and len(tbank_money_fragments(line)) >= 2:
        return False
    return True


def append_description_continuation(row: TbankCardRawRow, line: str) -> TbankCardRawRow:
    return TbankCardRawRow(
        page_number=row.page_number,
        source_line_index=row.source_line_index,
        line=row.line,
        operation_date_raw=row.operation_date_raw,
        posting_date_raw=row.posting_date_raw,
        description_raw=row.description_raw,
        operation_amount_raw=row.operation_amount_raw,
        account_amount_raw=row.account_amount_raw,
        currency_raw=row.currency_raw,
        direction=row.direction,
        continuation_lines=(*row.continuation_lines, line),
    )


def tbank_full_description(row: TbankCardRawRow) -> str | None:
    parts = [part for part in (row.description_raw, *row.continuation_lines) if part]
    return clean_cell(" ".join(parts))


def signed_tbank_amount_raw(amount_raw: str | None) -> str | None:
    if amount_raw is None:
        return None
    parsed = parse_money_amount(amount_raw)
    if parsed is None:
        return amount_raw
    signed = parsed if tbank_amount_has_explicit_sign(amount_raw) else -abs(parsed)
    return str(signed)


def tbank_amount_has_explicit_sign(amount_raw: str) -> bool:
    cleaned = clean_cell(amount_raw) or ""
    return cleaned.startswith(("+", "-"))


def tbank_amount_direction(amount_raw: str | None) -> int | None:
    signed_amount = signed_tbank_amount_raw(amount_raw)
    parsed = parse_money_amount(signed_amount)
    if parsed is None:
        return None
    if parsed < 0:
        return -1
    return 1


def tbank_money_fragments(line: str) -> list[MoneyFragment]:
    fragments: list[MoneyFragment] = []
    for match in TBANK_MONEY_PATTERN.finditer(line):
        raw = clean_cell(match.group(0))
        if raw is None:
            continue
        parsed = parse_money_amount(raw)
        if parsed is None:
            continue
        fragments.append(
            MoneyFragment(
                raw=raw,
                start=match.start(),
                end=match.end(),
                value=parsed,
            )
        )
    return fragments


def tbank_direction_name(direction: int | None) -> str | None:
    if direction is None:
        return None
    if direction < 0:
        return "outflow"
    return "inflow"


def extract_card_hint(extracted: ExtractedStatement) -> str | None:
    text = normalized_text(extracted)
    if "операции по карте" in text:
        return "карта ****"
    return None


def money_matches(pattern: re.Pattern[str], text: str) -> list[Decimal]:
    amounts: list[Decimal] = []
    for match in pattern.finditer(text):
        amount = parse_control_amount(match.group("amount"))
        if amount is not None:
            amounts.append(amount)
    return amounts


def first_money_match(pattern: re.Pattern[str], text: str) -> Decimal | None:
    amounts = money_matches(pattern, text)
    return amounts[0] if amounts else None


def parse_control_amount(raw: str | None) -> Decimal | None:
    cleaned = clean_cell(raw)
    if cleaned is None:
        return None
    try:
        return parse_money_amount(cleaned)
    except ValueError:
        return None
