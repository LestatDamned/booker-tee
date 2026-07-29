from dataclasses import replace
from decimal import Decimal
from typing import cast

from app.features.imports.mapping.control_totals import (
    MappingControlTotalKind,
    automatic_control_total_cell,
    detect_control_total_candidates,
    resolve_mapping_control_totals,
)
from app.features.imports.mapping.dto import (
    StatementMappingSpec,
    UnsignedAmountDirection,
)
from app.features.imports.mapping.engine import (
    StatementMappingEngine,
)


def test_detects_exact_balance_rows_and_excludes_them_from_transactions() -> None:
    raw_tables = statement_tables()
    candidates = detect_control_total_candidates(raw_tables)

    assert [(candidate.kind, candidate.amount) for candidate in candidates] == [
        (MappingControlTotalKind.OPENING_BALANCE, Decimal("1000.00")),
        (MappingControlTotalKind.CLOSING_BALANCE, Decimal("1250.00")),
    ]
    command = replace(
        mapping_command(),
        opening_balance_cell=automatic_control_total_cell(
            candidates,
            MappingControlTotalKind.OPENING_BALANCE,
        ),
        closing_balance_cell=automatic_control_total_cell(
            candidates,
            MappingControlTotalKind.CLOSING_BALANCE,
        ),
    )

    preview = StatementMappingEngine.apply(
        raw_tables,
        command,
        max_rows=None,
    )
    resolved = resolve_mapping_control_totals(raw_tables, command)

    assert preview.valid_count == 1
    assert preview.error_count == 0
    assert preview.rows[0].description == "Пополнение"
    assert [total.amount for total in resolved] == [
        Decimal("1000.00"),
        Decimal("1250.00"),
    ]


def test_ambiguous_balance_candidates_are_not_applied_automatically() -> None:
    raw_tables = statement_tables()
    tables = cast(list[list[list[str]]], raw_tables[0]["tables"])
    first_table = tables[0]
    first_table.append(["", "Остаток на конец периода", "1300,00"])

    candidates = detect_control_total_candidates(raw_tables)

    assert (
        automatic_control_total_cell(
            candidates,
            MappingControlTotalKind.CLOSING_BALANCE,
        )
        is None
    )


def statement_tables() -> list[dict[str, object]]:
    return [
        {
            "page_number": 1,
            "tables": [
                [
                    ["Дата", "Описание", "Сумма"],
                    ["", "Входящий остаток", "1 000,00 ₽"],
                    ["01.07.2026", "Пополнение", "+250,00"],
                    ["", "Исходящий остаток", "1 250,00 ₽"],
                ]
            ],
        }
    ]


def mapping_command() -> StatementMappingSpec:
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
