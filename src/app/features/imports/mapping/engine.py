from decimal import Decimal

from app.features.imports.mapping.dto import (
    MappedStatementRow,
    StatementMappingResult,
    StatementMappingSpec,
    UnknownStatementMappingWarning,
    UnsignedAmountDirection,
)
from app.features.imports.mapping.raw_tables import (
    compatible_mapping_tables,
    mapping_start_row_for_table,
)
from app.features.imports.mapping.rows import (
    explicit_amount_direction,
    map_table_rows,
)
from app.features.imports.mapping.templates import mapped_field_indexes

DEFAULT_MAPPING_ROW_LIMIT = 20


class StatementMappingEngine:
    @staticmethod
    def apply(
        raw_tables: list[dict[str, object]] | None,
        spec: StatementMappingSpec,
        *,
        max_rows: int | None = DEFAULT_MAPPING_ROW_LIMIT,
    ) -> StatementMappingResult:
        rows: list[MappedStatementRow] = []
        for table_ref in compatible_mapping_tables(raw_tables, spec):
            rows.extend(
                map_table_rows(
                    table_ref.rows,
                    page_number=table_ref.page_number,
                    table_index=table_ref.table_index,
                    start_row=mapping_start_row_for_table(table_ref, spec),
                    spec=spec,
                    max_rows=None if max_rows is None else max_rows - len(rows),
                )
            )
            if max_rows is not None and len(rows) >= max_rows:
                return StatementMappingResult(
                    rows=rows,
                    warnings=mapping_warnings(rows, spec),
                )
        return StatementMappingResult(
            rows=rows,
            warnings=mapping_warnings(rows, spec),
        )


def mapping_warnings(
    rows: list[MappedStatementRow],
    spec: StatementMappingSpec,
) -> list[UnknownStatementMappingWarning]:
    warnings: list[UnknownStatementMappingWarning] = []
    warnings.extend(column_selection_warnings(spec))
    unsigned_amount_count = unsigned_amount_error_count(rows, spec)
    if unsigned_amount_count:
        warnings.append(
            UnknownStatementMappingWarning(
                code="unsigned_amount_direction_required",
                severity="warning",
                fields=["unsigned_amount_direction"],
                affected_row_count=unsigned_amount_count,
            )
        )
    if not rows or not any(row.status == "valid" for row in rows):
        warnings.append(
            UnknownStatementMappingWarning(
                code="no_valid_rows",
                severity="error",
            )
        )
        return warnings

    if mapping_error_ratio(rows) >= Decimal("0.25"):
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


def unsigned_amount_error_count(
    rows: list[MappedStatementRow],
    spec: StatementMappingSpec,
) -> int:
    if (
        spec.amount_column is None
        or spec.unsigned_amount_direction is not UnsignedAmountDirection.REQUIRE_SIGN
    ):
        return 0
    return sum(
        1
        for row in rows
        if row.amount is None
        and row.amount_raw.strip()
        and explicit_amount_direction(row.amount_raw) is None
    )


def column_selection_warnings(
    spec: StatementMappingSpec,
) -> list[UnknownStatementMappingWarning]:
    warnings: list[UnknownStatementMappingWarning] = []
    duplicate_fields = duplicated_column_fields(spec)
    if duplicate_fields:
        warnings.append(
            UnknownStatementMappingWarning(
                code="duplicate_column_roles",
                severity="warning",
                fields=duplicate_fields,
            )
        )
    if spec.amount_column is not None and (
        spec.debit_amount_column is not None or spec.credit_amount_column is not None
    ):
        warnings.append(
            UnknownStatementMappingWarning(
                code="amount_and_split_columns",
                severity="warning",
                fields=["amount", "debit_amount", "credit_amount"],
            )
        )
    if spec.amount_column is None and (
        spec.debit_amount_column is None or spec.credit_amount_column is None
    ):
        selected_split_fields = []
        if spec.debit_amount_column is not None:
            selected_split_fields.append("debit_amount")
        if spec.credit_amount_column is not None:
            selected_split_fields.append("credit_amount")
        warnings.append(
            UnknownStatementMappingWarning(
                code="partial_debit_credit_columns",
                severity="warning",
                fields=selected_split_fields,
            )
        )
    return warnings


def duplicated_column_fields(spec: StatementMappingSpec) -> list[str]:
    fields_by_column: dict[int, list[str]] = {}
    for field_name, column_index in mapped_field_indexes(spec):
        fields_by_column.setdefault(column_index, []).append(field_name)
    duplicated_fields: list[str] = []
    for field_names in fields_by_column.values():
        if len(field_names) > 1:
            duplicated_fields.extend(field_names)
    return duplicated_fields


def mapping_error_ratio(rows: list[MappedStatementRow]) -> Decimal:
    if not rows:
        return Decimal("0")
    error_count = sum(1 for row in rows if row.status == "error")
    return Decimal(error_count) / Decimal(len(rows))
