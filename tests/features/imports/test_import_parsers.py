from collections.abc import Callable
from decimal import Decimal

import pytest

from app.features.imports.parsers.alfabank import AlfabankXlsxStatementParser
from app.features.imports.parsers.expobank import ExpobankCardStatementParser
from app.features.imports.parsers.extractors.dto import (
    ExtractedStatement,
    ExtractedStatementPageTables,
)
from app.features.imports.parsers.ozon_bank import OzonBankCardStatementParser
from app.features.imports.parsers.protocol import BankStatementParser
from app.features.imports.parsers.registry import StatementParserRegistry
from app.features.imports.parsers.sberbank import (
    SberbankCardStatementParser,
)
from app.features.imports.parsers.sberbank import (
    stable_source_row_id as sberbank_source_row_id,
)
from app.features.imports.parsers.support.normalization import (
    normalize_description,
    parse_bank_date,
    parse_money_amount,
)
from app.features.imports.parsers.tbank import TbankCardStatementParser
from app.features.imports.parsers.vtb.card import (
    VtbCardStatementParser,
    stable_card_source_row_id,
)
from app.features.imports.parsers.vtb.deposit import (
    VtbDepositStatementParser,
)
from app.features.imports.parsers.vtb.deposit import (
    stable_source_row_id as vtb_deposit_source_row_id,
)
from app.features.imports.statements.types import RawTransactionStatus


def test_expobank_parser_creates_normalized_raw_transactions_from_fixture() -> None:
    extracted = expobank_extracted_fixture()
    parser = ExpobankCardStatementParser()

    rows = parser.parse_transaction_drafts(extracted, account_id=None, currency="RUB")

    assert parser.matches_statement(extracted)
    assert len(rows) == 2
    assert rows[0].status == RawTransactionStatus.NORMALIZED
    assert rows[0].operation_date == parse_bank_date("29.05.2026")
    assert rows[0].amount == parse_money_amount("21 000.00")
    assert rows[0].currency == "RUB"
    assert rows[0].raw_payload["bank_code"] == "expobank"
    assert rows[1].amount == Decimal("-743.75")


def test_expobank_parser_extracts_statement_control_totals_from_fixture() -> None:
    extracted = expobank_extracted_fixture()
    parser = ExpobankCardStatementParser()

    control_totals = parser.extract_control_totals(extracted, currency="RUB")

    assert control_totals is not None
    assert control_totals.total_inflow == Decimal("21000.00")
    assert control_totals.total_outflow == Decimal("743.75")
    assert control_totals.currency == "RUB"


@pytest.mark.parametrize(
    ("extracted_factory", "expected_name", "expected_type"),
    [
        pytest.param(
            lambda: expobank_extracted_fixture(),
            "expobank_card_statement_v1",
            "card_statement",
            id="expobank-card",
        ),
        pytest.param(
            lambda: vtb_deposit_extracted_fixture(),
            "vtb_deposit_statement_v1",
            "deposit_statement",
            id="vtb-deposit",
        ),
        pytest.param(
            lambda: vtb_card_extracted_fixture(),
            "vtb_card_statement_v1",
            "card_statement",
            id="vtb-card",
        ),
        pytest.param(
            lambda: sberbank_extracted_fixture(),
            "sberbank_card_statement_v1",
            "card_statement",
            id="sberbank-card",
        ),
        pytest.param(
            lambda: alfabank_xlsx_extracted_fixture(),
            "alfabank_xlsx_statement_v1",
            "card_statement",
            id="alfabank-card",
        ),
        pytest.param(
            lambda: ozon_bank_card_extracted_fixture(),
            "ozon_bank_card_statement_v1",
            "card_statement",
            id="ozon-card",
        ),
        pytest.param(
            lambda: tbank_card_extracted_fixture(),
            "tbank_card_statement_v1",
            "card_statement",
            id="tbank-card",
        ),
    ],
)
def test_statement_parser_registry_detects_bank_and_statement_type(
    extracted_factory: Callable[[], ExtractedStatement],
    expected_name: str,
    expected_type: str,
) -> None:
    registry = StatementParserRegistry.with_default_parsers()
    parser = registry.find_matching_parser(extracted_factory())

    assert parser is not None
    assert parser.parser_name == expected_name
    assert parser.statement_type == expected_type


