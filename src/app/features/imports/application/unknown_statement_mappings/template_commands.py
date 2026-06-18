from typing import cast

from app.features.imports.application.unknown_statement_mappings.dto import (
    UnknownStatementMappingCommand,
)
from app.features.imports.application.unknown_statement_mappings.template_signatures import (
    table_signature_for_mapping,
    table_signatures_match,
)
from app.features.imports.application.unknown_statement_mappings.values import (
    int_value,
    optional_int_value,
)
from app.features.imports.errors import UnknownStatementMappingError
from app.features.imports.models import ImportMappingTemplate


def compatible_mapping_templates(
    templates: list[ImportMappingTemplate],
    raw_tables: list[dict[str, object]] | None,
) -> list[ImportMappingTemplate]:
    return [
        template
        for template in templates
        if mapping_template_matches_raw_tables(template, raw_tables)
    ]


def select_compatible_mapping_template(
    templates: list[ImportMappingTemplate],
    raw_tables: list[dict[str, object]] | None,
) -> ImportMappingTemplate | None:
    compatible_templates = compatible_mapping_templates(templates, raw_tables)
    return compatible_templates[0] if compatible_templates else None


def mapping_command_as_json(
    command: UnknownStatementMappingCommand,
    *,
    raw_tables: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "page_number": command.page_number,
        "table_index": command.table_index,
        "operation_date_column": command.operation_date_column,
        "posting_date_column": command.posting_date_column,
        "description_column": command.description_column,
        "amount_column": command.amount_column,
        "debit_amount_column": command.debit_amount_column,
        "credit_amount_column": command.credit_amount_column,
        "balance_after_column": command.balance_after_column,
        "currency_column": command.currency_column,
        "first_data_row": command.first_data_row,
        "default_currency": command.default_currency,
    }
    signature = table_signature_for_mapping(raw_tables, command)
    if signature is not None:
        payload["table_signature"] = signature
    return payload


def mapping_template_matches_raw_tables(
    template: ImportMappingTemplate,
    raw_tables: list[dict[str, object]] | None,
) -> bool:
    expected_signature = template.column_mapping_json.get("table_signature")
    if not isinstance(expected_signature, dict):
        return False
    expected_signature = cast(dict[str, object], expected_signature)
    command = mapping_command_from_template(template)
    actual_signature = table_signature_for_mapping(
        raw_tables,
        command,
    )
    if actual_signature is None:
        return False
    return table_signatures_match(
        expected_signature,
        actual_signature,
        command=command,
    )


def mapping_command_from_template(
    template: ImportMappingTemplate,
) -> UnknownStatementMappingCommand:
    mapping = template.column_mapping_json
    return UnknownStatementMappingCommand(
        page_number=int_value(mapping.get("page_number"), default=1),
        table_index=int_value(mapping.get("table_index"), default=0),
        operation_date_column=int_value(mapping.get("operation_date_column"), default=0),
        posting_date_column=optional_int_value(mapping.get("posting_date_column")),
        description_column=int_value(mapping.get("description_column"), default=2),
        amount_column=optional_int_value(mapping.get("amount_column")),
        currency_column=optional_int_value(mapping.get("currency_column")),
        first_data_row=int_value(mapping.get("first_data_row"), default=1),
        default_currency=str(mapping.get("default_currency") or template.default_currency),
        debit_amount_column=optional_int_value(mapping.get("debit_amount_column")),
        credit_amount_column=optional_int_value(mapping.get("credit_amount_column")),
        balance_after_column=optional_int_value(mapping.get("balance_after_column")),
    )


def clean_template_name(value: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned:
        raise UnknownStatementMappingError("Template name is required.")
    return cleaned[:255]
