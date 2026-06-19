from decimal import Decimal
from typing import cast
from uuid import uuid4

from app.features.imports.application.unknown_statement_mappings.drafts import (
    mapped_rows_to_drafts,
)
from app.features.imports.application.unknown_statement_mappings.dto import (
    UnknownStatementMappingCommand,
)
from app.features.imports.application.unknown_statement_mappings.preview import (
    preview_compatible_unknown_statement_mapping,
    preview_unknown_statement_mapping,
)
from app.features.imports.application.unknown_statement_mappings.raw_tables import (
    compatible_mapping_table_count,
)
from app.features.imports.application.unknown_statement_mappings.template_commands import (
    compatible_mapping_templates,
    mapping_command_as_json,
    mapping_command_from_template,
    mapping_template_matches_raw_tables,
)
from app.features.imports.application.unknown_statement_mappings.ui_defaults import (
    default_mapping_command,
)
from app.features.imports.models import ImportMappingTemplate, RawTransactionStatus
from app.features.imports.parsing.support.normalization import parse_bank_date


def ozon_like_raw_tables() -> list[dict[str, object]]:
    return [
        {
            "page_number": 1,
            "tables": [
                [
                    [
                        "Дата операции",
                        "Документ",
                        "Назначение платежа",
                        "Сумма операции",
                        "Валюта",
                    ],
                    [
                        "12.05.2026 15:42:10",
                        "1",
                        "Оплата товаров по карте",
                        "-842,00 ₽",
                        "RUB",
                    ],
                ]
            ],
        }
    ]


def test_unknown_statement_mapping_preview_supports_split_debit_credit_columns() -> None:
    raw_tables: list[dict[str, object]] = [
        {
            "page_number": 1,
            "tables": [
                [
                    ["Дата", "Описание", "Списание", "Зачисление"],
                    ["12.05.2026", "Кафе", "500.00", ""],
                    ["13.05.2026", "Пополнение", "", "10000.00"],
                ]
            ],
        }
    ]
    command = UnknownStatementMappingCommand(
        page_number=1,
        table_index=0,
        operation_date_column=0,
        description_column=1,
        amount_column=None,
        currency_column=None,
        first_data_row=1,
        default_currency="RUB",
        debit_amount_column=2,
        credit_amount_column=3,
    )

    preview = preview_unknown_statement_mapping(raw_tables, command, max_rows=None)
    drafts = mapped_rows_to_drafts(preview.rows, command=command, account_id=uuid4())

    assert preview.valid_count == 2
    assert preview.error_count == 0
    assert [row.amount for row in preview.rows] == [Decimal("-500.00"), Decimal("10000.00")]
    assert [row.amount_raw for row in preview.rows] == [
        "debit: 500.00",
        "credit: 10000.00",
    ]
    columns = cast(dict[str, object], drafts[0].raw_payload["columns"])
    assert columns["amount"] is None
    assert columns["debit_amount"] == 2
    assert columns["credit_amount"] == 3


def test_unknown_statement_mapping_preview_warns_about_risky_column_selection() -> None:
    raw_tables: list[dict[str, object]] = [
        {
            "page_number": 1,
            "tables": [
                [
                    ["Дата", "Описание", "Сумма"],
                    ["12.05.2026", "Кафе", "-500.00"],
                ]
            ],
        }
    ]
    command = UnknownStatementMappingCommand(
        page_number=1,
        table_index=0,
        operation_date_column=0,
        description_column=0,
        amount_column=2,
        currency_column=None,
        first_data_row=1,
        default_currency="RUB",
        debit_amount_column=2,
    )

    preview = preview_unknown_statement_mapping(raw_tables, command, max_rows=None)

    assert [warning.code for warning in preview.warnings] == [
        "duplicate_column_roles",
        "amount_and_split_columns",
    ]
    assert preview.warnings[0].fields == ["operation_date", "description", "amount", "debit_amount"]


