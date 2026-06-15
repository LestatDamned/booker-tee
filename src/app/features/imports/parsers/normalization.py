from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from re import sub
from uuid import UUID


def clean_cell(value: object) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).replace("\xa0", " ").split())
    return cleaned or None


def normalize_description(*parts: str | None) -> str | None:
    cleaned_parts = [part for part in (clean_cell(part) for part in parts) if part]
    if not cleaned_parts:
        return None
    return " | ".join(cleaned_parts)


def parse_bank_date(raw: str | None) -> date | None:
    if raw is None:
        return None
    cleaned = clean_cell(raw)
    if cleaned is None:
        return None
    for date_format in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, date_format).date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {cleaned}")


def parse_money_amount(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    cleaned = clean_cell(raw)
    if cleaned is None:
        return None
    normalized = normalize_decimal_separators(sub(r"[^\d,.\-+]", "", cleaned))
    if normalized in {"", "-", "+", ".", "-.", "+."}:
        return None
    try:
        return Decimal(normalized).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValueError(f"Unsupported amount format: {cleaned}") from exc


def normalize_currency(raw: str | None, default_currency: str) -> str:
    cleaned = clean_cell(raw)
    if cleaned is None:
        return default_currency.upper()
    normalized = cleaned.upper()
    if normalized in {"RUR", "₽", "РУБ", "РУБЛЬ", "РУБЛИ", "RUB."}:
        return "RUB"
    if len(normalized) == 3 and normalized.isalpha():
        return normalized
    return default_currency.upper()


def build_dedupe_hash(
    *,
    account_id: UUID | None,
    operation_date: date | None,
    amount: Decimal | None,
    currency: str | None,
    description_normalized: str | None,
    source_row_id: str | None,
) -> str | None:
    if operation_date is None or amount is None or currency is None:
        return None
    fingerprint = "|".join(
        [
            str(account_id or ""),
            operation_date.isoformat(),
            str(amount),
            currency,
            description_normalized or "",
            source_row_id or "",
        ]
    )
    return sha256(fingerprint.encode("utf-8")).hexdigest()


def normalize_decimal_separators(value: str) -> str:
    if "," not in value and "." not in value:
        return value

    sign = ""
    unsigned = value
    if unsigned.startswith(("-", "+")):
        sign = unsigned[0]
        unsigned = unsigned[1:]

    last_comma = unsigned.rfind(",")
    last_dot = unsigned.rfind(".")
    decimal_separator = "." if last_dot > last_comma else ","
    thousands_separator = "," if decimal_separator == "." else "."

    if decimal_separator not in unsigned:
        return sign + unsigned.replace(thousands_separator, "")

    integer_part, fractional_part = unsigned.rsplit(decimal_separator, 1)
    if thousands_separator not in unsigned and len(fractional_part) != 2:
        return sign + unsigned.replace(decimal_separator, "")
    integer_part = integer_part.replace(thousands_separator, "").replace(decimal_separator, "")
    return f"{sign}{integer_part}.{fractional_part}"