def test_alfabank_xlsx_parser_creates_raw_transactions_from_table_with_preamble() -> None:
    extracted = alfabank_xlsx_extracted_fixture()
    parser = AlfabankXlsxStatementParser()

    rows = parser.parse_transaction_drafts(extracted, account_id=None, currency="RUB")
    control_totals = parser.extract_control_totals(extracted, currency="RUB")

    assert parser.matches_statement(extracted)
    assert len(rows) == 2
    assert rows[0].status == RawTransactionStatus.NORMALIZED
    assert rows[0].operation_date == parse_bank_date("2026-06-01")
    assert rows[0].posting_date == parse_bank_date("2026-06-02")
    assert rows[0].amount == Decimal("-10.50")
    assert rows[0].currency == "RUB"
    assert rows[0].description_normalized == "Coffee"
    assert rows[0].account_hint_raw == "счет ****"
    assert rows[0].raw_payload["bank_code"] == "alfabank"
    assert rows[0].raw_payload["statement_type"] == "card_statement"
    assert rows[0].raw_payload["source_row_id"] == "alfabank-xlsx:1:0:4"
    assert rows[1].amount == Decimal("500.00")
    assert rows[1].description_normalized == "Refund"
    assert control_totals is not None
    assert control_totals.currency == "RUB"
    assert control_totals.opening_balance == Decimal("1000.00")
    assert control_totals.closing_balance == Decimal("1489.50")
    assert control_totals.total_inflow == Decimal("500.00")
    assert control_totals.total_outflow == Decimal("10.50")


def test_ozon_bank_card_parser_creates_raw_transactions_from_pdf_table() -> None:
    extracted = ozon_bank_card_extracted_fixture()
    parser = OzonBankCardStatementParser()

    rows = parser.parse_transaction_drafts(extracted, account_id=None, currency="RUB")
    control_totals = parser.extract_control_totals(extracted, currency="RUB")

    assert parser.matches_statement(extracted)
    assert len(rows) == 2
    assert rows[0].status == RawTransactionStatus.NORMALIZED
    assert rows[0].operation_date == parse_bank_date("2026-06-01")
    assert rows[0].posting_date is None
    assert rows[0].amount == Decimal("-390.00")
    assert rows[0].currency == "RUB"
    assert rows[0].description_normalized == "Card purchase"
    assert rows[0].account_hint_raw == "карта ****"
    assert rows[0].raw_payload["bank_code"] == "ozon_bank"
    assert rows[0].raw_payload["statement_type"] == "card_statement"
    assert rows[0].raw_payload["source_row_id"] == "ozon-bank-card:100001"
    assert rows[1].amount == Decimal("65000.00")
    assert rows[1].description_normalized == "Cash deposit"
    assert control_totals is not None
    assert control_totals.currency == "RUB"
    assert control_totals.opening_balance == Decimal("1000.00")
    assert control_totals.closing_balance == Decimal("65610.00")
    assert control_totals.total_inflow == Decimal("65000.00")
    assert control_totals.total_outflow == Decimal("390.00")


def test_tbank_card_parser_creates_raw_transactions_from_text_layout() -> None:
    extracted = tbank_card_extracted_fixture()
    parser = TbankCardStatementParser()

    rows = parser.parse_transaction_drafts(extracted, account_id=None, currency="RUB")
    control_totals = parser.extract_control_totals(extracted, currency="RUB")

    assert parser.matches_statement(extracted)
    assert len(rows) == 3
    assert rows[0].status == RawTransactionStatus.NORMALIZED
    assert rows[0].operation_date == parse_bank_date("01.06.2026")
    assert rows[0].posting_date == parse_bank_date("02.06.2026")
    assert rows[0].amount == Decimal("-132.00")
    assert rows[0].currency == "RUB"
    assert rows[0].balance_after is None
    assert rows[0].description_normalized == "External transfer +70000000000"
    assert rows[0].account_hint_raw == "карта ****"
    assert rows[0].raw_payload["bank_code"] == "tbank"
    assert rows[0].raw_payload["statement_type"] == "card_statement"
    assert rows[0].raw_payload["source_row_id"] == "tbank-card:1:6"
    assert rows[1].amount == Decimal("500.00")
    assert rows[1].description_normalized == "Refund"
    assert rows[2].amount == Decimal("-359.96")
    assert rows[2].description_normalized == "06:11 Payment at KRASNYJ YAR KYA26 Krasnoyarsk RUS"
    assert control_totals is not None
    assert control_totals.currency == "RUB"
    assert control_totals.opening_balance == Decimal("1000.00")
    assert control_totals.closing_balance == Decimal("1008.04")
    assert control_totals.total_inflow == Decimal("500.00")
    assert control_totals.total_outflow == Decimal("491.96")


