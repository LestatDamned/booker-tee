from dataclasses import dataclass
from decimal import Decimal
from typing import cast

from app.features.imports.statements.dto import StatementControlTotals
from app.features.imports.statements.types import RawTransactionStatus
from app.features.imports.statements.validation import (
    StatementValidationStatus,
    validate_statement_totals,
)


@dataclass(frozen=True)
class RowStub:
    status: RawTransactionStatus
    amount: Decimal | None
    currency: str | None = "RUB"
    balance_after: Decimal | None = None


def test_statement_control_totals_validate_stored_json_and_serialize_money() -> None:
    totals = StatementControlTotals.model_validate(
        {
            "currency": "RUB",
            "opening_balance": "100",
            "closing_balance": "125.5",
            "mapping_sources": {"opening_balance": {"row_index": 1}},
        }
    )

    assert totals.opening_balance == Decimal("100")
    assert totals.model_dump(mode="json") == {
        "currency": "RUB",
        "opening_balance": "100.00",
        "closing_balance": "125.50",
        "total_inflow": None,
        "total_outflow": None,
    }


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
    assert report.model_dump(mode="json")["status"] == "valid"
    assert report.model_dump(mode="json")["calculated_total_inflow"] == "100.00"


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
    assert report.model_dump(mode="json")["inflow_difference"] == "-1.00"


def test_statement_validation_report_explains_ignored_rows_separately() -> None:
    report = validate_statement_totals(
        rows=[
            RowStub(status=RawTransactionStatus.CONFIRMED, amount=Decimal("50.00")),
            RowStub(status=RawTransactionStatus.IGNORED, amount=Decimal("50.00")),
            RowStub(status=RawTransactionStatus.CONFIRMED, amount=Decimal("-20.00")),
            RowStub(status=RawTransactionStatus.IGNORED, amount=Decimal("-30.00")),
        ],
        control_totals=StatementControlTotals(
            currency="RUB",
            total_inflow=Decimal("100.00"),
            total_outflow=Decimal("50.00"),
        ),
    )

    payload = report.model_dump(mode="json")
    assert report.status == StatementValidationStatus.MISMATCH
    assert payload["calculated_total_inflow"] == "50.00"
    assert payload["ignored_total_inflow"] == "50.00"
    assert payload["inflow_difference"] == "-50.00"
    assert payload["unexplained_inflow_difference"] == "0.00"
    assert payload["calculated_total_outflow"] == "20.00"
    assert payload["ignored_total_outflow"] == "30.00"
    assert payload["outflow_difference"] == "-30.00"
    assert payload["unexplained_outflow_difference"] == "0.00"


def test_statement_validation_report_is_unavailable_without_control_totals() -> None:
    report = validate_statement_totals(
        rows=[RowStub(status=RawTransactionStatus.NORMALIZED, amount=Decimal("99.00"))],
        control_totals=None,
    )

    assert report.status == StatementValidationStatus.UNAVAILABLE
    assert report.model_dump(mode="json")["status"] == "unavailable"


def test_statement_validation_report_checks_ascending_balance_chain() -> None:
    report = validate_statement_totals(
        rows=[
            RowStub(
                status=RawTransactionStatus.NORMALIZED,
                amount=Decimal("100.00"),
                balance_after=Decimal("1100.00"),
            ),
            RowStub(
                status=RawTransactionStatus.NORMALIZED,
                amount=Decimal("-30.00"),
                balance_after=Decimal("1070.00"),
            ),
        ],
        control_totals=None,
    )

    balance_chain = cast(
        dict[str, object],
        report.model_dump(mode="json")["balance_chain"],
    )
    assert report.status == StatementValidationStatus.UNAVAILABLE
    assert balance_chain["status"] == "valid"
    assert balance_chain["direction"] == "ascending"
    assert balance_chain["checked_pair_count"] == 1


def test_statement_validation_report_checks_descending_balance_chain() -> None:
    report = validate_statement_totals(
        rows=[
            RowStub(
                status=RawTransactionStatus.NORMALIZED,
                amount=Decimal("-30.00"),
                balance_after=Decimal("1070.00"),
            ),
            RowStub(
                status=RawTransactionStatus.NORMALIZED,
                amount=Decimal("100.00"),
                balance_after=Decimal("1100.00"),
            ),
        ],
        control_totals=None,
    )

    balance_chain = cast(
        dict[str, object],
        report.model_dump(mode="json")["balance_chain"],
    )
    assert report.status == StatementValidationStatus.UNAVAILABLE
    assert balance_chain["status"] == "valid"
    assert balance_chain["direction"] == "descending"


def test_statement_validation_report_detects_balance_chain_mismatch() -> None:
    report = validate_statement_totals(
        rows=[
            RowStub(
                status=RawTransactionStatus.NORMALIZED,
                amount=Decimal("100.00"),
                balance_after=Decimal("1100.00"),
            ),
            RowStub(
                status=RawTransactionStatus.NORMALIZED,
                amount=Decimal("-30.00"),
                balance_after=Decimal("1060.00"),
            ),
        ],
        control_totals=None,
    )

    balance_chain = cast(
        dict[str, object],
        report.model_dump(mode="json")["balance_chain"],
    )
    mismatches = cast(list[dict[str, object]], balance_chain["mismatches"])
    assert report.status == StatementValidationStatus.MISMATCH
    assert (
        report.model_dump(mode="json")["message"]
        == "Остатки после операций не совпадают с суммами строк."
    )
    assert balance_chain["status"] == "mismatch"
    assert balance_chain["mismatch_count"] == 1
    assert mismatches[0]["expected_balance_after"] == "1070.00"
    assert mismatches[0]["actual_balance_after"] == "1060.00"


def test_statement_validation_report_needs_review_for_uncertain_rows() -> None:
    report = validate_statement_totals(
        rows=[RowStub(status=RawTransactionStatus.NEEDS_REVIEW, amount=None)],
        control_totals=StatementControlTotals(currency="RUB", total_inflow=Decimal("0.00")),
    )

    assert report.status == StatementValidationStatus.NEEDS_REVIEW
    assert report.model_dump(mode="json")["needs_review_count"] == 1


def test_statement_validation_report_needs_review_for_possible_duplicate_rows() -> None:
    report = validate_statement_totals(
        rows=[RowStub(status=RawTransactionStatus.POSSIBLE_DUPLICATE, amount=Decimal("10.00"))],
        control_totals=StatementControlTotals(currency="RUB", total_inflow=Decimal("10.00")),
    )

    assert report.status == StatementValidationStatus.NEEDS_REVIEW
    assert report.model_dump(mode="json")["needs_review_count"] == 1
