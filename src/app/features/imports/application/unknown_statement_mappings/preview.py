from decimal import Decimal

from app.features.imports.application.unknown_statement_mappings.dto import (
    UnknownStatementMappedRow,
    UnknownStatementMappingCommand,
    UnknownStatementMappingPreview,
    UnknownStatementMappingWarning,
)
from app.features.imports.application.unknown_statement_mappings.raw_tables import (
    compatible_mapping_tables,
    find_raw_table,
    mapping_start_row_for_table,
)
from app.features.imports.application.unknown_statement_mappings.row_mapping import (
    map_table_rows,
)
from app.features.imports.application.unknown_statement_mappings.template_signatures import (
    mapped_field_indexes,
)

MAX_MAPPING_PREVIEW_ROWS = 20


def preview_unknown_statement_mapping(
    raw_tables: list[dict[str, object]] | None,
    command: UnknownStatementMappingCommand,
    *,
    max_rows: int | None = MAX_MAPPING_PREVIEW_ROWS,
) -> UnknownStatementMappingPreview:
    table = find_raw_table(
        raw_tables,
        page_number=command.page_number,
        table_index=command.table_index,
    )
    if table is None:
        return UnknownStatementMappingPreview(rows=[])

    rows = map_table_rows(
        table,
        page_number=command.page_number,
        table_index=command.table_index,
        start_row=command.first_data_row,
        command=command,
        max_rows=max_rows,
    )
    return UnknownStatementMappingPreview(
        rows=rows,
        warnings=mapping_warnings_for_preview(rows, command),
    )


def preview_compatible_unknown_statement_mapping(
    raw_tables: list[dict[str, object]] | None,
    command: UnknownStatementMappingCommand,
    *,
    max_rows: int | None = MAX_MAPPING_PREVIEW_ROWS,
) -> UnknownStatementMappingPreview:
    rows: list[UnknownStatementMappedRow] = []
    for table_ref in compatible_mapping_tables(raw_tables, command):
        rows.extend(
            map_table_rows(
                table_ref.rows,
                page_number=table_ref.page_number,
                table_index=table_ref.table_index,
                start_row=mapping_start_row_for_table(table_ref, command),
                command=command,
                max_rows=None if max_rows is None else max_rows - len(rows),
            )
        )
        if max_rows is not None and len(rows) >= max_rows:
            return UnknownStatementMappingPreview(
                rows=rows,
                warnings=mapping_warnings_for_preview(rows, command),
            )
    return UnknownStatementMappingPreview(
        rows=rows,
        warnings=mapping_warnings_for_preview(rows, command),
    )


def mapping_warnings_for_preview(
    rows: list[UnknownStatementMappedRow],
    command: UnknownStatementMappingCommand,
) -> list[UnknownStatementMappingWarning]:
    warnings: list[UnknownStatementMappingWarning] = []
    warnings.extend(column_selection_warnings(command))
    if not rows or not any(row.status == "valid" for row in rows):
        warnings.append(
            UnknownStatementMappingWarning(
                code="no_valid_rows",
                severity="error",
            )
        )
        return warnings

    if preview_error_ratio(rows) >= Decimal("0.25"):
        warnings.append(
            UnknownStatementMappingWarning(
                code="high_error_rate",
                severity="warning",
            )
        )
    if any("остаток:" in row.error for row in rows):
        warnings.append(
            UnknownStatementMappingWarning(
                code="balance_after_parse_errors",
                severity="warning",
                fields=["balance_after"],
            )
        )
    return warnings


def column_selection_warnings(
    command: UnknownStatementMappingCommand,
) -> list[UnknownStatementMappingWarning]:
    warnings: list[UnknownStatementMappingWarning] = []
    duplicate_fields = duplicated_column_fields(command)
    if duplicate_fields:
        warnings.append(
            UnknownStatementMappingWarning(
                code="duplicate_column_roles",
                severity="warning",
                fields=duplicate_fields,
            )
        )
    if command.amount_column is not None and (
        command.debit_amount_column is not None or command.credit_amount_column is not None
    ):
        warnings.append(
            UnknownStatementMappingWarning(
                code="amount_and_split_columns",
                severity="warning",
                fields=["amount", "debit_amount", "credit_amount"],
            )
        )
    if command.amount_column is None and (
        command.debit_amount_column is None or command.credit_amount_column is None
    ):
        selected_split_fields = []
        if command.debit_amount_column is not None:
            selected_split_fields.append("debit_amount")
        if command.credit_amount_column is not None:
            selected_split_fields.append("credit_amount")
        warnings.append(
            UnknownStatementMappingWarning(
                code="partial_debit_credit_columns",
                severity="warning",
                fields=selected_split_fields,
            )
        )
    return warnings


def duplicated_column_fields(command: UnknownStatementMappingCommand) -> list[str]:
    fields_by_column: dict[int, list[str]] = {}
    for field_name, column_index in mapped_field_indexes(command):
        fields_by_column.setdefault(column_index, []).append(field_name)
    duplicated_fields: list[str] = []
    for field_names in fields_by_column.values():
        if len(field_names) > 1:
            duplicated_fields.extend(field_names)
    return duplicated_fields


def preview_error_ratio(rows: list[UnknownStatementMappedRow]) -> Decimal:
    if not rows:
        return Decimal("0")
    error_count = sum(1 for row in rows if row.status == "error")
    return Decimal(error_count) / Decimal(len(rows))
