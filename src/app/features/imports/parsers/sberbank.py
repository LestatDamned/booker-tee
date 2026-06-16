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

SBERBANK_CARD_MARKERS = (
    "Выписка по счёту дебетовой карты",
    "ИТОГО ПО ОПЕРАЦИЯМ ЗА ПЕРИОД",
    "Расшифровка операций",
)
NON_OPERATION_NOISE_PREFIXES = {
    "Продолжение на следующей странице",
    "Выписка по счёту дебетовой карты Страница",
    "Для проверки подлинности документа",
    "1. Зайдите в приложение СберБанк Онлайн в раздел «Выписки и справки»",
    "2. Нажмите кнопку в верхнем правом углу и отсканируйте QR-код*",
    "3. Получите документ в электронном виде",
    "* Предоставляя QR-код третьим лицам",
    "Действителен",
    "ДАТА ОПЕРАЦИИ (МСК) КАТЕГОРИЯ СУММА В ВАЛЮТЕ СЧЁТА ОСТАТОК СРЕДСТВ",
    "Дата обработки1 Описание операции Сумма в валюте В валюте счёта",
    "и код авторизации операции2",
}
ROW_START_RE = re.compile(
    r"^(?P<operation_date>\d{2}\.\d{2}\.\d{4})\s+"
    r"(?P<operation_time>\d{2}:\d{2})\s+"
    r"(?P<category_code>\d+)\s+"
    r"(?P<amount>[+\-]?\d[\d ]*?[,.]\d{2})\s+"
    r"(?P<balance_after>[+\-]?\d[\d ]*[,.]\d{2})$"
)
DETAIL_RE = re.compile(
    r"^(?P<posting_date>\d{2}\.\d{2}\.\d{4})\s+"
    r"(?P<auth_code>\d+)\s+"
    r"(?P<description>.+)$"
)
PERIOD_RE = re.compile(
    r"За период\s+(?P<date_from>\d{2}\.\d{2}\.\d{4})\s+[—-]\s+"
    r"(?P<date_to>\d{2}\.\d{2}\.\d{4})"
)
OPENING_BALANCE_RE = re.compile(r"Остаток на\s+\d{2}\.\d{2}\.\d{4}\s+(?P<amount>\d[\d ]*[,.]\d{2})")
CLOSING_BALANCE_RE = re.compile(r"Остаток на\s+\d{2}\.\d{2}\.\d{4}\s+(?P<amount>\d[\d ]*[,.]\d{2})")
ACCOUNT_INFLOWS_RE = re.compile(
    r"Номер счёта\s+(?P<account>[\d ]+)\s+Пополнение\s+"
    r"(?P<amount>\d[\d ]*[,.]\d{2})"
)
CARD_OUTFLOWS_RE = re.compile(r"Карта\s+(?P<card>.+?)\s+Списание\s+(?P<amount>\d[\d ]*[,.]\d{2})")


@dataclass(frozen=True)
class SberbankOperationRow:
    source_line_index: int
    row_start: str
    detail_lines: tuple[str, ...]


