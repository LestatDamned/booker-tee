import json
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.features.imports.documents.validation_report import (
    StoredValidationReport,
)
from app.features.imports.mapping.analysis.analyzer import (
    StatementAnalyzer,
)
from app.features.imports.mapping.analysis.dto import UnknownStatementAnalysis
from app.features.imports.mapping.analysis.hints import (
    DEFAULT_HINT_CONFIG_PATH,
    extract_statement_control_totals,
    load_statement_hint_config,
)
from app.features.imports.mapping.analysis.text_tables import (
    raw_tables_with_text_candidate_tables,
)
from app.features.imports.mapping.drafts import StatementMappingDraftBuilder
from app.features.imports.mapping.engine import (
    StatementMappingEngine,
)
from app.features.imports.mapping.raw_tables import (
    compatible_mapping_tables,
)
from app.features.imports.mapping.templates import (
    StatementMappingDefaultResolver,
)
from app.features.imports.parsers.extractors.dto import (
    ExtractedStatement,
    ExtractedStatementPageTables,
)
from app.features.imports.parsers.support.normalization import parse_bank_date
from app.features.imports.statements.validation import StatementValidationStatus


def stored_report_json(analysis: UnknownStatementAnalysis) -> dict[str, object]:
    return analysis.stored_report().model_dump(mode="json", exclude_unset=True)


def sanitized_unknown_statement_fixture(name: str) -> ExtractedStatement:
    path = Path("tests/fixtures/unknown_statements") / name
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    text_by_page = payload.get("text_by_page")
    tables_by_page = payload.get("tables_by_page")
    metadata = payload.get("metadata")
    assert isinstance(text_by_page, list)
    assert isinstance(tables_by_page, list)
    assert isinstance(metadata, dict)
    return ExtractedStatement(
        text_by_page=[str(page_text) for page_text in text_by_page],
        tables_by_page=[
            extracted_page_tables_from_payload(page_tables)
            for page_tables in tables_by_page
            if isinstance(page_tables, dict)
        ],
        metadata=cast(dict[str, object], metadata),
    )


def extracted_page_tables_from_payload(
    payload: dict[object, object],
) -> ExtractedStatementPageTables:
    page_number = payload.get("page_number")
    tables = payload.get("tables")
    assert isinstance(page_number, int)
    assert isinstance(tables, list)
    return ExtractedStatementPageTables(
        page_number=page_number,
        tables=cast(list[list[list[str | None]]], tables),
    )


def raw_tables_from_extracted_fixture(extracted: ExtractedStatement) -> list[dict[str, object]]:
    return [
        {
            "page_number": page_tables.page_number,
            "tables": page_tables.tables,
        }
        for page_tables in extracted.tables_by_page
    ]