def test_sberbank_card_parser_creates_raw_transactions_from_fixture() -> None:
    extracted = sberbank_extracted_fixture()
    parser = SberbankCardStatementParser()

    rows = parser.parse_transaction_drafts(extracted, account_id=None, currency="RUB")
    control_totals = parser.extract_control_totals(extracted, currency="RUB")

    assert parser.matches_statement(extracted)
    assert len(rows) == 2
    assert rows[0].operation_date == parse_bank_date("27.04.2026")
    assert rows[0].posting_date == parse_bank_date("27.04.2026")
    assert rows[0].amount == Decimal("500.00")
    assert rows[0].balance_after == Decimal("1500.00")
    assert rows[0].status == RawTransactionStatus.NORMALIZED
    assert rows[1].amount == Decimal("-10.50")
    assert "Coffee shop" in (rows[1].description_normalized or "")
    assert rows[0].raw_payload["bank_code"] == "sberbank"
    assert rows[0].raw_payload["statement_type"] == "card_statement"
    assert rows[0].account_hint_raw is not None
    assert rows[0].account_hint_raw.startswith("счет ****")
    assert rows[0].account_hint_raw.count("*") >= 4
    assert control_totals is not None
    assert control_totals.opening_balance == Decimal("1000.00")
    assert control_totals.total_inflow == Decimal("500.00")
    assert control_totals.total_outflow == Decimal("10.50")
    assert control_totals.closing_balance == Decimal("1489.50")


def test_sberbank_auth_code_identity_survives_overlapping_statement_periods() -> None:
    partial = sberbank_source_row_id(
        auth_code="ABC123",
        source_line_index=10,
    )
    full = sberbank_source_row_id(
        auth_code="ABC123",
        source_line_index=42,
    )

    assert partial == full == "sberbank-card:auth:ABC123"


def test_positional_bank_row_identities_do_not_include_statement_period() -> None:
    assert sberbank_source_row_id(auth_code=None, source_line_index=10) == ("sberbank-card:line:10")
    assert (
        stable_card_source_row_id(
            row_index=7,
            operation_date_raw="10.05.2026",
            operation_time_raw="12:30:15",
        )
        == "vtb-card:10.05.2026:12:30:15:7"
    )
    assert vtb_deposit_source_row_id(12) == "vtb-deposit:12"


@pytest.mark.parametrize(
    ("extracted_factory", "parser", "full_period", "partial_period"),
    [
        pytest.param(
            lambda: sberbank_extracted_fixture(),
            SberbankCardStatementParser(),
            "За период 01.04.2026 — 30.04.2026",
            "За период 01.04.2026 — 31.05.2026",
            id="sberbank-card",
        ),
        pytest.param(
            lambda: vtb_card_extracted_fixture(),
            VtbCardStatementParser(),
            "Период выписки 01.05.2026 - 31.05.2026",
            "Период выписки 01.05.2026 - 10.05.2026",
            id="vtb-card",
        ),
        pytest.param(
            lambda: vtb_deposit_extracted_fixture(),
            VtbDepositStatementParser(),
            "Период выписки 01.05.2026 - 31.05.2026",
            "Период выписки 01.05.2026 - 10.05.2026",
            id="vtb-deposit",
        ),
    ],
)
def test_overlapping_statement_period_does_not_change_bank_row_hashes(
    extracted_factory: Callable[[], ExtractedStatement],
    parser: BankStatementParser,
    full_period: str,
    partial_period: str,
) -> None:
    extracted = extracted_factory()
    overlapping = extracted.model_copy(
        update={
            "text_by_page": [
                page.replace(full_period, partial_period) for page in extracted.text_by_page
            ]
        }
    )
    full_rows = parser.parse_transaction_drafts(extracted, account_id=None, currency="RUB")
    overlapping_rows = parser.parse_transaction_drafts(
        overlapping,
        account_id=None,
        currency="RUB",
    )

    assert [row.dedupe_hash for row in full_rows] == [row.dedupe_hash for row in overlapping_rows]


