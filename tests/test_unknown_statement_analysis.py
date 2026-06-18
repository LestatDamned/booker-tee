import json
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

from app.features.imports.application.unknown_statement_mappings.drafts import (
    mapped_rows_to_drafts,
)
from app.features.imports.application.unknown_statement_mappings.preview import (
    preview_compatible_unknown_statement_mapping,
    preview_unknown_statement_mapping,
)
from app.features.imports.application.unknown_statement_mappings.raw_tables import (
    compatible_mapping_table_count,
)
from app.features.imports.application.unknown_statement_mappings.ui_defaults import (
    default_mapping_command,
)
from app.features.imports.application.unknown_statements.analyzer import (
    analyze_unknown_statement,
)
from app.features.imports.application.unknown_statements.control_totals import (
    extract_unknown_statement_control_totals,
)
from app.features.imports.application.unknown_statements.hints import (
    DEFAULT_HINT_CONFIG_PATH,
    load_statement_hint_config,
)
from app.features.imports.infrastructure.extraction.pdfplumber_extractor import (
    ExtractedPdf,
    ExtractedPdfPageTables,
)
from app.features.imports.parsing.parsers.normalization import parse_bank_date


def sanitized_unknown_statement_fixture(name: str) -> ExtractedPdf:
    path = Path("tests/fixtures/unknown_statements") / name
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    text_by_page = payload.get("text_by_page")
    tables_by_page = payload.get("tables_by_page")
    metadata = payload.get("metadata")
    assert isinstance(text_by_page, list)
    assert isinstance(tables_by_page, list)
    assert isinstance(metadata, dict)
    return ExtractedPdf(
        text_by_page=[str(page_text) for page_text in text_by_page],
        tables_by_page=[
            extracted_pdf_page_tables_from_payload(page_tables)
            for page_tables in tables_by_page
            if isinstance(page_tables, dict)
        ],
        metadata=cast(dict[str, object], metadata),
    )


def extracted_pdf_page_tables_from_payload(
    payload: dict[object, object],
) -> ExtractedPdfPageTables:
    page_number = payload.get("page_number")
    tables = payload.get("tables")
    assert isinstance(page_number, int)
    assert isinstance(tables, list)
    return ExtractedPdfPageTables(
        page_number=page_number,
        tables=cast(list[list[list[str | None]]], tables),
    )


def raw_tables_from_extracted_fixture(extracted: ExtractedPdf) -> list[dict[str, object]]:
    return [
        {
            "page_number": page_tables.page_number,
            "tables": page_tables.tables,
        }
        for page_tables in extracted.tables_by_page
    ]


def test_unknown_statement_hints_load_from_config_file() -> None:
    config = load_statement_hint_config(DEFAULT_HINT_CONFIG_PATH)

    assert "Opening balance" in config.generic_control_total_labels.opening_balance
    ozon_hint = next(hint for hint in config.statement_hints if hint.bank_name == "Ozon Bank")
    assert "ozon bank" in ozon_hint.markers
    assert ozon_hint.statement_types[0].statement_type == "card_statement"
    assert "Входящий остаток" in ozon_hint.control_total_labels[0].opening_balance


