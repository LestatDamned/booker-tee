import re
from decimal import Decimal

from app.features.imports.application.unknown_statements.hints import (
    ControlTotalLabelSet,
    control_total_label_sets_for_text,
)
from app.features.imports.parsing.parser_types import StatementControlTotals
from app.features.imports.parsing.support.normalization import parse_money_amount


def extract_unknown_statement_control_totals(
    text_by_page: list[str] | None,
) -> StatementControlTotals | None:
    if not text_by_page:
        return None
    text = "\n".join(text_by_page)
    currency = detect_statement_currency(text)
    control_total_labels = control_total_label_sets_for_text(text)
    opening_balance = find_money_after_any_label(
        text,
        control_total_labels,
        field="opening_balance",
    )
    closing_balance = find_money_after_any_label(
        text,
        control_total_labels,
        field="closing_balance",
    )
    total_inflow = find_money_after_any_label(
        text,
        control_total_labels,
        field="total_inflow",
    )
    total_outflow = find_money_after_any_label(
        text,
        control_total_labels,
        field="total_outflow",
    )
    if not any([opening_balance, closing_balance, total_inflow, total_outflow]):
        return None
    return StatementControlTotals(
        currency=currency,
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        total_inflow=total_inflow,
        total_outflow=abs(total_outflow) if total_outflow is not None else None,
    )


def detect_statement_currency(text: str) -> str:
    normalized = text.casefold()
    if "российский рубль" in normalized or "₽" in text:
        return "RUB"
    if "usd" in normalized or "$" in text:
        return "USD"
    if "eur" in normalized or "€" in text:
        return "EUR"
    return "RUB"


def find_money_after_any_label(
    text: str,
    label_sets: tuple[ControlTotalLabelSet, ...],
    *,
    field: str,
) -> Decimal | None:
    for label_set in label_sets:
        labels = getattr(label_set, field)
        for label in labels:
            amount = find_money_after_label(text, label)
            if amount is not None:
                return amount
    return None


def find_money_after_label(text: str, label: str) -> Decimal | None:
    currency_pattern = r"(?:₽|руб|RUB|USD|EUR|\$|€)?"
    pattern = (
        rf"{re.escape(label)}\s*:?\s*{currency_pattern}\s*"
        rf"([+-]?\s*[\d\s.,]+)\s*{currency_pattern}"
    )
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if match is None:
        return None
    return parse_money_amount(match.group(1))
