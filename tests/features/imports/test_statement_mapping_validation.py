from dataclasses import replace

from app.features.imports.application.unknown_statement_mappings.dto import (
    MappingControlTotalCellRef,
    StatementMappingSpec,
    UnsignedAmountDirection,
)
from app.features.imports.application.unknown_statement_mappings.validation import (
    MappingValidationCode,
    MappingValidationSeverity,
    StatementMappingValidator,
)


def test_valid_statement_mapping_has_no_issues() -> None:
    assert (
        StatementMappingValidator.validate(
            spec=mapping_spec(),
            selected_table=selected_table(),
            raw_tables=raw_tables(),
        )
        == ()
    )


def test_statement_mapping_validator_returns_all_column_issues() -> None:
    spec = replace(
        mapping_spec(),
        description_column=0,
        amount_column=5,
        debit_amount_column=2,
        first_data_row=4,
    )

    issues = StatementMappingValidator.validate(
        spec=spec,
        selected_table=selected_table(),
        raw_tables=raw_tables(),
    )

    assert [issue.code for issue in issues] == [
        MappingValidationCode.DUPLICATE_ROLES,
        MappingValidationCode.CONFLICTING_AMOUNT,
        MappingValidationCode.COLUMN_OUT_OF_RANGE,
        MappingValidationCode.FIRST_ROW_OUT_OF_RANGE,
    ]
    assert all(issue.severity is MappingValidationSeverity.ERROR for issue in issues)
    assert issues[0].fields == ("operationDateColumn", "descriptionColumn")
    assert issues[2].fields == ("amountColumn",)


def test_missing_table_does_not_report_dependent_column_errors() -> None:
    issues = StatementMappingValidator.validate(
        spec=mapping_spec(),
        selected_table=[],
        raw_tables=None,
    )

    assert len(issues) == 1
    assert issues[0].code is MappingValidationCode.TABLE_NOT_FOUND
    assert issues[0].fields == ("tableRef",)


def test_control_total_validation_returns_duplicate_and_invalid_cell_issues() -> None:
    invalid_cell = MappingControlTotalCellRef(
        page_number=1,
        table_index=0,
        row_number=0,
        column_index=0,
    )
    spec = replace(
        mapping_spec(),
        opening_balance_cell=invalid_cell,
        closing_balance_cell=invalid_cell,
    )

    issues = StatementMappingValidator.validate(
        spec=spec,
        selected_table=selected_table(),
        raw_tables=raw_tables(),
    )

    assert [issue.code for issue in issues] == [
        MappingValidationCode.DUPLICATE_CONTROL_TOTAL_CELLS,
        MappingValidationCode.CONTROL_TOTAL_CELL_INVALID,
        MappingValidationCode.CONTROL_TOTAL_CELL_INVALID,
    ]
    assert [issue.fields for issue in issues] == [
        ("openingBalanceCell", "closingBalanceCell"),
        ("openingBalanceCell",),
        ("closingBalanceCell",),
    ]


def mapping_spec() -> StatementMappingSpec:
    return StatementMappingSpec(
        page_number=1,
        table_index=0,
        operation_date_column=0,
        description_column=1,
        amount_column=2,
        currency_column=None,
        first_data_row=1,
        default_currency="RUB",
        unsigned_amount_direction=UnsignedAmountDirection.REQUIRE_SIGN,
    )


def selected_table() -> list[list[str]]:
    return [
        ["Дата", "Описание", "Сумма"],
        ["01.07.2026", "Пополнение", "+250,00"],
    ]


def raw_tables() -> list[dict[str, object]]:
    return [
        {
            "page_number": 1,
            "tables": [selected_table()],
        }
    ]