def test_vtb_card_parser_creates_raw_transactions_from_fixture() -> None:
    extracted = vtb_card_extracted_fixture()
    parser = VtbCardStatementParser()

    rows = parser.parse_transaction_drafts(extracted, account_id=None, currency="RUB")
    control_totals = parser.extract_control_totals(extracted, currency="RUB")

    assert parser.matches_statement(extracted)
    assert len(rows) == 2
    assert rows[0].operation_date == parse_bank_date("26.05.2026")
    assert rows[0].posting_date == parse_bank_date("29.05.2026")
    assert rows[0].amount == Decimal("-2509.00")
    assert rows[0].currency == "RUB"
    assert rows[0].status == RawTransactionStatus.NORMALIZED
    assert rows[0].account_hint_raw == "карта ****"
    assert rows[1].amount == Decimal("500.00")
    assert "SBER*5411*SAMOKAT" in (rows[0].description_normalized or "")
    assert rows[0].raw_payload["bank_code"] == "vtb"
    assert rows[0].raw_payload["statement_type"] == "card_statement"
    assert control_totals is not None
    assert control_totals.opening_balance == Decimal("0.00")
    assert control_totals.total_inflow == Decimal("500.00")
    assert control_totals.total_outflow == Decimal("2509.00")
    assert control_totals.closing_balance == Decimal("500.00")


def test_vtb_deposit_parser_creates_raw_transactions_from_may_period_fixture() -> None:
    extracted = vtb_deposit_extracted_fixture()
    parser = VtbDepositStatementParser()

    rows = parser.parse_transaction_drafts(extracted, account_id=None, currency="RUB")
    control_totals = parser.extract_control_totals(extracted, currency="RUB")

    assert parser.matches_statement(extracted)
    assert len(rows) == 2
    assert rows[0].operation_date == parse_bank_date("08.05.2026")
    assert rows[0].posting_date == parse_bank_date("08.05.2026")
    assert rows[0].amount == Decimal("-21000.00")
    assert rows[0].status == RawTransactionStatus.NORMALIZED
    assert rows[1].amount == Decimal("14316.35")
    assert "Выплата % по договору" in (rows[1].description_normalized or "")
    assert rows[1].raw_payload["bank_code"] == "vtb"
    assert rows[1].raw_payload["statement_type"] == "deposit_statement"
    assert control_totals is not None
    assert control_totals.opening_balance == Decimal("1326326.24")
    assert control_totals.total_inflow == Decimal("14316.35")
    assert control_totals.total_outflow == Decimal("21000.00")
    assert control_totals.closing_balance == Decimal("1319642.59")


def test_vtb_deposit_parser_creates_raw_transactions_from_june_period_fixture() -> None:
    extracted = vtb_deposit_extracted_fixture(
        period="01.06.2026 - 30.06.2026",
        opening="1298642.59",
        inflow="0.00",
        outflow="1298642.00",
        closing="0.59",
        rows=(
            "01.06.2026 01.06.2026 -4000.00 RUB 0.00 RUB 4000.00 RUB Transfer",
            "02.06.2026 02.06.2026 -8800.00 RUB 0.00 RUB 8800.00 RUB Transfer",
            "03.06.2026 03.06.2026 -1285842.00 RUB 0.00 RUB 1285842.00 RUB Transfer",
        ),
    )
    parser = VtbDepositStatementParser()

    rows = parser.parse_transaction_drafts(extracted, account_id=None, currency="RUB")
    control_totals = parser.extract_control_totals(extracted, currency="RUB")

    assert len(rows) == 3
    assert rows[0].operation_date == parse_bank_date("01.06.2026")
    assert rows[0].amount == Decimal("-4000.00")
    assert rows[1].amount == Decimal("-8800.00")
    assert rows[2].amount == Decimal("-1285842.00")
    assert control_totals is not None
    assert control_totals.opening_balance == Decimal("1298642.59")
    assert control_totals.total_inflow == Decimal("0.00")
    assert control_totals.total_outflow == Decimal("1298642.00")
    assert control_totals.closing_balance == Decimal("0.59")


def test_expobank_parser_marks_ambiguous_amounts_for_review() -> None:
    table: list[list[str | None]] = [
        [
            "Document",
            "Processed at",
            "Debiting",
            "Crediting",
            "Sender / Receiver",
            "Account",
            "Purpose",
        ],
        ["№1", "29.05.2026", "100.00", "50.00", "Counterparty", "Account", "Purpose"],
    ]
    extracted = ExtractedStatement(
        text_by_page=[""],
        tables_by_page=[ExtractedStatementPageTables(page_number=1, tables=[table])],
        metadata={},
    )

    rows = ExpobankCardStatementParser().parse_transaction_drafts(
        extracted,
        account_id=None,
        currency="RUB",
    )

    assert rows[0].status == RawTransactionStatus.NEEDS_REVIEW
    assert rows[0].amount is None
    assert rows[0].normalization_error == "Both debit and credit are present."