def test_unknown_statement_analysis_finds_mapping_candidates() -> None:
    extracted = ExtractedPdf(
        text_by_page=[
            "\n".join(
                [
                    "ООО «ОЗОН Банк»",
                    "Справка о движении средств",
                    "Оплата товаров по карте",
                ]
            )
        ],
        tables_by_page=[
            ExtractedPdfPageTables(
                page_number=1,
                tables=[
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
            )
        ],
        metadata={},
    )

    report = analyze_unknown_statement(extracted).as_validation_report()
    previews = cast(list[dict[str, object]], report["table_previews"])
    preview = previews[0]

    assert report["status"] == "needs_mapping"
    assert report["detected_bank_name"] == "Ozon Bank"
    assert report["detected_statement_type"] == "card_statement"
    assert report["text_based"] is True
    assert report["table_count"] == 1
    assert preview["page_number"] == 1
    assert preview["row_count"] == 2
    column_candidates = cast(list[dict[str, object]], preview["column_candidates"])
    assert {
        "field": "operation_date",
        "column_index": 0,
        "header": "Дата операции",
        "confidence": 0.95,
    } in column_candidates
    assert {
        "field": "description",
        "column_index": 2,
        "header": "Назначение платежа",
        "confidence": 0.9,
    } in column_candidates
    assert {
        "field": "amount",
        "column_index": 3,
        "header": "Сумма операции",
        "confidence": 0.85,
    } in column_candidates


def test_unknown_statement_analysis_keeps_all_table_candidates() -> None:
    extracted = ExtractedPdf(
        text_by_page=["Оплата товаров по карте" for _ in range(4)],
        tables_by_page=[
            ExtractedPdfPageTables(
                page_number=page_number,
                tables=[
                    [
                        ["Дата операции", "Документ", "Назначение платежа", "Сумма операции"],
                        ["12.05.2026 15:42:10", "1", "Оплата товаров", "-842,00 ₽"],
                    ]
                ],
            )
            for page_number in range(1, 5)
        ],
        metadata={},
    )

    report = analyze_unknown_statement(extracted).as_validation_report()
    previews = cast(list[dict[str, object]], report["table_previews"])

    assert report["page_count"] == 4
    assert report["table_count"] == 4
    assert [preview["page_number"] for preview in previews] == [1, 2, 3, 4]


def test_unknown_statement_analysis_detects_english_table_with_date_not_first() -> None:
    extracted = ExtractedPdf(
        text_by_page=["Account statement"],
        tables_by_page=[
            ExtractedPdfPageTables(
                page_number=1,
                tables=[
                    [
                        ["Description", "Transaction Date", "Amount", "Currency"],
                        ["Coffee shop", "2026-05-12", "-5.50", "USD"],
                        ["Salary", "2026-05-13", "+2000.00", "USD"],
                    ]
                ],
            )
        ],
        metadata={},
    )

    report = analyze_unknown_statement(extracted).as_validation_report()
    previews = cast(list[dict[str, object]], report["table_previews"])
    column_candidates = cast(list[dict[str, object]], previews[0]["column_candidates"])

    assert report["detected_bank_name"] is None
    assert report["detected_statement_type"] is None
    assert previews[0]["page_number"] == 1
    assert {
        "field": "description",
        "column_index": 0,
        "header": "Description",
        "confidence": 0.9,
    } in column_candidates
    assert {
        "field": "operation_date",
        "column_index": 1,
        "header": "Transaction Date",
        "confidence": 0.95,
    } in column_candidates
    assert {
        "field": "amount",
        "column_index": 2,
        "header": "Amount",
        "confidence": 0.85,
    } in column_candidates


def test_unknown_statement_analysis_includes_column_profiles() -> None:
    extracted = ExtractedPdf(
        text_by_page=["Account statement"],
        tables_by_page=[
            ExtractedPdfPageTables(
                page_number=1,
                tables=[
                    [
                        ["Description", "Transaction Date", "Amount", "Currency"],
                        ["Coffee shop", "2026-05-12", "-5.50", "USD"],
                        ["Salary", "2026-05-13", "+2000.00", "USD"],
                    ]
                ],
            )
        ],
        metadata={},
    )

    report = analyze_unknown_statement(extracted).as_validation_report()
    previews = cast(list[dict[str, object]], report["table_previews"])
    profiles = cast(list[dict[str, object]], previews[0]["column_profiles"])

    assert profiles[0]["header"] == "Description"
    assert profiles[0]["description_like_count"] == 2
    assert profiles[0]["header_matches"] == ["description"]
    assert profiles[1]["header"] == "Transaction Date"
    assert profiles[1]["date_like_count"] == 2
    assert profiles[1]["header_matches"] == ["operation_date"]
    assert profiles[2]["money_like_count"] == 2
    assert profiles[3]["currency_like_count"] == 2


def test_unknown_statement_analysis_includes_mapping_suggestions() -> None:
    extracted = ExtractedPdf(
        text_by_page=["Account statement"],
        tables_by_page=[
            ExtractedPdfPageTables(
                page_number=1,
                tables=[
                    [
                        ["Description", "Transaction Date", "Amount", "Currency"],
                        ["Coffee shop", "2026-05-12", "-5.50", "USD"],
                        ["Salary", "2026-05-13", "+2000.00", "USD"],
                    ]
                ],
            )
        ],
        metadata={},
    )

    report = analyze_unknown_statement(extracted).as_validation_report()
    previews = cast(list[dict[str, object]], report["table_previews"])
    suggestions = cast(list[dict[str, object]], previews[0]["mapping_suggestions"])
    suggestion = suggestions[0]
    reasons = cast(list[dict[str, object]], suggestion["reasons"])

    assert suggestion["operation_date_column"] == 1
    assert suggestion["description_column"] == 0
    assert suggestion["amount_column"] == 2
    assert suggestion["currency_column"] == 3
    assert suggestion["first_data_row"] == 1
    assert suggestion["confidence"] == pytest.approx(0.9125)
    assert {
        "field": "operation_date",
        "column_index": 1,
        "header": "Transaction Date",
        "evidence": "header_match",
        "matched_count": None,
        "sample_count": None,
    } in reasons


def test_unknown_statement_analysis_detects_balance_after_column() -> None:
    extracted = ExtractedPdf(
        text_by_page=["Account statement"],
        tables_by_page=[
            ExtractedPdfPageTables(
                page_number=1,
                tables=[
                    [
                        ["Date", "Description", "Amount", "Currency", "Balance"],
                        ["2026-05-12", "Coffee shop", "-5.50", "USD", "994.50"],
                        ["2026-05-13", "Salary", "+2000.00", "USD", "2994.50"],
                    ]
                ],
            )
        ],
        metadata={},
    )

    report = analyze_unknown_statement(extracted).as_validation_report()
    previews = cast(list[dict[str, object]], report["table_previews"])
    column_candidates = cast(list[dict[str, object]], previews[0]["column_candidates"])
    suggestions = cast(list[dict[str, object]], previews[0]["mapping_suggestions"])
    suggestion = suggestions[0]
    reasons = cast(list[dict[str, object]], suggestion["reasons"])

    assert {
        "field": "balance_after",
        "column_index": 4,
        "header": "Balance",
        "confidence": 0.85,
    } in column_candidates
    assert suggestion["balance_after_column"] == 4
    assert {
        "field": "balance_after",
        "column_index": 4,
        "header": "Balance",
        "evidence": "header_match",
        "matched_count": None,
        "sample_count": None,
    } in reasons


def test_unknown_statement_analysis_detects_posting_date_column() -> None:
    extracted = ExtractedPdf(
        text_by_page=["Account statement"],
        tables_by_page=[
            ExtractedPdfPageTables(
                page_number=1,
                tables=[
                    [
                        ["Transaction Date", "Posting Date", "Description", "Amount"],
                        ["2026-05-12", "2026-05-13", "Coffee shop", "-5.50"],
                        ["2026-05-14", "2026-05-15", "Salary", "+2000.00"],
                    ]
                ],
            )
        ],
        metadata={},
    )

    report = analyze_unknown_statement(extracted).as_validation_report()
    previews = cast(list[dict[str, object]], report["table_previews"])
    column_candidates = cast(list[dict[str, object]], previews[0]["column_candidates"])
    suggestions = cast(list[dict[str, object]], previews[0]["mapping_suggestions"])
    suggestion = suggestions[0]
    reasons = cast(list[dict[str, object]], suggestion["reasons"])

    assert {
        "field": "posting_date",
        "column_index": 1,
        "header": "Posting Date",
        "confidence": 0.9,
    } in column_candidates
    assert suggestion["operation_date_column"] == 0
    assert suggestion["posting_date_column"] == 1
    assert {
        "field": "posting_date",
        "column_index": 1,
        "header": "Posting Date",
        "evidence": "header_match",
        "matched_count": None,
        "sample_count": None,
    } in reasons


def test_unknown_statement_analysis_uses_structured_mapping_warnings() -> None:
    extracted = ExtractedPdf(
        text_by_page=["Account statement"],
        tables_by_page=[
            ExtractedPdfPageTables(
                page_number=1,
                tables=[
                    [
                        ["Date", "Description", "Debit"],
                        ["2026-05-12", "Coffee shop", "5.50"],
                        ["2026-05-13", "Groceries", "20.00"],
                    ]
                ],
            )
        ],
        metadata={},
    )

    report = analyze_unknown_statement(extracted).as_validation_report()
    previews = cast(list[dict[str, object]], report["table_previews"])
    suggestions = cast(list[dict[str, object]], previews[0]["mapping_suggestions"])
    warnings = cast(list[dict[str, object]], suggestions[0]["warnings"])

    assert warnings == [
        {
            "code": "partial_debit_credit_columns",
            "fields": ["debit_amount"],
        }
    ]


def test_unknown_statement_analysis_suggests_mapping_for_table_without_headers() -> None:
    extracted = ExtractedPdf(
        text_by_page=["Account statement"],
        tables_by_page=[
            ExtractedPdfPageTables(
                page_number=1,
                tables=[
                    [
                        ["2026-05-12", "Coffee shop", "-5.50", "USD"],
                        ["2026-05-13", "Salary", "+2000.00", "USD"],
                        ["2026-05-14", "Groceries", "-42.10", "USD"],
                    ]
                ],
            )
        ],
        metadata={},
    )

    report = analyze_unknown_statement(extracted).as_validation_report()
    previews = cast(list[dict[str, object]], report["table_previews"])
    preview = previews[0]
    profiles = cast(list[dict[str, object]], preview["column_profiles"])
    suggestions = cast(list[dict[str, object]], preview["mapping_suggestions"])
    suggestion = suggestions[0]
    reasons = cast(list[dict[str, object]], suggestion["reasons"])

    assert preview["rows"] == [
        ["2026-05-12", "Coffee shop", "-5.50", "USD"],
        ["2026-05-13", "Salary", "+2000.00", "USD"],
        ["2026-05-14", "Groceries", "-42.10", "USD"],
    ]
    assert profiles[0]["header"] == "column 1"
    assert profiles[0]["header_matches"] == []
    assert suggestion["operation_date_column"] == 0
    assert suggestion["description_column"] == 1
    assert suggestion["amount_column"] == 2
    assert suggestion["currency_column"] == 3
    assert suggestion["first_data_row"] == 0
    assert suggestion["confidence"] == pytest.approx(0.85)
    assert suggestion["warnings"] == []
    assert {
        "field": "operation_date",
        "column_index": 0,
        "header": "column 1",
        "evidence": "date_like_values",
        "matched_count": 3,
        "sample_count": 3,
    } in reasons


def test_unknown_statement_analysis_does_not_treat_transaction_text_as_header() -> None:
    long_description = (
        "Оплата товаров по карте 3977 сумма 390.00 RUB в MERCHANT EXAMPLE CITY RU "
        "дата 2026-05-30 время 18:16:34"
    )
    extracted = ExtractedPdf(
        text_by_page=["Account statement"],
        tables_by_page=[
            ExtractedPdfPageTables(
                page_number=1,
                tables=[
                    [
                        [
                            "2026-05-30",
                            "10853995013",
                            long_description,
                            "-390.00",
                            "-390.00",
                        ],
                        [
                            "2026-05-30",
                            "1084543089",
                            "Coffee shop date 2026-05-30 amount 385.87",
                            "-385.87",
                            "-385.87",
                        ],
                    ]
                ],
            )
        ],
        metadata={},
    )

    report = analyze_unknown_statement(extracted).as_validation_report()
    previews = cast(list[dict[str, object]], report["table_previews"])
    preview = previews[0]
    profiles = cast(list[dict[str, object]], preview["column_profiles"])
    candidates = cast(list[dict[str, object]], preview["column_candidates"])
    rows = cast(list[list[str]], preview["rows"])

    assert rows[0][2] == long_description
    assert profiles[2]["header"] == "column 3"
    assert profiles[2]["header_matches"] == []
    assert profiles[2]["money_like_count"] == 0
    assert profiles[2]["description_like_count"] == 2
    assert {
        "field": "operation_date",
        "column_index": 0,
        "header": "column 1",
        "confidence": 0.75,
    } in candidates
    assert {
        "field": "description",
        "column_index": 2,
        "header": "column 3",
        "confidence": 0.65,
    } in candidates
    assert not any(
        candidate["field"] == "operation_date" and candidate["column_index"] == 2
        for candidate in candidates
    )


def test_unknown_statement_analysis_split_debit_credit_suggestion_has_no_warning() -> None:
    extracted = ExtractedPdf(
        text_by_page=["Account statement"],
        tables_by_page=[
            ExtractedPdfPageTables(
                page_number=1,
                tables=[
                    [
                        ["Date", "Description", "Debit", "Credit"],
                        ["2026-05-12", "Coffee shop", "5.50", ""],
                        ["2026-05-13", "Salary", "", "2000.00"],
                    ]
                ],
            )
        ],
        metadata={},
    )

    report = analyze_unknown_statement(extracted).as_validation_report()
    previews = cast(list[dict[str, object]], report["table_previews"])
    suggestions = cast(list[dict[str, object]], previews[0]["mapping_suggestions"])
    suggestion = suggestions[0]

    assert suggestion["amount_column"] is None
    assert suggestion["debit_amount_column"] == 2
    assert suggestion["credit_amount_column"] == 3
    assert suggestion["warnings"] == []


def test_unknown_statement_analysis_detects_split_debit_credit_table() -> None:
    extracted = ExtractedPdf(
        text_by_page=["Выписка по счету"],
        tables_by_page=[
            ExtractedPdfPageTables(
                page_number=1,
                tables=[
                    [
                        ["Дата", "Описание", "Списание", "Зачисление"],
                        ["12.05.2026", "Кафе", "500.00", ""],
                        ["13.05.2026", "Пополнение", "", "10000.00"],
                    ]
                ],
            )
        ],
        metadata={},
    )

    report = analyze_unknown_statement(extracted).as_validation_report()
    previews = cast(list[dict[str, object]], report["table_previews"])
    column_candidates = cast(list[dict[str, object]], previews[0]["column_candidates"])

    assert len(previews) == 1
    assert {
        "field": "operation_date",
        "column_index": 0,
        "header": "Дата",
        "confidence": 0.95,
    } in column_candidates
    assert {
        "field": "description",
        "column_index": 1,
        "header": "Описание",
        "confidence": 0.9,
    } in column_candidates
    assert {
        "field": "debit_amount",
        "column_index": 2,
        "header": "Списание",
        "confidence": 0.9,
    } in column_candidates
    assert {
        "field": "credit_amount",
        "column_index": 3,
        "header": "Зачисление",
        "confidence": 0.9,
    } in column_candidates


def test_sanitized_unknown_statement_fixture_covers_posting_date_and_balance() -> None:
    extracted = sanitized_unknown_statement_fixture("generic_english_card_statement.json")

    report = analyze_unknown_statement(extracted).as_validation_report()
    command = default_mapping_command(report, default_currency="USD")
    preview = preview_unknown_statement_mapping(
        raw_tables_from_extracted_fixture(extracted),
        command,
        max_rows=None,
    )
    drafts = mapped_rows_to_drafts(preview.rows, command=command, account_id=uuid4())

    assert extracted.metadata["fixture_kind"] == "sanitized_unknown_statement"
    assert report["detected_bank_name"] is None
    assert report["statement_total_inflow"] == "250.25"
    assert command.operation_date_column == 0
    assert command.posting_date_column == 1
    assert command.description_column == 2
    assert command.amount_column == 3
    assert command.currency_column == 4
    assert command.balance_after_column == 5
    assert preview.valid_count == 2
    assert preview.error_count == 0
    assert drafts[0].posting_date == parse_bank_date("2026-05-13")
    assert drafts[0].balance_after == Decimal("994.50")
    assert drafts[1].amount == Decimal("250.25")


def test_sanitized_unknown_statement_fixture_covers_split_continuation_tables() -> None:
    extracted = sanitized_unknown_statement_fixture("split_debit_credit_continuation.json")

    report = analyze_unknown_statement(extracted).as_validation_report()
    table_previews = cast(list[dict[str, object]], report["table_previews"])
    continuation_preview = table_previews[1]
    command = default_mapping_command(report, default_currency="RUB")
    preview = preview_compatible_unknown_statement_mapping(
        raw_tables_from_extracted_fixture(extracted),
        command,
        max_rows=None,
    )

    assert report["detected_bank_name"] is None
    assert command.page_number == 1
    assert command.table_index == 1
    assert command.amount_column is None
    assert command.debit_amount_column == 2
    assert command.credit_amount_column == 3
    assert command.balance_after_column == 4
    assert continuation_preview["is_continuation"] is True
    assert continuation_preview["continued_from_page_number"] == 1
    assert continuation_preview["continued_from_table_index"] == 1
    assert continuation_preview["preview_row_count"] == 2
    assert continuation_preview["row_count"] == 2
    assert (
        compatible_mapping_table_count(raw_tables_from_extracted_fixture(extracted), command) == 2
    )
    assert [(row.page_number, row.table_index) for row in preview.rows] == [
        (1, 1),
        (1, 1),
        (2, 0),
        (2, 0),
    ]
    assert [row.amount for row in preview.rows] == [
        Decimal("-500.00"),
        Decimal("10000.00"),
        Decimal("-320.00"),
        Decimal("150.00"),
    ]
    assert [row.balance_after for row in preview.rows] == [
        Decimal("9500.00"),
        Decimal("19500.00"),
        Decimal("19180.00"),
        Decimal("19330.00"),
    ]


def test_unknown_statement_extracts_ozon_control_totals_from_text() -> None:
    control_totals = extract_unknown_statement_control_totals(
        [
            "\n".join(
                [
                    "Валюта: РОССИЙСКИЙ РУБЛЬ",
                    "Входящий остаток: 46 003.06 ₽",
                    "Итого зачислений за период: 69 796.06 ₽",
                    "Итого списаний за период: 58 205.74 ₽",
                    "Исходящий остаток: 57 593.38 ₽",
                ]
            )
        ]
    )

    assert control_totals is not None
    assert control_totals.currency == "RUB"
    assert control_totals.opening_balance == Decimal("46003.06")
    assert control_totals.total_inflow == Decimal("69796.06")
    assert control_totals.total_outflow == Decimal("58205.74")
    assert control_totals.closing_balance == Decimal("57593.38")


def test_unknown_statement_extracts_generic_english_control_totals_from_text() -> None:
    control_totals = extract_unknown_statement_control_totals(
        [
            "\n".join(
                [
                    "Currency: USD",
                    "Opening balance: $1,000.00",
                    "Total credits: 250.25 USD",
                    "Total debits: 100.10 USD",
                    "Closing balance: $1,150.15",
                ]
            )
        ]
    )

    assert control_totals is not None
    assert control_totals.currency == "USD"
    assert control_totals.opening_balance == Decimal("1000.00")
    assert control_totals.total_inflow == Decimal("250.25")
    assert control_totals.total_outflow == Decimal("100.10")
    assert control_totals.closing_balance == Decimal("1150.15")