@dataclass(frozen=True)
class SberbankCardStatementParser:
    bank_code: str = "sberbank"
    statement_type: str = "card_statement"
    parser_name: str = "sberbank_card_statement_v1"
    parser_version: str = "0.1"

    def can_parse(self, extracted: ExtractedPdf) -> bool:
        text = extracted_text(extracted)
        return all(marker in text for marker in SBERBANK_CARD_MARKERS)

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
        for row in extract_operation_rows(text):
            drafts.append(
                build_sberbank_draft(
                    row,
                    row_index=len(drafts),
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
        account_match = ACCOUNT_INFLOWS_RE.search(text)
        card_match = CARD_OUTFLOWS_RE.search(text)
        balance_matches = CLOSING_BALANCE_RE.findall(text)
        if account_match is None and card_match is None and not balance_matches:
            return None

        return StatementControlTotals(
            currency=normalize_currency(extract_statement_currency(text), currency),
            opening_balance=parse_money_amount(balance_matches[0]) if balance_matches else None,
            closing_balance=parse_money_amount(balance_matches[-1]) if balance_matches else None,
            total_inflow=parse_money_amount(account_match.group("amount"))
            if account_match
            else None,
            total_outflow=parse_money_amount(card_match.group("amount")) if card_match else None,
        )


def extracted_text(extracted: ExtractedPdf) -> str:
    return "\n".join(page_text or "" for page_text in extracted.text_by_page)


def extract_operation_rows(text: str) -> list[SberbankOperationRow]:
    rows: list[SberbankOperationRow] = []
    current_line_index: int | None = None
    current_start: str | None = None
    current_details: list[str] = []

    for line_index, raw_line in enumerate(text.splitlines()):
        line = clean_cell(raw_line)
        if line is None:
            continue
        if ROW_START_RE.match(line):
            if current_line_index is not None and current_start is not None:
                rows.append(
                    SberbankOperationRow(
                        source_line_index=current_line_index,
                        row_start=current_start,
                        detail_lines=tuple(current_details),
                    )
                )
            current_line_index = line_index
            current_start = line
            current_details = []
            continue
        if current_start is not None:
            if is_after_operations_footer(line):
                break
            if is_non_operation_noise(line):
                continue
            current_details.append(line)

    if current_line_index is not None and current_start is not None:
        rows.append(
            SberbankOperationRow(
                source_line_index=current_line_index,
                row_start=current_start,
                detail_lines=tuple(current_details),
            )
        )
    return rows


def build_sberbank_draft(
    row: SberbankOperationRow,
    *,
    row_index: int,
    account_id: UUID | None,
    account_hint: str | None,
    currency: str,
    statement_period: tuple[str, str] | None,
) -> RawTransactionDraft:
    match = ROW_START_RE.match(row.row_start)
    normalization_errors: list[str] = []
    if match is None:
        normalization_errors.append("Sberbank row format was not recognized.")
        return needs_review_draft(row, row_index, account_id, account_hint, currency)

    data = match.groupdict()
    detail = parse_detail(row.detail_lines)
    operation_date = parse_with_error(parse_bank_date, data["operation_date"], normalization_errors)
    posting_date = parse_with_error(parse_bank_date, detail.posting_date_raw, normalization_errors)
    amount = signed_sberbank_amount(data["amount"], normalization_errors)
    row_currency = normalize_currency(None, currency)
    balance_after = parse_with_error(
        parse_money_amount,
        data["balance_after"],
        normalization_errors,
    )
    description = normalize_description(detail.description_raw)
    source_row_id = stable_source_row_id(
        auth_code=detail.auth_code,
        source_line_index=row.source_line_index,
        statement_period=statement_period,
    )
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
            **raw_payload(row, statement_period),
            "source_row_id": source_row_id,
            "operation_time": data["operation_time"],
            "category_code": data["category_code"],
            "auth_code": detail.auth_code,
        },
        operation_date_raw=data["operation_date"],
        posting_date_raw=detail.posting_date_raw,
        description_raw=detail.description_raw,
        amount_raw=data["amount"],
        currency_raw=None,
        balance_after_raw=data["balance_after"],
        account_hint_raw=account_hint,
        account_id=account_id,
        operation_date=operation_date,
        posting_date=posting_date,
        description_normalized=description,
        amount=amount,
        currency=row_currency,
        balance_after=balance_after,
        dedupe_hash=dedupe_hash,
        confidence_score=Decimal("0.9200") if is_normalized else Decimal("0.5000"),
        normalization_error="; ".join(normalization_errors) if normalization_errors else None,
    )


@dataclass(frozen=True)
class SberbankDetail:
    posting_date_raw: str | None
    auth_code: str | None
    description_raw: str | None


