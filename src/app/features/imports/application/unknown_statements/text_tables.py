import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, cast

from app.features.imports.application.unknown_statements.table_analysis import (
    build_table_preview,
)
from app.features.imports.application.unknown_statements.table_preview_dto import (
    UnknownStatementTablePreview,
)
from app.features.imports.application.unknown_statements.value_detectors import (
    DATE_PATTERNS,
    normalize_cell,
)
from app.features.imports.infrastructure.extraction.extracted_statement import ExtractedStatement
from app.features.imports.parsing.support.normalization import (
    normalize_currency,
    parse_money_amount,
)

TEXT_TABLE_HEADER = ["Date", "Description", "Amount", "Currency", "Balance"]
TEXT_TABLE_SOURCE_TYPE = "text_candidate"
MAX_TEXT_CANDIDATE_ROWS_PER_PAGE = 300

MONEY_FRAGMENT_PATTERN = re.compile(
    r"(?<![\d./:-])"
    r"(?:[₽$€£]\s*)?"
    r"(?:[+-]\s*)?"
    r"(?:\d{1,3}(?:[\s\u00a0]\d{3})+|\d+)"
    r"(?:[,.]\d{2})?"
    r"\s*(?:₽|руб\.?|rub|rur|usd|eur|gbp|cny|try|aed|[$€£])?"
    r"(?![\d./:-])",
    flags=re.IGNORECASE,
)
MONEY_HAS_AMOUNT_MARKER_PATTERN = re.compile(
    r"[+-]|[,.]\d{2}\b|₽|руб\.?|rub|rur|usd|eur|gbp|cny|try|aed|[$€£]",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class TextCandidateTable:
    page_number: int
    table_index: int
    rows: list[list[str]]


@dataclass(frozen=True)
class MoneyFragment:
    raw: str
    start: int
    end: int
    value: Decimal


def build_text_candidate_table_previews(
    extracted: ExtractedStatement,
) -> list[UnknownStatementTablePreview]:
    return [
        build_table_preview(
            nullable_table_rows(table.rows),
            page_number=table.page_number,
            table_index=table.table_index,
            source_type=TEXT_TABLE_SOURCE_TYPE,
        )
        for table in build_text_candidate_tables(extracted)
    ]


def raw_tables_with_text_candidate_tables(
    extracted: ExtractedStatement,
    raw_tables: list[dict[str, object]] | None,
) -> list[dict[str, object]]:
    candidate_tables = build_text_candidate_tables(extracted)
    if not candidate_tables:
        return list(raw_tables or [])

    raw_tables_by_page = raw_tables_by_page_number(raw_tables)
    for candidate_table in candidate_tables:
        page_payload = raw_tables_by_page.setdefault(
            candidate_table.page_number,
            {"page_number": candidate_table.page_number, "tables": []},
        )
        tables = page_payload.get("tables")
        if isinstance(tables, list):
            cast(list[Any], tables).append(candidate_table.rows)

    return [raw_tables_by_page[page_number] for page_number in sorted(raw_tables_by_page)]


def build_text_candidate_tables(extracted: ExtractedStatement) -> list[TextCandidateTable]:
    tables: list[TextCandidateTable] = []
    existing_table_counts = {
        page_tables.page_number: len(page_tables.tables) for page_tables in extracted.tables_by_page
    }
    for page_number, page_text in enumerate(extracted.text_by_page, start=1):
        candidate_rows = text_candidate_rows_for_page(page_text)
        if not candidate_rows:
            continue
        tables.append(
            TextCandidateTable(
                page_number=page_number,
                table_index=existing_table_counts.get(page_number, 0),
                rows=[TEXT_TABLE_HEADER, *candidate_rows],
            )
        )
    return tables


def text_candidate_rows_for_page(page_text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in page_text.splitlines():
        row = text_candidate_row(line)
        if row is None:
            if rows and continuation_line(line):
                rows[-1][1] = normalize_cell(f"{rows[-1][1]} {line}")
            continue
        rows.append(row)
        if len(rows) >= MAX_TEXT_CANDIDATE_ROWS_PER_PAGE:
            break
    return rows


def text_candidate_row(line: str) -> list[str] | None:
    cleaned = normalize_cell(line)
    if not cleaned:
        return None
    dates = date_fragments(cleaned)
    money_fragments = find_money_fragments(cleaned)
    if not dates or not money_fragments:
        return None

    amount = select_operation_amount(money_fragments)
    if amount is None:
        return None
    balance = select_balance_after(money_fragments, amount)
    description = text_candidate_description(cleaned, money_fragments)
    if not description:
        return None

    return [
        dates[0],
        description,
        amount.raw,
        currency_from_money(amount.raw),
        balance.raw if balance is not None else "",
    ]


def date_fragments(value: str) -> list[str]:
    matches: list[tuple[int, str]] = []
    for pattern in DATE_PATTERNS:
        matches.extend((match.start(), match.group(0)) for match in pattern.finditer(value))
    return [raw for _, raw in sorted(matches, key=lambda item: item[0])]


def find_money_fragments(value: str) -> list[MoneyFragment]:
    fragments: list[MoneyFragment] = []
    for match in MONEY_FRAGMENT_PATTERN.finditer(value):
        raw = normalize_cell(match.group(0))
        if not raw or not MONEY_HAS_AMOUNT_MARKER_PATTERN.search(raw):
            continue
        try:
            parsed = parse_money_amount(raw)
        except ValueError:
            continue
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


def select_operation_amount(fragments: list[MoneyFragment]) -> MoneyFragment | None:
    for fragment in fragments:
        if money_fragment_is_signed(fragment.raw):
            return fragment
    return fragments[0] if fragments else None


def select_balance_after(
    fragments: list[MoneyFragment],
    amount: MoneyFragment,
) -> MoneyFragment | None:
    for fragment in fragments:
        if fragment == amount:
            continue
        if fragment.start > amount.end:
            return fragment
    return None


def money_fragment_is_signed(value: str) -> bool:
    return bool(re.match(r"^[^\d]*[+-]", value.strip()))


def text_candidate_description(
    line: str,
    money_fragments: list[MoneyFragment],
) -> str:
    description = line
    removals = date_spans(line)
    removals.extend((fragment.start, fragment.end) for fragment in money_fragments)
    for start, end in sorted(removals, reverse=True):
        description = f"{description[:start]} {description[end:]}"
    return normalize_cell(description)


def date_spans(value: str) -> list[tuple[int, int]]:
    matches: list[tuple[int, int]] = []
    for pattern in DATE_PATTERNS:
        matches.extend((match.start(), match.end()) for match in pattern.finditer(value))
    return matches


def currency_from_money(value: str) -> str:
    lowered = value.casefold()
    if "₽" in value or "руб" in lowered or "rub" in lowered or "rur" in lowered:
        return "RUB"
    if "$" in value or "usd" in lowered:
        return "USD"
    if "€" in value or "eur" in lowered:
        return "EUR"
    if "£" in value or "gbp" in lowered:
        return "GBP"
    for code in ("cny", "try", "aed"):
        if code in lowered:
            return code.upper()
    return normalize_currency(None, "")


def continuation_line(line: str) -> bool:
    cleaned = normalize_cell(line)
    if len(cleaned) < 3:
        return False
    return not date_fragments(cleaned) and not find_money_fragments(cleaned)


def raw_tables_by_page_number(
    raw_tables: list[dict[str, object]] | None,
) -> dict[int, dict[str, object]]:
    pages: dict[int, dict[str, object]] = {}
    for page_payload in raw_tables or []:
        page_number = page_payload.get("page_number")
        tables = page_payload.get("tables")
        if isinstance(page_number, int) and isinstance(tables, list):
            pages[page_number] = {
                **page_payload,
                "tables": list(tables),
            }
    return pages


def nullable_table_rows(rows: list[list[str]]) -> list[list[str | None]]:
    converted: list[list[str | None]] = []
    for row in rows:
        converted.append(list(row))
    return converted
