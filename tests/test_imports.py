from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import UploadFile

from app.features.imports.extraction.pdfplumber_extractor import (
    ExtractedPdf,
    ExtractedPdfPageTables,
    PdfPlumberExtractor,
)
from app.features.imports.models import RawTransaction, RawTransactionStatus
from app.features.imports.parser_types import StatementControlTotals
from app.features.imports.parsers.expobank import ExpobankCardStatementParser
from app.features.imports.parsers.factory import default_statement_parser_registry
from app.features.imports.parsers.normalization import (
    normalize_description,
    parse_bank_date,
    parse_money_amount,
)
from app.features.imports.parsers.sberbank import SberbankCardStatementParser
from app.features.imports.parsers.vtb import VtbCardStatementParser, VtbDepositStatementParser
from app.features.imports.router import review_redirect_url, review_row_anchor
from app.features.imports.service import (
    UploadValidationError,
    document_has_linked_operations,
    mark_raw_transaction_duplicate,
    possible_duplicate_fingerprint,
    raw_transaction_status_for_review_action,
    validate_pdf_upload,
)
from app.features.imports.storage import UploadStorage, sanitize_filename
from app.features.imports.validation import (
    StatementValidationStatus,
    validate_statement_totals,
)


@dataclass(frozen=True)
class RowStub:
    status: RawTransactionStatus
    amount: Decimal | None
    currency: str | None = "RUB"


def test_sanitize_filename_removes_paths_and_unsafe_characters() -> None:
    assert sanitize_filename("../bank statement июнь.pdf") == "bank_statement_.pdf"
    assert sanitize_filename("statement") == "statement.pdf"


@pytest.mark.asyncio
async def test_upload_storage_preserves_pdf_bytes(tmp_path: Path) -> None:
    content = b"%PDF-1.4 local fixture bytes"
    upload = UploadFile(file=BytesIO(content), filename="../statement.pdf")
    workspace_id = uuid4()
    document_id = uuid4()

    stored = await UploadStorage(tmp_path).save_pdf(
        upload,
        workspace_id=workspace_id,
        document_id=document_id,
    )

    assert stored.file_size_bytes == len(content)
    assert stored.sha256_hash == sha256(content).hexdigest()
    assert stored.path.read_bytes() == content
    assert stored.storage_key == f"{workspace_id}/{document_id}/statement.pdf"


def test_validate_pdf_upload_rejects_non_pdf_filename() -> None:
    upload = UploadFile(file=BytesIO(b"not a pdf"), filename="statement.txt")

    with pytest.raises(UploadValidationError):
        validate_pdf_upload(upload)


def test_pdfplumber_extractor_preserves_raw_pages() -> None:
    extracted = PdfPlumberExtractor().extract(Path("tests/fixtures/expobank_statement.pdf"))

    assert extracted.text_by_page
    assert len(extracted.tables_by_page) == len(extracted.text_by_page)
    assert all(page.page_number >= 1 for page in extracted.tables_by_page)


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

    expobank_parser = registry.find_parser(expobank_extracted)
    vtb_parser = registry.find_parser(vtb_extracted)
    vtb_card_parser = registry.find_parser(vtb_card_extracted)
    sberbank_parser = registry.find_parser(sberbank_extracted)

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


def test_statement_validation_report_is_valid_when_totals_match() -> None:
    report = validate_statement_totals(
        rows=[
            RowStub(status=RawTransactionStatus.NORMALIZED, amount=Decimal("100.00")),
            RowStub(status=RawTransactionStatus.NORMALIZED, amount=Decimal("-30.00")),
        ],
        control_totals=StatementControlTotals(
            currency="RUB",
            total_inflow=Decimal("100.00"),
            total_outflow=Decimal("30.00"),
        ),
    )

    assert report.status == StatementValidationStatus.VALID
    assert report.as_json()["status"] == "valid"
    assert report.as_json()["calculated_total_inflow"] == "100.00"


def test_statement_validation_report_detects_mismatched_totals() -> None:
    report = validate_statement_totals(
        rows=[RowStub(status=RawTransactionStatus.NORMALIZED, amount=Decimal("99.00"))],
        control_totals=StatementControlTotals(
            currency="RUB",
            total_inflow=Decimal("100.00"),
            total_outflow=Decimal("0.00"),
        ),
    )

    assert report.status == StatementValidationStatus.MISMATCH
    assert report.as_json()["inflow_difference"] == "-1.00"


