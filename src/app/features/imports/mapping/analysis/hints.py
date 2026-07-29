import re
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.features.imports.parsers.support.normalization import parse_money_amount
from app.features.imports.statements.dto import StatementControlTotals

DEFAULT_HINT_CONFIG_PATH = Path(__file__).with_name("unknown_statement_hints.json")

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
NonEmptyMarkers = Annotated[tuple[NonEmptyString, ...], Field(min_length=1)]


class StatementTypeHint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    statement_type: NonEmptyString
    markers: NonEmptyMarkers


class ControlTotalLabelSet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    opening_balance: tuple[NonEmptyString, ...] = ()
    closing_balance: tuple[NonEmptyString, ...] = ()
    total_inflow: tuple[NonEmptyString, ...] = ()
    total_outflow: tuple[NonEmptyString, ...] = ()


class BankStatementHint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    bank_name: NonEmptyString
    markers: NonEmptyMarkers
    statement_types: tuple[StatementTypeHint, ...] = ()
    control_total_labels: tuple[ControlTotalLabelSet, ...] = ()


class StatementHintConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    generic_control_total_labels: ControlTotalLabelSet
    banks: tuple[BankStatementHint, ...]


@lru_cache(maxsize=1)
def statement_hint_config() -> StatementHintConfig:
    return load_statement_hint_config(DEFAULT_HINT_CONFIG_PATH)


def load_statement_hint_config(path: Path) -> StatementHintConfig:
    return StatementHintConfig.model_validate_json(path.read_text(encoding="utf-8"))


def detect_bank_name_from_hints(text: str) -> str | None:
    normalized = normalize_hint_text(text)
    for hint in statement_hint_config().banks:
        if any(marker in normalized for marker in hint.markers):
            return hint.bank_name
    return None


def detect_statement_type_from_hints(text: str) -> str | None:
    normalized = normalize_hint_text(text)
    for hint in statement_hint_config().banks:
        for statement_type in hint.statement_types:
            if all(marker in normalized for marker in statement_type.markers):
                return statement_type.statement_type
    return None


def control_total_label_sets_for_text(text: str) -> tuple[ControlTotalLabelSet, ...]:
    normalized = normalize_hint_text(text)
    config = statement_hint_config()
    label_sets: list[ControlTotalLabelSet] = [config.generic_control_total_labels]
    for hint in config.banks:
        if any(marker in normalized for marker in hint.markers):
            label_sets.extend(hint.control_total_labels)
    return tuple(label_sets)


def normalize_hint_text(text: str) -> str:
    return " ".join(text.casefold().split())


def extract_statement_control_totals(
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
    if all(
        value is None for value in (opening_balance, closing_balance, total_inflow, total_outflow)
    ):
        return None
    return StatementControlTotals(
        currency=currency,
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        total_inflow=total_inflow,
        total_outflow=abs(total_outflow) if total_outflow is not None else None,
    )


def detect_statement_currency(text: str) -> str | None:
    normalized = text.casefold()
    if "российский рубль" in normalized or "₽" in text:
        return "RUB"
    if "usd" in normalized or "$" in text:
        return "USD"
    if "eur" in normalized or "€" in text:
        return "EUR"
    return None


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