def english_statement() -> ExtractedStatement:
    return ExtractedStatement(
        text_by_page=["Account statement"],
        tables_by_page=[
            ExtractedStatementPageTables(
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


def test_unknown_statement_hints_load_from_config_file() -> None:
    config = load_statement_hint_config(DEFAULT_HINT_CONFIG_PATH)

    assert "Opening balance" in config.generic_control_total_labels.opening_balance
    ozon_hint = next(hint for hint in config.banks if hint.bank_name == "Ozon Bank")
    assert "ozon bank" in ozon_hint.markers
    assert ozon_hint.statement_types[0].statement_type == "card_statement"
    assert "Входящий остаток" in ozon_hint.control_total_labels[0].opening_balance


def test_unknown_statement_hints_reject_invalid_nested_config(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid-hints.json"
    config_path.write_text(
        json.dumps(
            {
                "generic_control_total_labels": {},
                "banks": [
                    {
                        "bank_name": "Example Bank",
                        "markers": ["example bank"],
                        "statement_types": [
                            {
                                "statement_type": "card_statement",
                                "markers": "operation",
                            }
                        ],
                        "unexpected": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError) as exc_info:
        load_statement_hint_config(config_path)

    error_locations = {error["loc"] for error in exc_info.value.errors()}
    assert ("banks", 0, "statement_types", 0, "markers") in error_locations
    assert ("banks", 0, "unexpected") in error_locations


def test_unknown_statement_analysis_finds_mapping_candidates() -> None:
    extracted = ExtractedStatement(
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
            ExtractedStatementPageTables(
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

    analysis = StatementAnalyzer.analyze(extracted)
    report = stored_report_json(analysis)
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
    } in column_candidates
    assert {
        "field": "description",
        "column_index": 2,
        "header": "Назначение платежа",
    } in column_candidates
    assert {
        "field": "amount",
        "column_index": 3,
        "header": "Сумма операции",
    } in column_candidates


def test_unknown_statement_analysis_finds_header_after_preamble() -> None:
    extracted = ExtractedStatement(
        text_by_page=[
            "\n".join(
                [
                    "Альфа-Банк",
                    "Операция по карте",
                ]
            )
        ],
        tables_by_page=[
            ExtractedStatementPageTables(
                page_number=1,
                tables=[
                    [
                        ["Дата открытия счета", "2026-01-01", None, None, None],
                        ["Валюта счета", "RUB", None, None, "Расходы"],
                        ["Дата формирования выписки", "2026-06-01", None, None, None],
                        ["Дата операции", "Дата проводки", None, "Описание", "Сумма"],
                        ["2026-06-01", "2026-06-02", None, "Coffee", "-10.50"],
                    ]
                ],
            )
        ],
        metadata={"source_format": "xlsx"},
    )

    analysis = StatementAnalyzer.analyze(extracted)
    report = stored_report_json(analysis)
    previews = cast(list[dict[str, object]], report["table_previews"])
    preview = previews[0]
    rows = cast(list[list[str]], preview["rows"])
    suggestions = cast(list[dict[str, object]], preview["mapping_suggestions"])
    suggestion = suggestions[0]

    assert report["detected_bank_name"] == "Alfa Bank"
    assert report["detected_statement_type"] == "card_statement"
    assert rows[0] == ["Дата операции", "Дата проводки", "", "Описание", "Сумма"]
    assert suggestion["operation_date_column"] == 0
    assert suggestion["posting_date_column"] == 1
    assert suggestion["description_column"] == 3
    assert suggestion["amount_column"] == 4
    assert suggestion["first_data_row"] == 4


def test_unknown_statement_analysis_keeps_all_table_candidates() -> None:
    extracted = ExtractedStatement(
        text_by_page=["Оплата товаров по карте" for _ in range(4)],
        tables_by_page=[
            ExtractedStatementPageTables(
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

    report = stored_report_json(StatementAnalyzer.analyze(extracted))
    previews = cast(list[dict[str, object]], report["table_previews"])

    assert report["page_count"] == 4
    assert report["table_count"] == 4
    assert [preview["page_number"] for preview in previews] == [1, 2, 3, 4]


def test_unknown_statement_analysis_detects_english_table_with_date_not_first() -> None:
    extracted = english_statement()

    report = stored_report_json(StatementAnalyzer.analyze(extracted))
    previews = cast(list[dict[str, object]], report["table_previews"])
    column_candidates = cast(list[dict[str, object]], previews[0]["column_candidates"])

    assert report["detected_bank_name"] is None
    assert report["detected_statement_type"] is None
    assert previews[0]["page_number"] == 1
    assert {
        "field": "description",
        "column_index": 0,
        "header": "Description",
    } in column_candidates
    assert {
        "field": "operation_date",
        "column_index": 1,
        "header": "Transaction Date",
    } in column_candidates
    assert {
        "field": "amount",
        "column_index": 2,
        "header": "Amount",
    } in column_candidates


def test_unknown_statement_analysis_keeps_column_profiles_internal() -> None:
    extracted = english_statement()

    analysis = StatementAnalyzer.analyze(extracted)
    profiles = analysis.table_previews[0].column_profiles
    report = stored_report_json(analysis)
    previews = cast(list[dict[str, object]], report["table_previews"])

    assert profiles[0].header == "Description"
    assert profiles[0].description_like_count == 2
    assert profiles[0].header_matches == ["description"]
    assert profiles[1].header == "Transaction Date"
    assert profiles[1].date_like_count == 2
    assert profiles[1].header_matches == ["operation_date"]
    assert profiles[2].money_like_count == 2
    assert profiles[3].currency_like_count == 2
    assert "column_profiles" not in previews[0]


def test_unknown_statement_analysis_includes_mapping_suggestions() -> None:
    extracted = english_statement()

    report = stored_report_json(StatementAnalyzer.analyze(extracted))
    previews = cast(list[dict[str, object]], report["table_previews"])
    suggestions = cast(list[dict[str, object]], previews[0]["mapping_suggestions"])
    suggestion = suggestions[0]
    reasons = cast(list[dict[str, object]], suggestion["reasons"])

    assert suggestion["operation_date_column"] == 1
    assert suggestion["description_column"] == 0
    assert suggestion["amount_column"] == 2
    assert suggestion["currency_column"] == 3
    assert suggestion["first_data_row"] == 1
    assert {
        "field": "operation_date",
        "column_index": 1,
        "header": "Transaction Date",
        "evidence": "header_match",
        "matched_count": None,
        "sample_count": None,
    } in reasons


def test_unknown_statement_analysis_detects_balance_after_column() -> None:
    extracted = ExtractedStatement(
        text_by_page=["Account statement"],
        tables_by_page=[
            ExtractedStatementPageTables(
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

    report = stored_report_json(StatementAnalyzer.analyze(extracted))
    previews = cast(list[dict[str, object]], report["table_previews"])
    column_candidates = cast(list[dict[str, object]], previews[0]["column_candidates"])
    suggestions = cast(list[dict[str, object]], previews[0]["mapping_suggestions"])
    suggestion = suggestions[0]
    reasons = cast(list[dict[str, object]], suggestion["reasons"])

    assert {
        "field": "balance_after",
        "column_index": 4,
        "header": "Balance",
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
    extracted = ExtractedStatement(
        text_by_page=["Account statement"],
        tables_by_page=[
            ExtractedStatementPageTables(
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

    report = stored_report_json(StatementAnalyzer.analyze(extracted))
    previews = cast(list[dict[str, object]], report["table_previews"])
    column_candidates = cast(list[dict[str, object]], previews[0]["column_candidates"])
    suggestions = cast(list[dict[str, object]], previews[0]["mapping_suggestions"])
    suggestion = suggestions[0]
    reasons = cast(list[dict[str, object]], suggestion["reasons"])

    assert {
        "field": "posting_date",
        "column_index": 1,
        "header": "Posting Date",
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
    extracted = ExtractedStatement(
        text_by_page=["Account statement"],
        tables_by_page=[
            ExtractedStatementPageTables(
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

    report = stored_report_json(StatementAnalyzer.analyze(extracted))
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
    extracted = ExtractedStatement(
        text_by_page=["Account statement"],
        tables_by_page=[
            ExtractedStatementPageTables(
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

    analysis = StatementAnalyzer.analyze(extracted)
    profiles = analysis.table_previews[0].column_profiles
    report = stored_report_json(analysis)
    previews = cast(list[dict[str, object]], report["table_previews"])
    preview = previews[0]
    suggestions = cast(list[dict[str, object]], preview["mapping_suggestions"])
    suggestion = suggestions[0]
    reasons = cast(list[dict[str, object]], suggestion["reasons"])

    assert preview["rows"] == [
        ["2026-05-12", "Coffee shop", "-5.50", "USD"],
        ["2026-05-13", "Salary", "+2000.00", "USD"],
        ["2026-05-14", "Groceries", "-42.10", "USD"],
    ]
    assert profiles[0].header == "column 1"
    assert profiles[0].header_matches == []
    assert suggestion["operation_date_column"] == 0
    assert suggestion["description_column"] == 1
    assert suggestion["amount_column"] == 2
    assert suggestion["currency_column"] == 3
    assert suggestion["first_data_row"] == 0
    assert suggestion["warnings"] == []
    assert {
        "field": "operation_date",
        "column_index": 0,
        "header": "column 1",
        "evidence": "date_like_values",
        "matched_count": 3,
        "sample_count": 3,
    } in reasons


def test_unknown_statement_analysis_builds_text_candidate_table_when_pdf_tables_are_empty() -> None:
    extracted = ExtractedStatement(
        text_by_page=[
            "\n".join(
                [
                    "ООО «ОЗОН Банк»",
                    "12.05.2026 Оплата товаров по карте -842,00 ₽ 57 593,38 ₽",
                    "Продолжение описания покупки",
                    "13.05.2026 Пополнение карты +10 000,00 RUB 67 593,38 ₽",
                ]
            )
        ],
        tables_by_page=[
            ExtractedStatementPageTables(
                page_number=1,
                tables=[
                    [],
                    [["", "", ""]],
                ],
            )
        ],
        metadata={},
    )

    analysis = StatementAnalyzer.analyze(extracted)
    report = stored_report_json(analysis)
    previews = cast(list[dict[str, object]], report["table_previews"])
    preview = previews[0]
    command = StatementMappingDefaultResolver.resolve(
        StoredValidationReport.model_validate(report),
        default_currency="RUB",
    ).spec
    mapped_preview = StatementMappingEngine.apply(
        raw_tables_with_text_candidate_tables(
            analysis.generated_text_tables,
            raw_tables_from_extracted_fixture(extracted),
        ),
        command,
        max_rows=None,
    )

    assert report["table_count"] == 2
    assert report["text_based"] is True
    assert preview["source_type"] == "text_candidate"
    assert preview["table_index"] == 2
    assert preview["rows"] == [
        ["Date", "Description", "Amount", "Currency", "Balance"],
        [
            "12.05.2026",
            "Оплата товаров по карте Продолжение описания покупки",
            "-842,00 ₽",
            "RUB",
            "57 593,38 ₽",
        ],
        ["13.05.2026", "Пополнение карты", "+10 000,00 RUB", "RUB", "67 593,38 ₽"],
    ]
    assert command.page_number == 1
    assert command.table_index == 2
    assert command.operation_date_column == 0
    assert command.description_column == 1
    assert command.amount_column == 2
    assert command.currency_column == 3
    assert command.balance_after_column == 4
    assert command.first_data_row == 1
    assert mapped_preview.valid_count == 2
    assert mapped_preview.error_count == 0
    assert [row.amount for row in mapped_preview.rows] == [
        Decimal("-842.00"),
        Decimal("10000.00"),
    ]
    assert [row.balance_after for row in mapped_preview.rows] == [
        Decimal("57593.38"),
        Decimal("67593.38"),
    ]


def test_unknown_statement_persists_all_generated_rows_beyond_preview() -> None:
    transaction_lines = [f"{day:02d}.05.2026 Operation {day} -{day},00 RUB" for day in range(1, 9)]
    extracted = ExtractedStatement(
        text_by_page=["\n".join(transaction_lines)],
        tables_by_page=[],
        metadata={},
    )

    analysis = StatementAnalyzer.analyze(extracted)
    report = stored_report_json(analysis)
    raw_tables = raw_tables_with_text_candidate_tables(
        analysis.generated_text_tables,
        None,
    )
    persisted_tables = cast(list[list[list[str]]], raw_tables[0]["tables"])

    assert analysis.table_previews[0].preview_row_count == 5
    assert analysis.table_previews[0].row_count == 9
    assert len(persisted_tables[0]) == 9
    assert persisted_tables[0][-1][1] == "Operation 8"
    assert "generated_text_tables" not in report


def test_unknown_statement_analysis_does_not_treat_transaction_text_as_header() -> None:
    long_description = (
        "Оплата товаров по карте 3977 сумма 390.00 RUB в MERCHANT EXAMPLE CITY RU "
        "дата 2026-05-30 время 18:16:34"
    )
    extracted = ExtractedStatement(
        text_by_page=["Account statement"],
        tables_by_page=[
            ExtractedStatementPageTables(
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

    analysis = StatementAnalyzer.analyze(extracted)
    profiles = analysis.table_previews[0].column_profiles
    report = stored_report_json(analysis)
    previews = cast(list[dict[str, object]], report["table_previews"])
    preview = previews[0]
    candidates = cast(list[dict[str, object]], preview["column_candidates"])
    rows = cast(list[list[str]], preview["rows"])

    assert rows[0][2] == long_description
    assert profiles[2].header == "column 3"
    assert profiles[2].header_matches == []
    assert profiles[2].money_like_count == 0
    assert profiles[2].description_like_count == 2
    assert {
        "field": "operation_date",
        "column_index": 0,
        "header": "column 1",
    } in candidates
    assert {
        "field": "description",
        "column_index": 2,
        "header": "column 3",
    } in candidates
    assert not any(
        candidate["field"] == "operation_date" and candidate["column_index"] == 2
        for candidate in candidates
    )


def test_unknown_statement_analysis_split_debit_credit_suggestion_has_no_warning() -> None:
    extracted = ExtractedStatement(
        text_by_page=["Account statement"],
        tables_by_page=[
            ExtractedStatementPageTables(
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

    report = stored_report_json(StatementAnalyzer.analyze(extracted))
    previews = cast(list[dict[str, object]], report["table_previews"])
    suggestions = cast(list[dict[str, object]], previews[0]["mapping_suggestions"])
    suggestion = suggestions[0]

    assert suggestion["amount_column"] is None
    assert suggestion["debit_amount_column"] == 2
    assert suggestion["credit_amount_column"] == 3
    assert suggestion["warnings"] == []


def test_unknown_statement_analysis_detects_split_debit_credit_table() -> None:
    extracted = ExtractedStatement(
        text_by_page=["Выписка по счету"],
        tables_by_page=[
            ExtractedStatementPageTables(
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

    report = stored_report_json(StatementAnalyzer.analyze(extracted))
    previews = cast(list[dict[str, object]], report["table_previews"])
    column_candidates = cast(list[dict[str, object]], previews[0]["column_candidates"])

    assert len(previews) == 1
    assert {
        "field": "operation_date",
        "column_index": 0,
        "header": "Дата",
    } in column_candidates
    assert {
        "field": "description",
        "column_index": 1,
        "header": "Описание",
    } in column_candidates
    assert {
        "field": "debit_amount",
        "column_index": 2,
        "header": "Списание",
    } in column_candidates
    assert {
        "field": "credit_amount",
        "column_index": 3,
        "header": "Зачисление",
    } in column_candidates


def test_sanitized_unknown_statement_fixture_covers_posting_date_and_balance() -> None:
    extracted = sanitized_unknown_statement_fixture("generic_english_card_statement.json")

    report = stored_report_json(StatementAnalyzer.analyze(extracted))
    command = StatementMappingDefaultResolver.resolve(
        StoredValidationReport.model_validate(report),
        default_currency="USD",
    ).spec
    preview = StatementMappingEngine.apply(
        raw_tables_from_extracted_fixture(extracted),
        command,
        max_rows=None,
    )
    drafts = StatementMappingDraftBuilder(
        spec=command,
        account_id=uuid4(),
    ).build_rows(preview.rows)

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

    report = stored_report_json(StatementAnalyzer.analyze(extracted))
    table_previews = cast(list[dict[str, object]], report["table_previews"])
    continuation_preview = table_previews[1]
    command = StatementMappingDefaultResolver.resolve(
        StoredValidationReport.model_validate(report),
        default_currency="RUB",
    ).spec
    preview = StatementMappingEngine.apply(
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
        len(
            compatible_mapping_tables(
                raw_tables_from_extracted_fixture(extracted),
                command,
            )
        )
        == 2
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


def test_stored_unknown_statement_report_decodes_nested_mapping_contract() -> None:
    extracted = sanitized_unknown_statement_fixture("generic_english_card_statement.json")

    stored = StatementAnalyzer.analyze(extracted).stored_report()

    assert stored.needs_mapping is True
    assert stored.statement_status is None
    assert stored.statement_total_inflow == "250.25"
    assert stored.opening_balance == "1000.00"
    assert len(stored.table_previews) == 1
    preview = stored.table_previews[0]
    assert preview.page_number == 1
    assert preview.column_candidates[0].column_index == 0
    assert preview.mapping_suggestions[0].posting_date_column == 1
    assert preview.mapping_suggestions[0].reasons


def test_stored_validation_report_decodes_known_and_legacy_fields() -> None:
    stored = StoredValidationReport.model_validate(
        {
            "status": "mismatch",
            "message": "Totals differ.",
            "extracted_count": 2,
            "calculated_total_inflow": Decimal("10.00"),
            "unexplained_inflow_difference": "",
            "balance_chain": {
                "status": "valid",
                "checked_pair_count": 1,
                "mismatch_count": 0,
            },
            "future_field": "ignored",
        }
    )

    assert stored.statement_status is StatementValidationStatus.MISMATCH
    assert stored.balance_chain_status is StatementValidationStatus.VALID
    assert stored.calculated_total_inflow == "10.00"
    assert stored.unexplained_inflow_difference is None
    assert stored.table_previews == ()


def test_unknown_statement_extracts_ozon_control_totals_from_text() -> None:
    control_totals = extract_statement_control_totals(
        [
            "\n".join(
                [
                    "ООО «ОЗОН Банк»",
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
    control_totals = extract_statement_control_totals(
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


def test_unknown_statement_preserves_zero_control_totals() -> None:
    control_totals = extract_statement_control_totals(
        [
            "\n".join(
                [
                    "Currency: USD",
                    "Opening balance: 0.00 USD",
                    "Total credits: 0.00 USD",
                    "Total debits: 0.00 USD",
                    "Closing balance: 0.00 USD",
                ]
            )
        ]
    )

    assert control_totals is not None
    assert control_totals.opening_balance == Decimal("0.00")
    assert control_totals.total_inflow == Decimal("0.00")
    assert control_totals.total_outflow == Decimal("0.00")
    assert control_totals.closing_balance == Decimal("0.00")


def test_unknown_statement_does_not_guess_missing_currency() -> None:
    control_totals = extract_statement_control_totals(
        ["Opening balance: 1000.00\nClosing balance: 1200.00"]
    )

    assert control_totals is not None
    assert control_totals.currency is None


def test_unknown_statement_ignores_unmatched_bank_control_total_labels() -> None:
    control_totals = extract_statement_control_totals(["Расходы: 500.00 ₽"])

    assert control_totals is None


def test_unknown_statement_uses_control_total_labels_for_detected_bank() -> None:
    control_totals = extract_statement_control_totals(["Альфа-Банк\nРасходы: 500.00 ₽"])

    assert control_totals is not None
    assert control_totals.total_outflow == Decimal("500.00")