def test_statement_validation_report_is_unavailable_without_control_totals() -> None:
    report = validate_statement_totals(
        rows=[RowStub(status=RawTransactionStatus.NORMALIZED, amount=Decimal("99.00"))],
        control_totals=None,
    )

    assert report.status == StatementValidationStatus.UNAVAILABLE
    assert report.as_json()["status"] == "unavailable"


def test_statement_validation_report_needs_review_for_uncertain_rows() -> None:
    report = validate_statement_totals(
        rows=[RowStub(status=RawTransactionStatus.NEEDS_REVIEW, amount=None)],
        control_totals=StatementControlTotals(currency="RUB", total_inflow=Decimal("0.00")),
    )

    assert report.status == StatementValidationStatus.NEEDS_REVIEW
    assert report.as_json()["needs_review_count"] == 1


def test_statement_validation_report_needs_review_for_possible_duplicate_rows() -> None:
    report = validate_statement_totals(
        rows=[RowStub(status=RawTransactionStatus.POSSIBLE_DUPLICATE, amount=Decimal("10.00"))],
        control_totals=StatementControlTotals(currency="RUB", total_inflow=Decimal("10.00")),
    )

    assert report.status == StatementValidationStatus.NEEDS_REVIEW
    assert report.as_json()["needs_review_count"] == 1


def test_raw_transaction_review_actions_map_to_statuses() -> None:
    assert raw_transaction_status_for_review_action("ignore") == RawTransactionStatus.IGNORED
    assert raw_transaction_status_for_review_action("mark_unique") == RawTransactionStatus.MATCHED
    assert (
        raw_transaction_status_for_review_action("needs_review")
        == RawTransactionStatus.NEEDS_REVIEW
    )


def test_possible_duplicate_fingerprint_requires_normalized_fields() -> None:
    account_id = uuid4()
    raw_transaction = raw_transaction_from_values(
        account_id=account_id,
        amount=Decimal("10.00"),
    )

    assert possible_duplicate_fingerprint(raw_transaction) == (
        account_id,
        parse_bank_date("29.05.2026"),
        Decimal("10.00"),
        "RUB",
    )
    raw_transaction.amount = None
    assert possible_duplicate_fingerprint(raw_transaction) is None


def test_mark_raw_transaction_duplicate_preserves_review_message() -> None:
    raw_transaction = raw_transaction_from_values(normalization_error="Existing issue.")

    mark_raw_transaction_duplicate(
        raw_transaction,
        RawTransactionStatus.DUPLICATE,
        "Exact duplicate.",
    )

    assert raw_transaction.status == RawTransactionStatus.DUPLICATE
    assert raw_transaction.normalization_error == "Existing issue.; Exact duplicate."


def test_document_has_linked_operations_detects_confirmed_rows() -> None:
    raw_transaction = raw_transaction_from_values()
    document = RawTransactionDocumentStub(raw_transactions=[raw_transaction])

    assert document_has_linked_operations(document) is False

    raw_transaction.linked_operation_id = uuid4()
    assert document_has_linked_operations(document) is True


def test_review_redirect_url_keeps_user_at_raw_transaction() -> None:
    document_id = uuid4()
    raw_transaction_id = uuid4()

    assert review_row_anchor(raw_transaction_id) == f"raw-{raw_transaction_id}"
    assert review_redirect_url(document_id) == f"/imports/documents/{document_id}/review"
    assert review_redirect_url(document_id, raw_transaction_id) == (
        f"/imports/documents/{document_id}/review#raw-{raw_transaction_id}"
    )


def raw_transaction_from_values(
    *,
    account_id: UUID | None = None,
    amount: Decimal | None = Decimal("10.00"),
    normalization_error: str | None = None,
) -> RawTransaction:
    return RawTransaction(
        workspace_id=uuid4(),
        uploaded_document_id=uuid4(),
        parse_attempt_id=uuid4(),
        row_index=0,
        status=RawTransactionStatus.NORMALIZED,
        raw_payload={},
        account_id=account_id,
        operation_date=parse_bank_date("29.05.2026"),
        amount=amount,
        currency="RUB",
        normalization_error=normalization_error,
    )


@dataclass(frozen=True)
class RawTransactionDocumentStub:
    raw_transactions: list[RawTransaction]