def test_normalizers_parse_bank_values_without_float() -> None:
    parsed_date = parse_bank_date("04.05.2026")

    assert parsed_date is not None
    assert parsed_date.isoformat() == "2026-05-04"
    assert parse_money_amount("1 234,50") == parse_money_amount("1234.50")
    assert parse_money_amount("1,298,642.59") == Decimal("1298642.59")
    assert parse_money_amount("-42,000.00") == Decimal("-42000.00")
    assert normalize_description("  Payment\nfor rent ", " Sender ") == "Payment for rent | Sender"


def expobank_extracted_fixture() -> ExtractedStatement:
    return ExtractedStatement(
        text_by_page=["Expobank synthetic statement"],
        tables_by_page=[
            ExtractedStatementPageTables(
                page_number=1,
                tables=[
                    [
                        [
                            "Document",
                            "Processed at",
                            "Debiting",
                            "Crediting",
                            "Sender / Receiver",
                            "Account",
                            "Purpose",
                        ],
                        ["№1", "29.05.2026", None, "21 000.00", "Employer", "****", "Salary"],
                        [
                            "№2",
                            "30.05.2026",
                            "743.75",
                            None,
                            "KRASNOE&BELOE",
                            "****",
                            "Card purchase",
                        ],
                        ["Total", None, "743.75", "21 000.00", None, None, None],
                    ]
                ],
            )
        ],
        metadata={"source_format": "pdf", "fixture": "synthetic"},
    )


def sberbank_extracted_fixture() -> ExtractedStatement:
    text = "\n".join(
        [
            "Выписка по счёту дебетовой карты",
            "За период 01.04.2026 — 30.04.2026",
            "Валюта Российский рубль",
            "Остаток на 01.04.2026 1000.00",
            "Номер счёта 00000000000000001234 Пополнение 500.00",
            "Карта **** 1234 Списание 10.50",
            "Остаток на 30.04.2026 1489.50",
            "ИТОГО ПО ОПЕРАЦИЯМ ЗА ПЕРИОД",
            "Расшифровка операций",
            "27.04.2026 10:00 5411 +500.00 1500.00",
            "27.04.2026 123456 Refund",
            "28.04.2026 11:00 5812 -10.50 1489.50",
            "28.04.2026 654321 Coffee shop",
            "*",
        ]
    )
    return extracted_text_fixture(text)


def vtb_card_extracted_fixture() -> ExtractedStatement:
    text = "\n".join(
        [
            "Номер карты 0000000000000000",
            "Период выписки 01.05.2026 - 31.05.2026",
            "Информация о балансе карты",
            "Баланс на начало периода 0.00 RUB В обработке 0.00 RUB",
            "Поступления 500.00 RUB",
            "Баланс на конец периода 500.00 RUB Расходные операции 2509.00 RUB",
            "Операции по карте",
        ]
    )
    table: list[list[str | None]] = [
        [
            "26.05.2026 10:00:00",
            "29.05.2026",
            "-2509.00 RUB",
            "-2509.00",
            "0.00",
            "SBER*5411*SAMOKAT",
        ],
        ["27.05.2026 11:00:00", "29.05.2026", "500.00 RUB", "500.00", "0.00", "Refund"],
    ]
    return extracted_text_fixture(text, tables=[table])


def vtb_deposit_extracted_fixture(
    *,
    period: str = "01.05.2026 - 31.05.2026",
    opening: str = "1326326.24",
    inflow: str = "14316.35",
    outflow: str = "21000.00",
    closing: str = "1319642.59",
    rows: tuple[str, ...] = (
        "08.05.2026 08.05.2026 -21000.00 RUB 0.00 RUB 21000.00 RUB Transfer",
        "31.05.2026 31.05.2026 14316.35 RUB 14316.35 RUB 0.00 RUB Выплата % по договору",
    ),
) -> ExtractedStatement:
    text = "\n".join(
        [
            f"Период выписки {period}",
            f"Баланс на начало периода {opening} RUB Поступления {inflow} RUB",
            f"Баланс на конец периода {closing} RUB Расходные операции {outflow} RUB",
            "00000000000000001234 (RUB)",
            "Операции по счету",
            *rows,
        ]
    )
    return extracted_text_fixture(text)