def test_unknown_statement_mapping_preview_warns_about_many_errors() -> None:
    raw_tables: list[dict[str, object]] = [
        {
            "page_number": 1,
            "tables": [
                [
                    ["Дата", "Описание", "Сумма"],
                    ["12.05.2026", "Кафе", "-500.00"],
                    ["нет даты", "Такси", "-320.00"],
                ]
            ],
        }
    ]
    command = UnknownStatementMappingCommand(
        page_number=1,
        table_index=0,
        operation_date_column=0,
        description_column=1,
        amount_column=2,
        currency_column=None,
        first_data_row=1,
        default_currency="RUB",
    )

    preview = preview_unknown_statement_mapping(raw_tables, command, max_rows=None)

    assert preview.valid_count == 1
    assert preview.error_count == 1
    assert [warning.code for warning in preview.warnings] == ["high_error_rate"]


def test_default_mapping_command_uses_split_debit_credit_candidates() -> None:
    validation: dict[str, object] = {
        "table_previews": [
            {
                "page_number": 1,
                "table_index": 0,
                "column_candidates": [
                    {"field": "operation_date", "column_index": 0},
                    {"field": "description", "column_index": 1},
                    {"field": "debit_amount", "column_index": 2},
                    {"field": "credit_amount", "column_index": 3},
                ],
            }
        ]
    }

    command = default_mapping_command(validation, default_currency="RUB")

    assert command.amount_column is None
    assert command.debit_amount_column == 2
    assert command.credit_amount_column == 3


def test_default_mapping_command_prefers_mapping_suggestion() -> None:
    validation: dict[str, object] = {
        "table_previews": [
            {
                "page_number": 2,
                "table_index": 1,
                "mapping_suggestions": [
                    {
                        "operation_date_column": 4,
                        "posting_date_column": 8,
                        "description_column": 3,
                        "amount_column": None,
                        "debit_amount_column": 5,
                        "credit_amount_column": 6,
                        "currency_column": 7,
                        "first_data_row": 2,
                        "confidence": 0.88,
                        "reasons": [],
                        "warnings": [],
                    }
                ],
                "column_candidates": [
                    {"field": "operation_date", "column_index": 0},
                    {"field": "description", "column_index": 1},
                    {"field": "amount", "column_index": 2},
                ],
            }
        ]
    }

    command = default_mapping_command(validation, default_currency="USD")

    assert command.page_number == 2
    assert command.table_index == 1
    assert command.operation_date_column == 4
    assert command.posting_date_column == 8
    assert command.description_column == 3
    assert command.amount_column is None
    assert command.debit_amount_column == 5
    assert command.credit_amount_column == 6
    assert command.currency_column == 7
    assert command.first_data_row == 2
    assert command.default_currency == "USD"


def test_unknown_statement_mapping_preview_normalizes_selected_columns() -> None:
    raw_tables: list[dict[str, object]] = [
        {
            "page_number": 1,
            "tables": [
                [
                    [
                        "Дата операции",
                        "Документ",
                        "Назначение платежа",
                        "Сумма операции",
                        "Валюта",
                    ],
                    [
                        "12.05.2026 15:42:10",
                        "1",
                        "Оплата товаров по карте",
                        "-842,00 ₽",
                        "RUB",
                    ],
                ]
            ],
        }
    ]
    command = UnknownStatementMappingCommand(
        page_number=1,
        table_index=0,
        operation_date_column=0,
        description_column=2,
        amount_column=3,
        currency_column=4,
        first_data_row=1,
        default_currency="RUB",
    )

    preview = preview_unknown_statement_mapping(raw_tables, command)

    assert preview.valid_count == 1
    assert preview.error_count == 0
    assert preview.rows[0].operation_date == parse_bank_date("12.05.2026")
    assert preview.rows[0].amount == Decimal("-842.00")
    assert preview.rows[0].currency == "RUB"
    assert preview.rows[0].description == "Оплата товаров по карте"


