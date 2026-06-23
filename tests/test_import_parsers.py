from decimal import Decimal
from pathlib import Path

from app.features.imports.infrastructure.extraction.pdfplumber_extractor import (
    ExtractedPdf,
    ExtractedPdfPageTables,
    PdfPlumberExtractor,
)
from app.features.imports.models import RawTransactionStatus
from app.features.imports.parsing.parsers.alfabank.xlsx import AlfabankXlsxStatementParser
from app.features.imports.parsing.parsers.expobank.card import ExpobankCardStatementParser
from app.features.imports.parsing.parsers.ozon_bank.card import OzonBankCardStatementParser
from app.features.imports.parsing.parsers.sberbank.card import SberbankCardStatementParser
from app.features.imports.parsing.parsers.tbank.card import TbankCardStatementParser
from app.features.imports.parsing.parsers.vtb.card import VtbCardStatementParser
from app.features.imports.parsing.parsers.vtb.deposit import VtbDepositStatementParser
from app.features.imports.parsing.registry import default_statement_parser_registry
from app.features.imports.parsing.support.normalization import (
    normalize_description,
    parse_bank_date,
    parse_money_amount,
)


def test_expobank_parser_creates_normalized_raw_transactions_from_fixture() -> None:
    extracted = PdfPlumberExtractor().extract(Path("tests/fixtures/expobank_statement.pdf"))
    parser = ExpobankCardStatementParser()

    rows = parser.extract_raw_transactions(extracted, account_id=None, currency="RUB")

    assert parser.can_parse(extracted)
    assert len(rows) == 91
    assert rows[0].status == RawTransactionStatus.NORMALIZED
    assert rows[0].operation_date == parse_bank_date("29.05.2026")
    assert rows[0].amount == parse_money_amount("21 000.00")
    assert rows[0].currency == "RUB"
    assert rows[0].raw_payload["bank_code"] == "expobank"
    assert rows[1].amount == Decimal("-743.75")


def test_expobank_parser_extracts_statement_control_totals_from_fixture() -> None:
    extracted = PdfPlumberExtractor().extract(Path("tests/fixtures/expobank_statement.pdf"))
    parser = ExpobankCardStatementParser()

    control_totals = parser.extract_control_totals(extracted, currency="RUB")

    assert control_totals is not None
    assert control_totals.total_inflow == Decimal("102600.00")
    assert control_totals.total_outflow == Decimal("94056.37")
    assert control_totals.currency == "RUB"


def test_statement_parser_registry_detects_bank_and_statement_type() -> None:
    registry = default_statement_parser_registry()
    expobank_extracted = PdfPlumberExtractor().extract(
        Path("tests/fixtures/expobank_statement.pdf")
    )
    vtb_extracted = PdfPlumberExtractor().extract(Path("tests/fixtures/VTB_statement_june.pdf"))
    vtb_card_extracted = PdfPlumberExtractor().extract(
        Path("tests/fixtures/vtb_card_statement.pdf")
    )
    sberbank_extracted = PdfPlumberExtractor().extract(
        Path("tests/fixtures/sberbank_statement.pdf")
    )
    alfabank_extracted = alfabank_xlsx_extracted_fixture()
    ozon_extracted = ozon_bank_card_extracted_fixture()
    tbank_extracted = tbank_card_extracted_fixture()

    expobank_parser = registry.find_parser(expobank_extracted)
    vtb_parser = registry.find_parser(vtb_extracted)
    vtb_card_parser = registry.find_parser(vtb_card_extracted)
    sberbank_parser = registry.find_parser(sberbank_extracted)
    alfabank_parser = registry.find_parser(alfabank_extracted)
    ozon_parser = registry.find_parser(ozon_extracted)
    tbank_parser = registry.find_parser(tbank_extracted)

    assert expobank_parser is not None
    assert expobank_parser.parser_name == "expobank_card_statement_v1"
    assert expobank_parser.statement_type == "card_statement"
    assert vtb_parser is not None
    assert vtb_parser.parser_name == "vtb_deposit_statement_v1"
    assert vtb_parser.statement_type == "deposit_statement"
    assert vtb_card_parser is not None
    assert vtb_card_parser.parser_name == "vtb_card_statement_v1"
    assert vtb_card_parser.statement_type == "card_statement"
    assert sberbank_parser is not None
    assert sberbank_parser.parser_name == "sberbank_card_statement_v1"
    assert sberbank_parser.statement_type == "card_statement"
    assert alfabank_parser is not None
    assert alfabank_parser.parser_name == "alfabank_xlsx_statement_v1"
    assert alfabank_parser.statement_type == "card_statement"
    assert ozon_parser is not None
    assert ozon_parser.parser_name == "ozon_bank_card_statement_v1"
    assert ozon_parser.statement_type == "card_statement"
    assert tbank_parser is not None
    assert tbank_parser.parser_name == "tbank_card_statement_v1"
    assert tbank_parser.statement_type == "card_statement"


