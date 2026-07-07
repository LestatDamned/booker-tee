from collections.abc import Mapping, Sequence
from typing import cast

from app.features.imports.application.unknown_statement_mappings.dto import (
    UnknownStatementMappingCommand,
)
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


def mapping_table_options(
    table_options: Sequence[Mapping[str, object]],
    command: UnknownStatementMappingCommand,
) -> list[MappingTableOptionVM]:
    return [mapping_table_option(table, command) for table in table_options]


def mapping_table_option(
    table: Mapping[str, object],
    command: UnknownStatementMappingCommand,
) -> MappingTableOptionVM:
    page_number = int_table_value(table, "page_number", default=1)
    table_index = int_table_value(table, "table_index", default=0)
    return MappingTableOptionVM(
        value=f"{page_number}:{table_index}",
        page_label=str(page_number),
        table_label=str(table_index + 1) if table_index else None,
        is_selected=page_number == command.page_number and table_index == command.table_index,
    )


def mapping_selected_table(
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

    page_number = int_table_value(table, "page_number", default=1)
    table_index = int_table_value(table, "table_index", default=0)
    row_count = int_table_value(table, "row_count", default=0)
    column_count = int_table_value(table, "column_count", default=0)

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
        column_options=mapping_column_options(table),
        mapping_suggestion=mapping_table_suggestion(table),
        column_candidates=mapping_column_candidates(table),
        rows=mapping_table_rows(table),
    )


def mapping_table_suggestion(table: Mapping[str, object]) -> MappingSuggestionVM | None:
    suggestions = table.get("mapping_suggestions")
    if not isinstance(suggestions, list) or not suggestions:
        return None
    suggestion = string_key_mapping(suggestions[0])
    if suggestion is None:
        return None
    return mapping_suggestion(suggestion)


def mapping_suggestion(suggestion: Mapping[str, object]) -> MappingSuggestionVM:
    confidence = float_table_value(suggestion, "confidence", default=0)
    return MappingSuggestionVM(
        title=f"Предложение маппинга · {int(round(confidence * 100))}%",
        reasons=mapping_suggestion_reasons(suggestion),
        warnings=mapping_suggestion_warnings(suggestion),
    )


def mapping_suggestion_reasons(
    suggestion: Mapping[str, object],
) -> list[MappingSuggestionReasonVM]:
    reasons = suggestion.get("reasons")
    if not isinstance(reasons, list):
        return []
    return [
        MappingSuggestionReasonVM(mapping_suggestion_reason_message(reason)) for reason in reasons
    ]


def mapping_suggestion_reason_message(reason: object) -> str:
    reason_mapping = string_key_mapping(reason)
    if reason_mapping is None or "field" not in reason_mapping:
        return str(reason)

    field_label = mapping_field_label(reason_mapping.get("field"))
    column_number = int_table_value(reason_mapping, "column_index", default=0) + 1
    evidence = string_table_value(reason_mapping, "evidence")

    if evidence == "header_match":
        return (
            f"{field_label}: колонка {column_number} выбрана по заголовку "
            f"«{string_table_value(reason_mapping, 'header')}»."
        )
    if evidence == "date_like_values":
        return mapping_profile_reason_message(field_label, column_number, reason_mapping, "дату")
    if evidence == "money_like_values":
        return mapping_profile_reason_message(field_label, column_number, reason_mapping, "суммы")
    if evidence == "currency_like_values":
        return mapping_profile_reason_message(field_label, column_number, reason_mapping, "валюту")
    if evidence == "description_like_values":
        return (
            f"{field_label}: колонка {column_number} содержит "
            f"{string_table_value(reason_mapping, 'matched_count')}/"
            f"{string_table_value(reason_mapping, 'sample_count')} текстовых значений."
        )
    return f"{field_label}: колонка {column_number}."


def mapping_profile_reason_message(
    field_label: str,
    column_number: int,
    reason: Mapping[str, object],
    value_label: str,
) -> str:
    return (
        f"{field_label}: колонка {column_number} содержит "
        f"{string_table_value(reason, 'matched_count')}/"
        f"{string_table_value(reason, 'sample_count')} значений, похожих на {value_label}."
    )


def mapping_suggestion_warnings(
    suggestion: Mapping[str, object],
) -> list[MappingSuggestionWarningVM]:
    warnings = suggestion.get("warnings")
    if not isinstance(warnings, list):
        return []
    return [
        MappingSuggestionWarningVM(mapping_suggestion_warning_message(warning))
        for warning in warnings
    ]


def mapping_suggestion_warning_message(warning: object) -> str:
    warning_mapping = string_key_mapping(warning)
    if warning_mapping is None:
        return str(warning)
    code = string_table_value(warning_mapping, "code")
    if code == "partial_debit_credit_columns":
        return (
            "Найдена только одна колонка списания/зачисления. Проверьте знак суммы перед импортом."
        )
    return code


def mapping_column_candidates(table: Mapping[str, object]) -> list[MappingColumnCandidateVM]:
    candidates = table.get("column_candidates")
    if not isinstance(candidates, list):
        return []
    candidate_vms: list[MappingColumnCandidateVM] = []
    for candidate in candidates:
        candidate_mapping = string_key_mapping(candidate)
        if candidate_mapping is not None:
            candidate_vms.append(
                MappingColumnCandidateVM(mapping_column_candidate_message(candidate_mapping))
            )
    return candidate_vms


def mapping_column_candidate_message(candidate: Mapping[str, object]) -> str:
    column_number = int_table_value(candidate, "column_index", default=0) + 1
    return (
        f"{string_table_value(candidate, 'field')}: колонка {column_number} · "
        f"{string_table_value(candidate, 'header')}"
    )


def mapping_table_rows(table: Mapping[str, object]) -> list[MappingSelectedTableRowVM]:
    rows = table.get("rows")
    if not isinstance(rows, list):
        return []
    return [MappingSelectedTableRowVM(cells=mapping_table_row_cells(row)) for row in rows]


def mapping_table_row_cells(row: object) -> list[str]:
    if isinstance(row, list):
        return [str(cell) for cell in row]
    return [str(row)]


def mapping_column_options(table: Mapping[str, object]) -> list[MappingColumnOptionVM]:
    column_count = int_table_value(table, "column_count", default=0)
    return [
        MappingColumnOptionVM(
            index=index,
            label=f"{index + 1} · {mapping_column_header(table, index)}",
        )
        for index in range(column_count)
    ]


def mapping_column_header(table: Mapping[str, object], index: int) -> str:
    rows = table.get("rows")
    if isinstance(rows, list) and rows and isinstance(rows[0], list) and len(rows[0]) > index:
        return str(rows[0][index])
    return f"Колонка {index + 1}"


def int_table_value(table: Mapping[str, object], key: str, *, default: int) -> int:
    value = table.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def float_table_value(table: Mapping[str, object], key: str, *, default: float) -> float:
    value = table.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def string_table_value(table: Mapping[str, object], key: str) -> str:
    value = table.get(key)
    return "" if value is None else str(value)


def string_key_mapping(value: object) -> Mapping[str, object] | None:
    if isinstance(value, Mapping):
        return cast(Mapping[str, object], value)
    return None


def mapping_field_label(value: object) -> str:
    labels = {
        "operation_date": "дата",
        "posting_date": "дата проводки",
        "description": "описание",
        "amount": "сумма",
        "debit_amount": "списание",
        "credit_amount": "зачисление",
        "currency": "валюта",
        "balance_after": "остаток после операции",
    }
    field = "" if value is None else str(value)
    return labels.get(field, field)