def test_unknown_statement_mapping_preview_normalizes_balance_after_column() -> None:
    account_id = uuid4()
    raw_tables: list[dict[str, object]] = [
        {
            "page_number": 1,
            "tables": [
                [
                    ["Дата", "Описание", "Сумма", "Остаток"],
                    ["12.05.2026", "Кафе", "-500,00 ₽", "9 500,00 ₽"],
                ]
            ],
        }
    ]
    command = UnknownStatementMappingCommand(
        page_number=1,
        table_index=0,
        operation_date_column=0,
        description_column=1,
        amount_column=2,
        currency_column=None,
        first_data_row=1,
        default_currency="RUB",
        balance_after_column=3,
    )

    preview = preview_unknown_statement_mapping(raw_tables, command, max_rows=None)
    drafts = mapped_rows_to_drafts(preview.rows, command=command, account_id=account_id)

    assert preview.valid_count == 1
    assert preview.rows[0].balance_after_raw == "9 500,00 ₽"
    assert preview.rows[0].balance_after == Decimal("9500.00")
    assert drafts[0].balance_after_raw == "9 500,00 ₽"
    assert drafts[0].balance_after == Decimal("9500.00")
    columns = cast(dict[str, object], drafts[0].raw_payload["columns"])
    assert columns["balance_after"] == 3


def test_unknown_statement_mapping_preview_normalizes_posting_date_column() -> None:
    account_id = uuid4()
    raw_tables: list[dict[str, object]] = [
        {
            "page_number": 1,
            "tables": [
                [
                    ["Дата операции", "Дата проводки", "Описание", "Сумма"],
                    ["12.05.2026", "13.05.2026", "Кафе", "-500,00 ₽"],
                ]
            ],
        }
    ]
    command = UnknownStatementMappingCommand(
        page_number=1,
        table_index=0,
        operation_date_column=0,
        description_column=2,
        amount_column=3,
        currency_column=None,
        first_data_row=1,
        default_currency="RUB",
        posting_date_column=1,
    )

    preview = preview_unknown_statement_mapping(raw_tables, command, max_rows=None)
    drafts = mapped_rows_to_drafts(preview.rows, command=command, account_id=account_id)

    assert preview.valid_count == 1
    assert preview.rows[0].posting_date_raw == "13.05.2026"
    assert preview.rows[0].posting_date == parse_bank_date("13.05.2026")
    assert drafts[0].posting_date_raw == "13.05.2026"
    assert drafts[0].posting_date == parse_bank_date("13.05.2026")
    columns = cast(dict[str, object], drafts[0].raw_payload["columns"])
    assert columns["posting_date"] == 1


def test_unknown_statement_mapping_builds_raw_transaction_drafts() -> None:
    account_id = uuid4()
    raw_tables: list[dict[str, object]] = [
        {
            "page_number": 1,
            "tables": [
                [
                    ["Дата операции", "Описание", "Сумма"],
                    ["12.05.2026", "Оплата товаров", "-842,00 ₽"],
                    ["нет даты", "Плохая строка", "-100,00 ₽"],
                ]
            ],
        }
    ]
    command = UnknownStatementMappingCommand(
        page_number=1,
        table_index=0,
        operation_date_column=0,
        description_column=1,
        amount_column=2,
        currency_column=None,
        first_data_row=1,
        default_currency="RUB",
    )
    preview = preview_unknown_statement_mapping(raw_tables, command, max_rows=None)

    drafts = mapped_rows_to_drafts(preview.rows, command=command, account_id=account_id)

    assert len(drafts) == 2
    assert drafts[0].status == RawTransactionStatus.NORMALIZED
    assert drafts[0].account_id == account_id
    assert drafts[0].operation_date == parse_bank_date("12.05.2026")
    assert drafts[0].posting_date == parse_bank_date("12.05.2026")
    assert drafts[0].amount == Decimal("-842.00")
    assert drafts[0].currency == "RUB"
    assert [draft.row_index for draft in drafts] == [0, 1]
    assert drafts[0].raw_payload["source_row_number"] == 1
    assert drafts[1].raw_payload["source_row_number"] == 2
    assert drafts[0].dedupe_hash is not None
    assert drafts[0].raw_payload["source"] == "unknown_statement_mapping"
    assert drafts[1].status == RawTransactionStatus.NEEDS_REVIEW
    assert drafts[1].normalization_error == "дата не распознана"


