from collections.abc import Mapping, Sequence
from typing import cast

from app.features.imports.application.unknown_statement_mappings.dto import (
    UnknownStatementMappingCommand,
)
from app.features.imports.presentation.field_labels import mapping_field_label
from app.features.imports.presentation.mapping.models import (
    MappingColumnCandidateVM,
    MappingColumnOptionVM,
    MappingSelectedTableRowVM,
    MappingSelectedTableVM,
    MappingSuggestionReasonVM,
    MappingSuggestionVM,
    MappingSuggestionWarningVM,
    MappingTableOptionVM,
)


def mapping_table_picker_options(
    table_options: Sequence[Mapping[str, object]],
    command: UnknownStatementMappingCommand,
) -> list[MappingTableOptionVM]:
    return [_mapping_table_picker_option(table, command) for table in table_options]


def _mapping_table_picker_option(
    table: Mapping[str, object],
    command: UnknownStatementMappingCommand,
) -> MappingTableOptionVM:
    page_number = _int_table_value(table, "page_number", default=1)
    table_index = _int_table_value(table, "table_index", default=0)
    return MappingTableOptionVM(
        value=f"{page_number}:{table_index}",
        page_label=str(page_number),
        table_label=str(table_index + 1) if table_index else None,
        is_selected=page_number == command.page_number and table_index == command.table_index,
    )


def mapping_selected_table_vm(
    table: Mapping[str, object],
    *,
    compatible_table_count: int,
) -> MappingSelectedTableVM:
    if not table:
        return MappingSelectedTableVM(
            title="",
            picker_meta="",
            size_meta="",
            import_scope_meta="",
            column_options=[],
            mapping_suggestion=None,
            column_candidates=[],
            rows=[],
        )

    page_number = _int_table_value(table, "page_number", default=1)
    table_index = _int_table_value(table, "table_index", default=0)
    row_count = _int_table_value(table, "row_count", default=0)
    column_count = _int_table_value(table, "column_count", default=0)

    if table.get("source_type") == "text_candidate":
        title = f"Выбранные строки из текста: страница {page_number}"
        picker_meta = f"выбрана страница {page_number} · строки из текста"
    else:
        title = f"Выбранная таблица: страница {page_number} · таблица {table_index + 1}"
        picker_meta = f"выбрана страница {page_number} · таблица {table_index + 1}"

    import_scope_meta = (
        f"импорт: {compatible_table_count} таблиц по этой схеме"
        if compatible_table_count > 1
        else "импорт: только выбранная таблица"
    )
    return MappingSelectedTableVM(
        title=title,
        picker_meta=picker_meta,
        size_meta=f"{row_count} строк · {column_count} колонок",
        import_scope_meta=import_scope_meta,
        column_options=_mapping_column_options(table),
        mapping_suggestion=_mapping_table_suggestion(table),
        column_candidates=_mapping_column_candidates(table),
        rows=_mapping_table_rows(table),
    )


def _mapping_table_suggestion(table: Mapping[str, object]) -> MappingSuggestionVM | None:
    suggestions = table.get("mapping_suggestions")
    if not isinstance(suggestions, list) or not suggestions:
        return None
    suggestion = _string_key_mapping(suggestions[0])
    if suggestion is None:
        return None
    return _mapping_suggestion(suggestion)


def _mapping_suggestion(suggestion: Mapping[str, object]) -> MappingSuggestionVM:
    confidence = _float_table_value(suggestion, "confidence", default=0)
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
    column_number = _int_table_value(reason_mapping, "column_index", default=0) + 1
    evidence = _string_table_value(reason_mapping, "evidence")

    if evidence == "header_match":
        return (
            f"{field_label}: колонка {column_number} выбрана по заголовку "
            f"«{_string_table_value(reason_mapping, 'header')}»."
        )
    if evidence == "date_like_values":
        return _mapping_profile_reason_message(field_label, column_number, reason_mapping, "дату")
    if evidence == "money_like_values":
        return _mapping_profile_reason_message(field_label, column_number, reason_mapping, "суммы")
    if evidence == "currency_like_values":
        return _mapping_profile_reason_message(field_label, column_number, reason_mapping, "валюту")
    if evidence == "description_like_values":
        return (
            f"{field_label}: колонка {column_number} содержит "
            f"{_string_table_value(reason_mapping, 'matched_count')}/"
            f"{_string_table_value(reason_mapping, 'sample_count')} текстовых значений."
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
        f"{_string_table_value(reason, 'matched_count')}/"
        f"{_string_table_value(reason, 'sample_count')} значений, похожих на {value_label}."
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
    code = _string_table_value(warning_mapping, "code")
    if code == "partial_debit_credit_columns":
        return (
            "Найдена только одна колонка списания/зачисления. Проверьте знак суммы перед импортом."
        )
    return code


def _mapping_column_candidates(table: Mapping[str, object]) -> list[MappingColumnCandidateVM]:
    candidates = table.get("column_candidates")
    if not isinstance(candidates, list):
        return []
    candidate_vms: list[MappingColumnCandidateVM] = []
    for candidate in candidates:
        candidate_mapping = _string_key_mapping(candidate)
        if candidate_mapping is not None:
            candidate_vms.append(
                MappingColumnCandidateVM(_mapping_column_candidate_message(candidate_mapping))
            )
    return candidate_vms


def _mapping_column_candidate_message(candidate: Mapping[str, object]) -> str:
    column_number = _int_table_value(candidate, "column_index", default=0) + 1
    return (
        f"{_string_table_value(candidate, 'field')}: колонка {column_number} · "
        f"{_string_table_value(candidate, 'header')}"
    )


def _mapping_table_rows(table: Mapping[str, object]) -> list[MappingSelectedTableRowVM]:
    rows = table.get("rows")
    if not isinstance(rows, list):
        return []
    return [MappingSelectedTableRowVM(cells=_mapping_table_row_cells(row)) for row in rows]


def _mapping_table_row_cells(row: object) -> list[str]:
    if isinstance(row, list):
        return [str(cell) for cell in row]
    return [str(row)]


def _mapping_column_options(table: Mapping[str, object]) -> list[MappingColumnOptionVM]:
    column_count = _int_table_value(table, "column_count", default=0)
    return [
        MappingColumnOptionVM(
            index=index,
            label=f"{index + 1} · {_mapping_column_header(table, index)}",
        )
        for index in range(column_count)
    ]


def _mapping_column_header(table: Mapping[str, object], index: int) -> str:
    rows = table.get("rows")
    if isinstance(rows, list) and rows and isinstance(rows[0], list) and len(rows[0]) > index:
        return str(rows[0][index])
    return f"Колонка {index + 1}"


def _int_table_value(table: Mapping[str, object], key: str, *, default: int) -> int:
    value = table.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _float_table_value(table: Mapping[str, object], key: str, *, default: float) -> float:
    value = table.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _string_table_value(table: Mapping[str, object], key: str) -> str:
    value = table.get(key)
    return "" if value is None else str(value)


def _string_key_mapping(value: object) -> Mapping[str, object] | None:
    if isinstance(value, Mapping):
        return cast(Mapping[str, object], value)
    return None
