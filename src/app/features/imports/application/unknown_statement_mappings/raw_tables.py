from dataclasses import dataclass
from typing import Any, cast

from app.features.imports.application.unknown_statement_mappings.dto import (
    UnknownStatementMappingCommand,
)
from app.features.imports.application.unknown_statement_mappings.row_mapping import (
    map_table_rows,
)


@dataclass(frozen=True)
class RawTableRef:
    page_number: int
    table_index: int
    rows: list[list[str]]


def find_raw_table(
    raw_tables: list[dict[str, object]] | None,
    *,
    page_number: int,
    table_index: int,
) -> list[list[str]]:
    if raw_tables is None:
        return []
    for page_tables in raw_tables:
        if page_tables.get("page_number") != page_number:
            continue
        tables = page_tables.get("tables")
        if not isinstance(tables, list) or table_index >= len(tables):
            return []
        table = tables[table_index]
        if not isinstance(table, list):
            return []
        return normalize_raw_table(cast(list[Any], table))
    return []


def compatible_mapping_tables(
    raw_tables: list[dict[str, object]] | None,
    command: UnknownStatementMappingCommand,
) -> list[RawTableRef]:
    return [
        table_ref
        for table_ref in iter_raw_tables(raw_tables)
        if mapping_can_apply_to_table(table_ref, command)
        or mapping_can_apply_to_continuation_table(table_ref, command)
    ]


def compatible_mapping_table_count(
    raw_tables: list[dict[str, object]] | None,
    command: UnknownStatementMappingCommand,
) -> int:
    return len(compatible_mapping_tables(raw_tables, command))


def iter_raw_tables(raw_tables: list[dict[str, object]] | None) -> list[RawTableRef]:
    if raw_tables is None:
        return []
    table_refs: list[RawTableRef] = []
    for page_tables in raw_tables:
        page_number = int_value(page_tables.get("page_number"), default=0)
        tables = page_tables.get("tables")
        if page_number < 1 or not isinstance(tables, list):
            continue
        for table_index, table in enumerate(tables):
            if isinstance(table, list):
                table_refs.append(
                    RawTableRef(
                        page_number=page_number,
                        table_index=table_index,
                        rows=normalize_raw_table(cast(list[Any], table)),
                    )
                )
    return table_refs


def mapping_can_apply_to_table(
    table_ref: RawTableRef,
    command: UnknownStatementMappingCommand,
) -> bool:
    if table_ref.table_index != command.table_index:
        return False
    if not table_has_required_columns(table_ref.rows, command):
        return False
    return any(
        row.status == "valid"
        for row in map_table_rows(
            table_ref.rows,
            page_number=table_ref.page_number,
            table_index=table_ref.table_index,
            start_row=mapping_start_row_for_table(table_ref, command),
            command=command,
            max_rows=None,
        )
    )


def mapping_can_apply_to_continuation_table(
    table_ref: RawTableRef,
    command: UnknownStatementMappingCommand,
) -> bool:
    if not table_is_after_selected_page(table_ref, command):
        return False
    if table_ref.table_index == command.table_index:
        return False
    if not table_has_required_columns(table_ref.rows, command):
        return False
    return any(
        row.status == "valid"
        for row in map_table_rows(
            table_ref.rows,
            page_number=table_ref.page_number,
            table_index=table_ref.table_index,
            start_row=0,
            command=command,
            max_rows=None,
        )
    )


def table_is_after_selected_page(
    table_ref: RawTableRef,
    command: UnknownStatementMappingCommand,
) -> bool:
    return table_ref.page_number > command.page_number


def table_has_required_columns(
    table: list[list[str]],
    command: UnknownStatementMappingCommand,
) -> bool:
    required_indexes = [
        command.operation_date_column,
        command.description_column,
    ]
    if command.posting_date_column is not None:
        required_indexes.append(command.posting_date_column)
    if command.amount_column is not None:
        required_indexes.append(command.amount_column)
    else:
        if command.debit_amount_column is not None:
            required_indexes.append(command.debit_amount_column)
        if command.credit_amount_column is not None:
            required_indexes.append(command.credit_amount_column)
    if command.currency_column is not None:
        required_indexes.append(command.currency_column)
    if command.balance_after_column is not None:
        required_indexes.append(command.balance_after_column)
    required_column_count = max(required_indexes, default=-1) + 1
    return any(len(row) >= required_column_count for row in table)


def mapping_start_row_for_table(
    table_ref: RawTableRef,
    command: UnknownStatementMappingCommand,
) -> int:
    if (
        table_ref.page_number == command.page_number
        and table_ref.table_index == command.table_index
    ):
        return command.first_data_row
    return 0


def normalize_raw_table(table: list[Any]) -> list[list[str]]:
    return [normalize_raw_row(cast(list[Any], row)) for row in table if isinstance(row, list)]


def normalize_raw_row(row: list[Any]) -> list[str]:
    return [str(cell).strip() if cell is not None else "" for cell in row]


def int_value(value: object, *, default: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return default