def test_alfabank_xlsx_parser_creates_raw_transactions_from_table_with_preamble() -> None:
    extracted = alfabank_xlsx_extracted_fixture()
    parser = AlfabankXlsxStatementParser()

    rows = parser.extract_raw_transactions(extracted, account_id=None, currency="RUB")
    control_totals = parser.extract_control_totals(extracted, currency="RUB")

    assert parser.can_parse(extracted)
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

    rows = parser.extract_raw_transactions(extracted, account_id=None, currency="RUB")
    control_totals = parser.extract_control_totals(extracted, currency="RUB")

    assert parser.can_parse(extracted)
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

    rows = parser.extract_raw_transactions(extracted, account_id=None, currency="RUB")
    control_totals = parser.extract_control_totals(extracted, currency="RUB")

    assert parser.can_parse(extracted)
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
    extracted = PdfPlumberExtractor().extract(Path("tests/fixtures/sberbank_statement.pdf"))
    parser = SberbankCardStatementParser()

    rows = parser.extract_raw_transactions(extracted, account_id=None, currency="RUB")
    control_totals = parser.extract_control_totals(extracted, currency="RUB")

    assert parser.can_parse(extracted)
    assert len(rows) == 11
    assert rows[0].operation_date == parse_bank_date("27.04.2026")
    assert rows[0].posting_date == parse_bank_date("27.04.2026")
    assert rows[0].amount == Decimal("25000.00")
    assert rows[0].balance_after == Decimal("27520.46")
    assert rows[0].status == RawTransactionStatus.NORMALIZED
    assert rows[1].amount == Decimal("-90000.00")
    assert rows[2].amount == Decimal("-2629.00")
    assert rows[-1].amount == Decimal("10000.00")
    assert "SAMOKAT SANKT-PETERBU RUS" in (rows[2].description_normalized or "")
    assert rows[0].raw_payload["bank_code"] == "sberbank"
    assert rows[0].raw_payload["statement_type"] == "card_statement"
    assert rows[0].account_hint_raw is not None
    assert rows[0].account_hint_raw.startswith("счет ****")
    assert rows[0].account_hint_raw.count("*") >= 4
    assert control_totals is not None
    assert control_totals.opening_balance == Decimal("59581.38")
    assert control_totals.total_inflow == Decimal("159568.08")
    assert control_totals.total_outflow == Decimal("191629.00")
    assert control_totals.closing_balance == Decimal("27520.46")


def test_vtb_card_parser_creates_raw_transactions_from_fixture() -> None:
    extracted = PdfPlumberExtractor().extract(Path("tests/fixtures/vtb_card_statement.pdf"))
    parser = VtbCardStatementParser()

    rows = parser.extract_raw_transactions(extracted, account_id=None, currency="RUB")
    control_totals = parser.extract_control_totals(extracted, currency="RUB")

    assert parser.can_parse(extracted)
    assert len(rows) == 8
    assert rows[0].operation_date == parse_bank_date("26.05.2026")
    assert rows[0].posting_date == parse_bank_date("29.05.2026")
    assert rows[0].amount == Decimal("-2509.00")
    assert rows[0].currency == "RUB"
    assert rows[0].status == RawTransactionStatus.NORMALIZED
    assert rows[0].account_hint_raw == "карта ****"
    assert rows[1].amount == Decimal("-199.99")
    assert rows[2].amount == Decimal("-711.00")
    assert rows[-1].amount == Decimal("-2914.00")
    assert "SBER*5411*SAMOKAT" in (rows[0].description_normalized or "")
    assert rows[0].raw_payload["bank_code"] == "vtb"
    assert rows[0].raw_payload["statement_type"] == "card_statement"
    assert control_totals is not None
    assert control_totals.opening_balance == Decimal("0.00")
    assert control_totals.total_inflow == Decimal("0.00")
    assert control_totals.total_outflow == Decimal("15261.65")
    assert control_totals.closing_balance == Decimal("0.00")


def test_vtb_deposit_parser_creates_raw_transactions_from_may_period_fixture() -> None:
    extracted = PdfPlumberExtractor().extract(Path("tests/fixtures/VTB_statement_june.pdf"))
    parser = VtbDepositStatementParser()

    rows = parser.extract_raw_transactions(extracted, account_id=None, currency="RUB")
    control_totals = parser.extract_control_totals(extracted, currency="RUB")

    assert parser.can_parse(extracted)
    assert len(rows) == 3
    assert rows[0].operation_date == parse_bank_date("08.05.2026")
    assert rows[0].posting_date == parse_bank_date("08.05.2026")
    assert rows[0].amount == Decimal("-21000.00")
    assert rows[0].status == RawTransactionStatus.NORMALIZED
    assert rows[2].amount == Decimal("14316.35")
    assert "Выплата % по дог" in (rows[2].description_normalized or "")
    assert rows[2].raw_payload["bank_code"] == "vtb"
    assert rows[2].raw_payload["statement_type"] == "deposit_statement"
    assert control_totals is not None
    assert control_totals.opening_balance == Decimal("1326326.24")
    assert control_totals.total_inflow == Decimal("14316.35")
    assert control_totals.total_outflow == Decimal("42000.00")
    assert control_totals.closing_balance == Decimal("1298642.59")


def test_vtb_deposit_parser_creates_raw_transactions_from_june_period_fixture() -> None:
    extracted = PdfPlumberExtractor().extract(Path("tests/fixtures/VTB_statement_may.pdf"))
    parser = VtbDepositStatementParser()

    rows = parser.extract_raw_transactions(extracted, account_id=None, currency="RUB")
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
    extracted = ExtractedPdf(
        text_by_page=[""],
        tables_by_page=[ExtractedPdfPageTables(page_number=1, tables=[table])],
        metadata={},
    )

    rows = ExpobankCardStatementParser().extract_raw_transactions(
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


def alfabank_xlsx_extracted_fixture() -> ExtractedPdf:
    return ExtractedPdf(
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
            ExtractedPdfPageTables(
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


def ozon_bank_card_extracted_fixture() -> ExtractedPdf:
    return ExtractedPdf(
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
            ExtractedPdfPageTables(
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


def tbank_card_extracted_fixture() -> ExtractedPdf:
    return ExtractedPdf(
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
        tables_by_page=[ExtractedPdfPageTables(page_number=1, tables=[])],
        metadata={"source_format": "pdf"},
    )


def row_with_values(values: dict[int, str]) -> list[str | None]:
    row: list[str | None] = [None] * 15
    for index, value in values.items():
        row[index] = value
    return row
