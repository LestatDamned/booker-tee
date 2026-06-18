import re

DATE_PATTERNS = (
    re.compile(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b"),
    re.compile(r"\b\d{4}-\d{1,2}-\d{1,2}\b"),
)
MONEY_PATTERN = re.compile(
    r"^(?:₽|\$|€|£)?\s*[+-]?\s*\d[\d\s]*(?:[,.]\d{2})\s*"
    r"(?:₽|руб\.?|rub|rur|usd|eur|gbp|cny|try|aed|\$|€|£)?$",
    flags=re.IGNORECASE,
)
SIGNED_INTEGER_MONEY_PATTERN = re.compile(
    r"^(?:₽|\$|€|£)?\s*[+-]\s*\d[\d\s]*"
    r"(?:₽|руб\.?|rub|rur|usd|eur|gbp|cny|try|aed|\$|€|£)?$",
    flags=re.IGNORECASE,
)
CURRENCY_PATTERN = re.compile(r"\b(?:rub|rur|usd|eur|gbp|cny|try|aed)\b|[₽$€£]")


def is_date_like_cell(value: str) -> bool:
    compacted = normalize_cell(value)
    if not compacted:
        return False
    return any(pattern.search(compacted) for pattern in DATE_PATTERNS)


def is_money_like_cell(value: str) -> bool:
    compacted = normalize_cell(value)
    if not compacted or not any(character.isdigit() for character in compacted):
        return False
    return bool(
        MONEY_PATTERN.fullmatch(compacted) or SIGNED_INTEGER_MONEY_PATTERN.fullmatch(compacted)
    )


def is_currency_like_cell(value: str) -> bool:
    compacted = normalize_cell(value)
    if not compacted:
        return False
    normalized = compacted.casefold()
    return bool(CURRENCY_PATTERN.fullmatch(normalized))


def is_description_like_cell(value: str) -> bool:
    compacted = normalize_cell(value)
    if len(compacted) < 3 or is_currency_like_cell(compacted):
        return False
    if MONEY_PATTERN.fullmatch(compacted) or SIGNED_INTEGER_MONEY_PATTERN.fullmatch(compacted):
        return False
    return cell_has_letters(compacted)


def cell_has_letters(value: str) -> bool:
    return any(character.isalpha() for character in value)


def normalize_cell(value: str) -> str:
    return " ".join(value.split())