def extracted_text_fixture(
    text: str,
    *,
    tables: list[list[list[str | None]]] | None = None,
) -> ExtractedStatement:
    return ExtractedStatement(
        text_by_page=[text],
        tables_by_page=[ExtractedStatementPageTables(page_number=1, tables=tables or [])],
        metadata={"source_format": "pdf", "fixture": "synthetic"},
    )


def alfabank_xlsx_extracted_fixture() -> ExtractedStatement:
    return ExtractedStatement(
        text_by_page=[
            "\n".join(
                [
                    "Альфа-Банк",
                    "Операция по карте",
                    "Выписка по счету",
                ]
            )
        ],
        tables_by_page=[
            ExtractedStatementPageTables(
                page_number=1,
                tables=[
                    [
                        row_with_values({0: "Валюта счета", 1: "RUB"}),
                        row_with_values(
                            {
                                0: "Входящий остаток",
                                1: "1000.00",
                                4: "Поступления",
                                5: "500.00",
                                8: "Расходы",
                                9: "10.50",
                                12: "Текущий баланс",
                                13: "1489.50",
                            }
                        ),
                        row_with_values({0: "Дата формирования выписки", 1: "2026-06-03"}),
                        row_with_values(
                            {
                                0: "Дата операции",
                                1: "Дата проводки",
                                11: "Описание",
                                12: "Сумма в валюте счета",
                            }
                        ),
                        row_with_values(
                            {
                                0: "2026-06-01",
                                1: "2026-06-02",
                                11: "Coffee",
                                12: "-10.50",
                            }
                        ),
                        row_with_values(
                            {
                                0: "2026-06-02",
                                1: "2026-06-02",
                                11: "Refund",
                                12: "500.00",
                            }
                        ),
                        row_with_values({0: "Итого"}),
                    ]
                ],
            )
        ],
        metadata={"source_format": "xlsx"},
    )


def ozon_bank_card_extracted_fixture() -> ExtractedStatement:
    return ExtractedStatement(
        text_by_page=[
            "\n".join(
                [
                    "Озон Банк",
                    "Оплата товаров по карте",
                    "Входящий остаток: 1 000.00 ₽",
                    "Итого зачислений за период: 65 000.00 ₽",
                    "Итого списаний за период: 390.00 ₽",
                    "Исходящий остаток: 65 610.00 ₽",
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
                            "",
                        ],
                        ["", "", "", "Российские рубли", "Валюта"],
                        [
                            "01.06.2026 10:15:20",
                            "100001",
                            "Card purchase",
                            "- 390.00 ₽",
                            "- 390.00 ₽",
                        ],
                        [
                            "02.06.2026 11:00:00",
                            "100002",
                            "Cash deposit",
                            "65 000.00 ₽",
                            "65 000.00 ₽",
                        ],
                    ]
                ],
            )
        ],
        metadata={"source_format": "pdf"},
    )


def tbank_card_extracted_fixture() -> ExtractedStatement:
    return ExtractedStatement(
        text_by_page=[
            "\n".join(
                [
                    "Выписка по договору №0000000000",
                    "Баланс на 01.06.26 1 000.00 ₽",
                    "• Поступления 500.00 ₽",
                    "• Расходы -491.96 ₽",
                    "Операции по карте № 0000 0000 0000 0000",
                    "операции обработки Описание операции в валюте счёта",
                    "01.06.26 02.06.26 External transfer 132.00 ₽ 132.00 ₽",
                    "+70000000000",
                    "02.06.26 02.06.26 Refund +500.00 ₽ 1 110.00 ₽",
                    "13.06.26 13.06.26 06:11 Payment at KRASNYJ YAR KYA26 359.96 ₽ 359.96 ₽",
                    "Krasnoyarsk RUS",
                    "Баланс на 13.06.26 1 008.04 ₽",
                ]
            )
        ],
        tables_by_page=[ExtractedStatementPageTables(page_number=1, tables=[])],
        metadata={"source_format": "pdf"},
    )


def row_with_values(values: dict[int, str]) -> list[str | None]:
    row: list[str | None] = [None] * 15
    for index, value in values.items():
        row[index] = value
    return row
