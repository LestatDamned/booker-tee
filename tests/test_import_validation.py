from dataclasses import dataclass
from decimal import Decimal
from typing import cast

from app.features.imports.domain.validation import (
    StatementValidationStatus,
    validate_statement_totals,
)
from app.features.imports.models import RawTransactionStatus
from app.features.imports.parsing.parser_types import StatementControlTotals
from app.features.imports.presentation.review import balance_chain_problem_messages


@dataclass(frozen=True)
class RowStub:
    status: RawTransactionStatus
    amount: Decimal | None
    currency: str | None = "RUB"
    balance_after: Decimal | None = None


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

    balance_chain = cast(dict[str, object], report.as_json()["balance_chain"])
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

    balance_chain = cast(dict[str, object], report.as_json()["balance_chain"])
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

    balance_chain = cast(dict[str, object], report.as_json()["balance_chain"])
    mismatches = cast(list[dict[str, object]], balance_chain["mismatches"])
    assert report.status == StatementValidationStatus.MISMATCH
    assert report.as_json()["message"] == "Остатки после операций не совпадают с суммами строк."
    assert balance_chain["status"] == "mismatch"
    assert balance_chain["mismatch_count"] == 1
    assert mismatches[0]["expected_balance_after"] == "1070.00"
    assert mismatches[0]["actual_balance_after"] == "1060.00"


def test_balance_chain_problem_messages_point_to_affected_rows() -> None:
    messages = balance_chain_problem_messages(
        {
            "balance_chain": {
                "mismatches": [
                    {
                        "row_index": 1,
                        "expected_balance_after": "1070.00",
                        "actual_balance_after": "1060.00",
                    }
                ]
            }
        }
    )

    assert messages == {1: ["остаток не сходится: ожидалось 1070.00, в строке 1060.00"]}


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
