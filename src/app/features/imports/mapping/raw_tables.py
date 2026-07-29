from dataclasses import dataclass
from typing import Any, cast

from app.features.imports.application.unknown_statement_mappings.values import int_value
from app.features.imports.mapping.dto import (
    StatementMappingSpec,
)
from app.features.imports.mapping.rows import (
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
    spec: StatementMappingSpec,
) -> list[RawTableRef]:
    return [
        table_ref
        for table_ref in iter_raw_tables(raw_tables)
        if mapping_can_apply_to_table(table_ref, spec)
        or mapping_can_apply_to_continuation_table(table_ref, spec)
    ]


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
    spec: StatementMappingSpec,
) -> bool:
    if table_ref.table_index != spec.table_index:
        return False
    if not table_has_required_columns(table_ref.rows, spec):
        return False
    return any(
        row.status == "valid"
        for row in map_table_rows(
            table_ref.rows,
            page_number=table_ref.page_number,
            table_index=table_ref.table_index,
            start_row=mapping_start_row_for_table(table_ref, spec),
            spec=spec,
            max_rows=None,
        )
    )


def mapping_can_apply_to_continuation_table(
    table_ref: RawTableRef,
    spec: StatementMappingSpec,
) -> bool:
    if not table_is_after_selected_page(table_ref, spec):
        return False
    if table_ref.table_index == spec.table_index:
        return False
    if not table_has_required_columns(table_ref.rows, spec):
        return False
    return any(
        row.status == "valid"
        for row in map_table_rows(
            table_ref.rows,
            page_number=table_ref.page_number,
            table_index=table_ref.table_index,
            start_row=0,
            spec=spec,
            max_rows=None,
        )
    )


def table_is_after_selected_page(
    table_ref: RawTableRef,
    spec: StatementMappingSpec,
) -> bool:
    return table_ref.page_number > spec.page_number


def table_has_required_columns(
    table: list[list[str]],
    spec: StatementMappingSpec,
) -> bool:
    required_indexes = [
        spec.operation_date_column,
        spec.description_column,
    ]
    if spec.posting_date_column is not None:
        required_indexes.append(spec.posting_date_column)
    if spec.amount_column is not None:
        required_indexes.append(spec.amount_column)
    else:
        if spec.debit_amount_column is not None:
            required_indexes.append(spec.debit_amount_column)
        if spec.credit_amount_column is not None:
            required_indexes.append(spec.credit_amount_column)
    if spec.currency_column is not None:
        required_indexes.append(spec.currency_column)
    if spec.balance_after_column is not None:
        required_indexes.append(spec.balance_after_column)
    required_column_count = max(required_indexes, default=-1) + 1
    return any(len(row) >= required_column_count for row in table)


def mapping_start_row_for_table(
    table_ref: RawTableRef,
    spec: StatementMappingSpec,
) -> int:
    if table_ref.page_number == spec.page_number and table_ref.table_index == spec.table_index:
        return spec.first_data_row
    return 0


def normalize_raw_table(table: list[Any]) -> list[list[str]]:
    return [normalize_raw_row(cast(list[Any], row)) for row in table if isinstance(row, list)]


def normalize_raw_row(row: list[Any]) -> list[str]:
    return [str(cell).strip() if cell is not None else "" for cell in row]
