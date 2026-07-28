from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

DEFAULT_HINT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "unknown_statement_hints.json"

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
