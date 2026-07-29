from dataclasses import dataclass
from enum import StrEnum

from app.features.imports.mapping.control_totals import (
    resolve_control_total_cell,
)
from app.features.imports.mapping.dto import (
    MappingControlTotalKind,
    StatementMappingSpec,
)


class MappingValidationCode(StrEnum):
    TABLE_NOT_FOUND = "mapping_table_not_found"
    DUPLICATE_ROLES = "duplicate_mapping_roles"
    CONFLICTING_AMOUNT = "conflicting_amount_mapping"
    INCOMPLETE_AMOUNT = "incomplete_amount_mapping"
    COLUMN_OUT_OF_RANGE = "mapping_column_out_of_range"
    FIRST_ROW_OUT_OF_RANGE = "mapping_first_row_out_of_range"
    DUPLICATE_CONTROL_TOTAL_CELLS = "duplicate_control_total_cells"
    CONTROL_TOTAL_CELL_INVALID = "control_total_cell_invalid"


class MappingValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class MappingValidationIssue:
    code: MappingValidationCode
    severity: MappingValidationSeverity
    message: str
    fields: tuple[str, ...]


class MappingCommandValidationError(ValueError):
    def __init__(self, issues: tuple[MappingValidationIssue, ...]) -> None:
        if not issues:
            raise ValueError("Mapping validation error requires at least one issue.")
        self.issues = issues
        super().__init__("; ".join(issue.message for issue in issues))


class StatementMappingValidator:
    @staticmethod
    def validate(
        *,
        spec: StatementMappingSpec,
        selected_table: list[list[str]],
        raw_tables: list[dict[str, object]] | None,
    ) -> tuple[MappingValidationIssue, ...]:
        if not selected_table:
            return (
                _error(
                    MappingValidationCode.TABLE_NOT_FOUND,
                    "Выбранная таблица не найдена.",
                    ("tableRef",),
                ),
            )

        issues = [
            *_column_mapping_issues(spec, selected_table),
            *_control_total_issues(spec, raw_tables),
        ]
        return tuple(issues)


def raise_for_mapping_validation_issues(
    issues: tuple[MappingValidationIssue, ...],
) -> None:
    blocking_issues = tuple(
        issue for issue in issues if issue.severity is MappingValidationSeverity.ERROR
    )
    if blocking_issues:
        raise MappingCommandValidationError(blocking_issues)


def _column_mapping_issues(
    spec: StatementMappingSpec,
    selected_table: list[list[str]],
) -> tuple[MappingValidationIssue, ...]:
    issues: list[MappingValidationIssue] = []
    fields = _selected_column_fields(spec)
    duplicates = _duplicate_fields(fields)
    if duplicates:
        issues.append(
            _error(
                MappingValidationCode.DUPLICATE_ROLES,
                "Одна колонка не может использоваться для нескольких ролей.",
                duplicates,
            )
        )
    if spec.amount_column is not None and (
        spec.debit_amount_column is not None or spec.credit_amount_column is not None
    ):
        issues.append(
            _error(
                MappingValidationCode.CONFLICTING_AMOUNT,
                "Выберите единую сумму или отдельные списание и зачисление.",
                ("amountColumn", "debitAmountColumn", "creditAmountColumn"),
            )
        )
    if spec.amount_column is None and (
        spec.debit_amount_column is None or spec.credit_amount_column is None
    ):
        issues.append(
            _error(
                MappingValidationCode.INCOMPLETE_AMOUNT,
                "Укажите колонку суммы либо обе колонки списания и зачисления.",
                ("amountColumn", "debitAmountColumn", "creditAmountColumn"),
            )
        )
    max_column_count = max((len(row) for row in selected_table), default=0)
    out_of_range = tuple(field for field, index in fields if index >= max_column_count)
    if out_of_range:
        issues.append(
            _error(
                MappingValidationCode.COLUMN_OUT_OF_RANGE,
                "Выбранной колонки нет в исходной таблице.",
                out_of_range,
            )
        )
    if spec.first_data_row >= len(selected_table):
        issues.append(
            _error(
                MappingValidationCode.FIRST_ROW_OUT_OF_RANGE,
                "Первая строка данных находится за пределами таблицы.",
                ("firstDataRowNumber",),
            )
        )
    return tuple(issues)


def _control_total_issues(
    spec: StatementMappingSpec,
    raw_tables: list[dict[str, object]] | None,
) -> tuple[MappingValidationIssue, ...]:
    selected = (
        (
            "openingBalanceCell",
            MappingControlTotalKind.OPENING_BALANCE,
            spec.opening_balance_cell,
        ),
        (
            "closingBalanceCell",
            MappingControlTotalKind.CLOSING_BALANCE,
            spec.closing_balance_cell,
        ),
    )
    issues: list[MappingValidationIssue] = []
    selected_cells = [cell for _, _, cell in selected if cell is not None]
    if len(set(selected_cells)) != len(selected_cells):
        issues.append(
            _error(
                MappingValidationCode.DUPLICATE_CONTROL_TOTAL_CELLS,
                "Начальный и конечный остатки должны ссылаться на разные ячейки.",
                tuple(field for field, _, cell in selected if cell is not None),
            )
        )
    for field, kind, cell in selected:
        if (
            cell is not None
            and resolve_control_total_cell(
                raw_tables,
                kind=kind,
                cell=cell,
            )
            is None
        ):
            issues.append(
                _error(
                    MappingValidationCode.CONTROL_TOTAL_CELL_INVALID,
                    "В выбранной ячейке не удалось распознать денежную сумму.",
                    (field,),
                )
            )
    return tuple(issues)


def _selected_column_fields(
    spec: StatementMappingSpec,
) -> tuple[tuple[str, int], ...]:
    values = (
        ("operationDateColumn", spec.operation_date_column),
        ("postingDateColumn", spec.posting_date_column),
        ("descriptionColumn", spec.description_column),
        ("amountColumn", spec.amount_column),
        ("debitAmountColumn", spec.debit_amount_column),
        ("creditAmountColumn", spec.credit_amount_column),
        ("currencyColumn", spec.currency_column),
        ("balanceAfterColumn", spec.balance_after_column),
    )
    return tuple((field, index) for field, index in values if index is not None)


def _duplicate_fields(fields: tuple[tuple[str, int], ...]) -> tuple[str, ...]:
    fields_by_index: dict[int, list[str]] = {}
    for field, index in fields:
        fields_by_index.setdefault(index, []).append(field)
    return tuple(
        field
        for grouped_fields in fields_by_index.values()
        if len(grouped_fields) > 1
        for field in grouped_fields
    )


def _error(
    code: MappingValidationCode,
    message: str,
    fields: tuple[str, ...],
) -> MappingValidationIssue:
    return MappingValidationIssue(
        code=code,
        severity=MappingValidationSeverity.ERROR,
        message=message,
        fields=fields,
    )
