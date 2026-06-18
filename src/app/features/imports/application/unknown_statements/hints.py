import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import cast

DEFAULT_HINT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "unknown_statement_hints.json"


@dataclass(frozen=True)
class StatementTypeHint:
    statement_type: str
    markers: tuple[str, ...]


@dataclass(frozen=True)
class ControlTotalLabelSet:
    opening_balance: tuple[str, ...] = ()
    closing_balance: tuple[str, ...] = ()
    total_inflow: tuple[str, ...] = ()
    total_outflow: tuple[str, ...] = ()


@dataclass(frozen=True)
class BankStatementHint:
    bank_name: str
    markers: tuple[str, ...]
    statement_types: tuple[StatementTypeHint, ...] = ()
    control_total_labels: tuple[ControlTotalLabelSet, ...] = ()


@dataclass(frozen=True)
class StatementHintConfig:
    generic_control_total_labels: ControlTotalLabelSet
    statement_hints: tuple[BankStatementHint, ...]


@lru_cache(maxsize=1)
def statement_hint_config() -> StatementHintConfig:
    return load_statement_hint_config(DEFAULT_HINT_CONFIG_PATH)


def load_statement_hint_config(path: Path) -> StatementHintConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Unknown statement hint config must be a JSON object.")
    config = cast(dict[str, object], payload)
    return StatementHintConfig(
        generic_control_total_labels=control_total_label_set_from_payload(
            config.get("generic_control_total_labels")
        ),
        statement_hints=tuple(
            bank_statement_hint_from_payload(bank_payload)
            for bank_payload in list_payload(config.get("banks"))
        ),
    )


def bank_statement_hint_from_payload(payload: object) -> BankStatementHint:
    if not isinstance(payload, dict):
        raise ValueError("Bank statement hint must be a JSON object.")
    bank_payload = cast(dict[str, object], payload)
    bank_name = bank_payload.get("bank_name")
    if not isinstance(bank_name, str) or not bank_name.strip():
        raise ValueError("Bank statement hint requires bank_name.")
    return BankStatementHint(
        bank_name=bank_name,
        markers=string_tuple(bank_payload.get("markers")),
        statement_types=tuple(
            statement_type_hint_from_payload(statement_type_payload)
            for statement_type_payload in list_payload(bank_payload.get("statement_types"))
        ),
        control_total_labels=tuple(
            control_total_label_set_from_payload(label_payload)
            for label_payload in list_payload(bank_payload.get("control_total_labels"))
        ),
    )


def statement_type_hint_from_payload(payload: object) -> StatementTypeHint:
    if not isinstance(payload, dict):
        raise ValueError("Statement type hint must be a JSON object.")
    statement_payload = cast(dict[str, object], payload)
    statement_type = statement_payload.get("statement_type")
    if not isinstance(statement_type, str) or not statement_type.strip():
        raise ValueError("Statement type hint requires statement_type.")
    return StatementTypeHint(
        statement_type=statement_type,
        markers=string_tuple(statement_payload.get("markers")),
    )


def control_total_label_set_from_payload(payload: object) -> ControlTotalLabelSet:
    if payload is None:
        return ControlTotalLabelSet()
    if not isinstance(payload, dict):
        raise ValueError("Control total label set must be a JSON object.")
    label_payload = cast(dict[str, object], payload)
    return ControlTotalLabelSet(
        opening_balance=string_tuple(label_payload.get("opening_balance")),
        closing_balance=string_tuple(label_payload.get("closing_balance")),
        total_inflow=string_tuple(label_payload.get("total_inflow")),
        total_outflow=string_tuple(label_payload.get("total_outflow")),
    )


def list_payload(payload: object) -> list[object]:
    return cast(list[object], payload) if isinstance(payload, list) else []


def string_tuple(payload: object) -> tuple[str, ...]:
    if not isinstance(payload, list):
        return ()
    return tuple(item for item in payload if isinstance(item, str) and item.strip())


def detect_bank_name_from_hints(text: str) -> str | None:
    normalized = normalize_hint_text(text)
    for hint in statement_hint_config().statement_hints:
        if any(marker in normalized for marker in hint.markers):
            return hint.bank_name
    return None


def detect_statement_type_from_hints(text: str) -> str | None:
    normalized = normalize_hint_text(text)
    for hint in statement_hint_config().statement_hints:
        for statement_type in hint.statement_types:
            if all(marker in normalized for marker in statement_type.markers):
                return statement_type.statement_type
    return None


def control_total_label_sets_for_text(text: str) -> tuple[ControlTotalLabelSet, ...]:
    normalized = normalize_hint_text(text)
    config = statement_hint_config()
    matched_label_sets: list[ControlTotalLabelSet] = [config.generic_control_total_labels]
    fallback_label_sets: list[ControlTotalLabelSet] = []
    for hint in config.statement_hints:
        if any(marker in normalized for marker in hint.markers):
            matched_label_sets.extend(hint.control_total_labels)
        else:
            fallback_label_sets.extend(hint.control_total_labels)
    return tuple(matched_label_sets + fallback_label_sets)


def normalize_hint_text(text: str) -> str:
    return " ".join(text.casefold().split())
