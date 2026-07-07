from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from app.features.imports.presentation.field_labels import mapping_field_label


@dataclass(frozen=True)
class MappingSuggestionReasonVM:
    message: str


@dataclass(frozen=True)
class MappingSuggestionWarningVM:
    message: str


@dataclass(frozen=True)
class MappingSuggestionVM:
    title: str
    reasons: list[MappingSuggestionReasonVM]
    warnings: list[MappingSuggestionWarningVM]


def first_mapping_suggestion_from_raw(value: object) -> MappingSuggestionVM | None:
    if not isinstance(value, list) or not value:
        return None
    return mapping_suggestion_from_raw(value[0])


def mapping_suggestion_from_raw(value: object) -> MappingSuggestionVM | None:
    suggestion = _string_key_mapping(value)
    if suggestion is None:
        return None
    confidence = _float_mapping_value(suggestion, "confidence", default=0)
    return MappingSuggestionVM(
        title=f"Предложение маппинга · {int(round(confidence * 100))}%",
        reasons=_mapping_suggestion_reasons(suggestion),
        warnings=_mapping_suggestion_warnings(suggestion),
    )


def _mapping_suggestion_reasons(
    suggestion: Mapping[str, object],
) -> list[MappingSuggestionReasonVM]:
    reasons = suggestion.get("reasons")
    if not isinstance(reasons, list):
        return []
    return [
        MappingSuggestionReasonVM(_mapping_suggestion_reason_message(reason)) for reason in reasons
    ]


def _mapping_suggestion_reason_message(reason: object) -> str:
    reason_mapping = _string_key_mapping(reason)
    if reason_mapping is None or "field" not in reason_mapping:
        return str(reason)

    field_label = mapping_field_label(reason_mapping.get("field"))
    column_number = _int_mapping_value(reason_mapping, "column_index", default=0) + 1
    evidence = _string_mapping_value(reason_mapping, "evidence")

    if evidence == "header_match":
        return (
            f"{field_label}: колонка {column_number} выбрана по заголовку "
            f"«{_string_mapping_value(reason_mapping, 'header')}»."
        )
    if evidence == "date_like_values":
        return _mapping_profile_reason_message(field_label, column_number, reason_mapping, "дату")
    if evidence == "money_like_values":
        return _mapping_profile_reason_message(
            field_label,
            column_number,
            reason_mapping,
            "суммы",
        )
    if evidence == "currency_like_values":
        return _mapping_profile_reason_message(
            field_label,
            column_number,
            reason_mapping,
            "валюту",
        )
    if evidence == "description_like_values":
        return (
            f"{field_label}: колонка {column_number} содержит "
            f"{_string_mapping_value(reason_mapping, 'matched_count')}/"
            f"{_string_mapping_value(reason_mapping, 'sample_count')} текстовых значений."
        )
    return f"{field_label}: колонка {column_number}."


def _mapping_profile_reason_message(
    field_label: str,
    column_number: int,
    reason: Mapping[str, object],
    value_label: str,
) -> str:
    return (
        f"{field_label}: колонка {column_number} содержит "
        f"{_string_mapping_value(reason, 'matched_count')}/"
        f"{_string_mapping_value(reason, 'sample_count')} значений, похожих на {value_label}."
    )


def _mapping_suggestion_warnings(
    suggestion: Mapping[str, object],
) -> list[MappingSuggestionWarningVM]:
    warnings = suggestion.get("warnings")
    if not isinstance(warnings, list):
        return []
    return [
        MappingSuggestionWarningVM(_mapping_suggestion_warning_message(warning))
        for warning in warnings
    ]


def _mapping_suggestion_warning_message(warning: object) -> str:
    warning_mapping = _string_key_mapping(warning)
    if warning_mapping is None:
        return str(warning)
    code = _string_mapping_value(warning_mapping, "code")
    if code == "partial_debit_credit_columns":
        return (
            "Найдена только одна колонка списания/зачисления. Проверьте знак суммы перед импортом."
        )
    return code


def _int_mapping_value(mapping: Mapping[str, object], key: str, *, default: int) -> int:
    value = mapping.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _float_mapping_value(mapping: Mapping[str, object], key: str, *, default: float) -> float:
    value = mapping.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _string_mapping_value(mapping: Mapping[str, object], key: str) -> str:
    value = mapping.get(key)
    return "" if value is None else str(value)


def _string_key_mapping(value: object) -> Mapping[str, object] | None:
    if isinstance(value, Mapping):
        return cast(Mapping[str, object], value)
    return None