def parse_detail(detail_lines: tuple[str, ...]) -> SberbankDetail:
    if not detail_lines:
        return SberbankDetail(posting_date_raw=None, auth_code=None, description_raw=None)

    first_line = detail_lines[0]
    match = DETAIL_RE.match(first_line)
    if match is None:
        return SberbankDetail(
            posting_date_raw=None,
            auth_code=None,
            description_raw=normalize_description(*detail_lines),
        )

    data = match.groupdict()
    return SberbankDetail(
        posting_date_raw=data["posting_date"],
        auth_code=data["auth_code"],
        description_raw=normalize_description(data["description"], *detail_lines[1:]),
    )


def needs_review_draft(
    row: SberbankOperationRow,
    row_index: int,
    account_id: UUID | None,
    account_hint: str | None,
    currency: str,
) -> RawTransactionDraft:
    return RawTransactionDraft(
        row_index=row_index,
        status=RawTransactionStatus.NEEDS_REVIEW,
        raw_payload=raw_payload(row, None),
        operation_date_raw=None,
        posting_date_raw=None,
        description_raw=normalize_description(row.row_start, *row.detail_lines),
        amount_raw=None,
        currency_raw=None,
        balance_after_raw=None,
        account_hint_raw=account_hint,
        account_id=account_id,
        operation_date=None,
        posting_date=None,
        description_normalized=normalize_description(row.row_start, *row.detail_lines),
        amount=None,
        currency=normalize_currency(None, currency),
        balance_after=None,
        dedupe_hash=None,
        confidence_score=Decimal("0.4000"),
        normalization_error="Sberbank row format was not recognized.",
    )


def signed_sberbank_amount(raw: str, normalization_errors: list[str]) -> Decimal | None:
    try:
        amount = parse_money_amount(raw)
    except ValueError as exc:
        normalization_errors.append(str(exc))
        return None
    if amount is None:
        normalization_errors.append("No Sberbank amount found.")
        return None

    cleaned = clean_cell(raw) or ""
    if cleaned.startswith("+"):
        return abs(amount)
    if cleaned.startswith("-"):
        return -abs(amount)
    return -abs(amount)


def raw_payload(
    row: SberbankOperationRow,
    statement_period: tuple[str, str] | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "bank_code": "sberbank",
        "statement_type": "card_statement",
        "source_line_index": row.source_line_index,
        "row_start": row.row_start,
        "detail_lines": list(row.detail_lines),
    }
    if statement_period is not None:
        payload["statement_period"] = {
            "date_from": statement_period[0],
            "date_to": statement_period[1],
        }
    return payload


def stable_source_row_id(
    *,
    auth_code: str | None,
    source_line_index: int,
    statement_period: tuple[str, str] | None,
) -> str:
    period_key = "-".join(statement_period) if statement_period is not None else "unknown-period"
    row_key = auth_code or str(source_line_index)
    return f"sberbank-card:{period_key}:{row_key}"


def extract_statement_period(text: str) -> tuple[str, str] | None:
    match = PERIOD_RE.search(text)
    if match is None:
        return None
    return (match.group("date_from"), match.group("date_to"))


def extract_account_hint(text: str) -> tuple[str | None, str | None]:
    account_match = ACCOUNT_INFLOWS_RE.search(text)
    card_match = CARD_OUTFLOWS_RE.search(text)
    account = account_match.group("account").replace(" ", "") if account_match else None
    card = card_match.group("card") if card_match else None
    hint = normalize_description(account, card)
    return hint, extract_statement_currency(text)


def extract_statement_currency(text: str) -> str | None:
    if "Валюта Российский рубль" in text:
        return "RUB"
    return None


def is_after_operations_footer(line: str) -> bool:
    return line == "*" or line.startswith("Дата формирования документа")


def is_non_operation_noise(line: str) -> bool:
    return any(line.startswith(prefix) for prefix in NON_OPERATION_NOISE_PREFIXES)


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