def test_unknown_statement_mapping_can_import_all_compatible_tables() -> None:
    account_id = uuid4()
    raw_tables: list[dict[str, object]] = [
        {
            "page_number": 1,
            "tables": [
                [
                    ["Дата операции", "Описание", "Сумма", "Валюта"],
                    ["", "", "Российские рубли", "Валюта"],
                    ["12.05.2026", "Оплата товаров", "-842,00 ₽"],
                ]
            ],
        },
        {
            "page_number": 2,
            "tables": [
                [
                    ["Дата операции", "Описание", "Сумма"],
                    ["13.05.2026", "Кафе", "-500,00 ₽"],
                ]
            ],
        },
    ]
    command = UnknownStatementMappingCommand(
        page_number=1,
        table_index=0,
        operation_date_column=0,
        description_column=1,
        amount_column=2,
        currency_column=None,
        first_data_row=1,
        default_currency="RUB",
    )

    preview = preview_compatible_unknown_statement_mapping(
        raw_tables,
        command,
        max_rows=None,
    )
    drafts = mapped_rows_to_drafts(preview.rows, command=command, account_id=account_id)

    assert compatible_mapping_table_count(raw_tables, command) == 2
    assert [row.page_number for row in preview.rows] == [1, 2]
    assert [draft.row_index for draft in drafts] == [0, 1]
    assert [draft.raw_payload["page_number"] for draft in drafts] == [1, 2]
    assert [draft.amount for draft in drafts] == [Decimal("-842.00"), Decimal("-500.00")]


def test_unknown_statement_mapping_imports_headerless_continuation_with_new_table_index() -> None:
    account_id = uuid4()
    raw_tables: list[dict[str, object]] = [
        {
            "page_number": 1,
            "tables": [
                [["Банк", "Тип"], ["Example Bank", "card"]],
                [
                    ["Дата операции", "Описание", "Сумма"],
                    ["12.05.2026", "Оплата товаров", "-842,00 ₽"],
                ],
            ],
        },
        {
            "page_number": 2,
            "tables": [
                [
                    ["13.05.2026", "Кафе", "-500,00 ₽"],
                    ["14.05.2026", "Такси", "-320,00 ₽"],
                ]
            ],
        },
    ]
    command = UnknownStatementMappingCommand(
        page_number=1,
        table_index=1,
        operation_date_column=0,
        description_column=1,
        amount_column=2,
        currency_column=None,
        first_data_row=1,
        default_currency="RUB",
    )

    preview = preview_compatible_unknown_statement_mapping(
        raw_tables,
        command,
        max_rows=None,
    )
    drafts = mapped_rows_to_drafts(preview.rows, command=command, account_id=account_id)

    assert compatible_mapping_table_count(raw_tables, command) == 2
    assert [(row.page_number, row.table_index) for row in preview.rows] == [
        (1, 1),
        (2, 0),
        (2, 0),
    ]
    assert [draft.amount for draft in drafts] == [
        Decimal("-842.00"),
        Decimal("-500.00"),
        Decimal("-320.00"),
    ]


def test_import_mapping_template_round_trips_mapping_command() -> None:
    command = UnknownStatementMappingCommand(
        page_number=2,
        table_index=1,
        operation_date_column=0,
        description_column=3,
        amount_column=4,
        currency_column=None,
        first_data_row=2,
        default_currency="RUB",
    )
    template = ImportMappingTemplate(
        workspace_id=uuid4(),
        name="Ozon card",
        bank_name="Ozon Bank",
        statement_type="card_statement",
        default_currency="RUB",
        column_mapping_json=mapping_command_as_json(command),
    )

    restored = mapping_command_from_template(template)

    assert restored == command


