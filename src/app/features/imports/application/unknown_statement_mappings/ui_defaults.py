from typing import Any, cast

from app.features.imports.application.unknown_statement_mappings.dto import (
    UnknownStatementMappingCommand,
)
from app.features.imports.application.unknown_statement_mappings.template_commands import (
    mapping_command_from_template,
)
from app.features.imports.application.unknown_statement_mappings.values import (
    int_value,
    optional_int_value,
)
from app.features.imports.models import ImportMappingTemplate


def default_mapping_command(
    validation: dict[str, object] | None,
    *,
    default_currency: str,
    templates: list[ImportMappingTemplate] | None = None,
) -> UnknownStatementMappingCommand:
    if templates:
        return mapping_command_from_template(templates[0])
    table = first_table_preview(validation)
    suggestion = first_mapping_suggestion(table)
    if suggestion:
        return UnknownStatementMappingCommand(
            page_number=int_value(table.get("page_number"), default=1),
            table_index=int_value(table.get("table_index"), default=0),
            operation_date_column=int_value(suggestion.get("operation_date_column"), default=0),
            posting_date_column=optional_int_value(suggestion.get("posting_date_column")),
            description_column=int_value(suggestion.get("description_column"), default=2),
            amount_column=optional_int_value(suggestion.get("amount_column")),
            currency_column=optional_int_value(suggestion.get("currency_column")),
            first_data_row=int_value(suggestion.get("first_data_row"), default=1),
            default_currency=default_currency,
            debit_amount_column=optional_int_value(suggestion.get("debit_amount_column")),
            credit_amount_column=optional_int_value(suggestion.get("credit_amount_column")),
            balance_after_column=optional_int_value(suggestion.get("balance_after_column")),
        )
    candidates = candidate_column_indexes(table)
    amount_column = candidates.get("amount")
    if (
        amount_column is None
        and candidates.get("debit_amount") is None
        and candidates.get("credit_amount") is None
    ):
        amount_column = 3
    return UnknownStatementMappingCommand(
        page_number=int_value(table.get("page_number"), default=1),
        table_index=int_value(table.get("table_index"), default=0),
        operation_date_column=candidates.get("operation_date", 0),
        posting_date_column=candidates.get("posting_date"),
        description_column=candidates.get("description", 2),
        amount_column=amount_column,
        currency_column=candidates.get("currency"),
        first_data_row=1,
        default_currency=default_currency,
        debit_amount_column=candidates.get("debit_amount"),
        credit_amount_column=candidates.get("credit_amount"),
        balance_after_column=candidates.get("balance_after"),
    )


def first_table_preview(validation: dict[str, object] | None) -> dict[str, object]:
    if validation is None:
        return {}
    previews = validation.get("table_previews")
    if not isinstance(previews, list) or not previews:
        return {}
    first = previews[0]
    return cast(dict[str, object], first) if isinstance(first, dict) else {}


def first_mapping_suggestion(table: dict[str, object]) -> dict[str, object]:
    suggestions = table.get("mapping_suggestions")
    if not isinstance(suggestions, list) or not suggestions:
        return {}
    first = suggestions[0]
    return cast(dict[str, object], first) if isinstance(first, dict) else {}


def candidate_column_indexes(table: dict[str, object]) -> dict[str, int]:
    candidates = table.get("column_candidates")
    if not isinstance(candidates, list):
        return {}
    indexes: dict[str, int] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        field = candidate.get("field")
        column_index = candidate.get("column_index")
        if isinstance(field, str) and isinstance(column_index, int):
            indexes[field] = column_index
    return indexes


def preview_table_options(validation: dict[str, object] | None) -> list[dict[str, Any]]:
    if validation is None:
        return []
    previews = validation.get("table_previews")
    if not isinstance(previews, list):
        return []
    return [cast(dict[str, Any], preview) for preview in previews if isinstance(preview, dict)]