def test_import_mapping_template_matches_same_table_signature() -> None:
    command = UnknownStatementMappingCommand(
        page_number=1,
        table_index=0,
        operation_date_column=0,
        description_column=2,
        amount_column=3,
        currency_column=4,
        first_data_row=1,
        default_currency="RUB",
    )
    raw_tables = ozon_like_raw_tables()
    template = ImportMappingTemplate(
        workspace_id=uuid4(),
        name="Ozon card",
        bank_name="Ozon Bank",
        statement_type="card_statement",
        default_currency="RUB",
        column_mapping_json=mapping_command_as_json(command, raw_tables=raw_tables),
    )

    assert mapping_template_matches_raw_tables(template, raw_tables)
    assert compatible_mapping_templates([template], raw_tables) == [template]


def test_import_mapping_template_matches_changed_headers_with_same_profiles() -> None:
    command = UnknownStatementMappingCommand(
        page_number=1,
        table_index=0,
        operation_date_column=0,
        description_column=2,
        amount_column=3,
        currency_column=4,
        first_data_row=1,
        default_currency="RUB",
    )
    template = ImportMappingTemplate(
        workspace_id=uuid4(),
        name="Ozon card",
        bank_name="Ozon Bank",
        statement_type="card_statement",
        default_currency="RUB",
        column_mapping_json=mapping_command_as_json(command, raw_tables=ozon_like_raw_tables()),
    )
    changed_tables: list[dict[str, object]] = [
        {
            "page_number": 1,
            "tables": [
                [
                    ["Дата операции", "Документ", "Описание", "Сумма операции", "Валюта"],
                    ["12.05.2026 15:42:10", "1", "Оплата товаров", "-842,00 ₽", "RUB"],
                ]
            ],
        }
    ]

    assert mapping_template_matches_raw_tables(template, changed_tables)
    assert compatible_mapping_templates([template], changed_tables) == [template]


def test_import_mapping_template_rejects_incompatible_column_profiles() -> None:
    command = UnknownStatementMappingCommand(
        page_number=1,
        table_index=0,
        operation_date_column=0,
        description_column=2,
        amount_column=3,
        currency_column=4,
        first_data_row=1,
        default_currency="RUB",
    )
    template = ImportMappingTemplate(
        workspace_id=uuid4(),
        name="Ozon card",
        bank_name="Ozon Bank",
        statement_type="card_statement",
        default_currency="RUB",
        column_mapping_json=mapping_command_as_json(command, raw_tables=ozon_like_raw_tables()),
    )
    changed_tables: list[dict[str, object]] = [
        {
            "page_number": 1,
            "tables": [
                [
                    ["Дата операции", "Документ", "Описание", "Комментарий", "Валюта"],
                    ["12.05.2026 15:42:10", "1", "Оплата товаров", "сумма скрыта", "RUB"],
                ]
            ],
        }
    ]

    assert not mapping_template_matches_raw_tables(template, changed_tables)
    assert compatible_mapping_templates([template], changed_tables) == []


def test_default_mapping_command_prefers_saved_template() -> None:
    saved_command = UnknownStatementMappingCommand(
        page_number=3,
        table_index=2,
        operation_date_column=1,
        description_column=4,
        amount_column=5,
        currency_column=None,
        first_data_row=2,
        default_currency="RUB",
    )
    template = ImportMappingTemplate(
        workspace_id=uuid4(),
        name="Ozon card",
        bank_name="Ozon Bank",
        statement_type="card_statement",
        default_currency="RUB",
        column_mapping_json=mapping_command_as_json(saved_command),
    )
    validation: dict[str, object] = {
        "table_previews": [
            {
                "page_number": 1,
                "table_index": 0,
                "column_candidates": [
                    {"field": "operation_date", "column_index": 0},
                    {"field": "description", "column_index": 2},
                    {"field": "amount", "column_index": 3},
                ],
            }
        ]
    }

    command = default_mapping_command(
        validation,
        default_currency="RUB",
        templates=[template],
    )

    assert command == saved_command
