from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from app.features.import_review.application.review import build_import_review_validation
from app.features.import_review.schemas.review import ImportReviewValidationReasonCode
from app.features.imports.models import UploadedDocument
from app.features.imports.statements.types import RawTransactionStatus
from app.features.imports.statements.validation import StatementValidationStatus


def test_validation_reports_unavailable_control_totals() -> None:
    validation = build_validation(
        rows=[row(1, amount="100.00")],
        control_totals=None,
    )

    assert validation.status is StatementValidationStatus.UNAVAILABLE
    assert validation.reason_code is ImportReviewValidationReasonCode.CONTROL_TOTALS_UNAVAILABLE


def test_validation_reports_rows_needing_review_before_totals() -> None:
    validation = build_validation(
        rows=[row(1, amount="100.00", status=RawTransactionStatus.NEEDS_REVIEW)],
        control_totals={"currency": "RUB", "total_inflow": "100.00"},
    )

    assert validation.status is StatementValidationStatus.NEEDS_REVIEW
    assert validation.reason_code is ImportReviewValidationReasonCode.ROWS_NEED_REVIEW
    assert validation.needs_review_count == 1


def test_validation_distinguishes_unexplained_and_ignored_mismatch() -> None:
    unexplained = build_validation(
        rows=[row(1, amount="100.00")],
        control_totals={"currency": "RUB", "total_inflow": "110.00"},
    )
    explained = build_validation(
        rows=[
            row(1, amount="100.00"),
            row(2, amount="10.00", status=RawTransactionStatus.IGNORED),
        ],
        control_totals={"currency": "RUB", "total_inflow": "110.00"},
    )

    assert unexplained.reason_code is ImportReviewValidationReasonCode.CONTROL_TOTALS_MISMATCH
    assert explained.reason_code is ImportReviewValidationReasonCode.IGNORED_ROWS_EXPLAIN_MISMATCH
    assert explained.ignored_total_inflow == Decimal("10.00")
    assert explained.unexplained_inflow_difference == Decimal("0.00")


def test_balance_chain_problem_maps_positions_to_stable_item_ids() -> None:
    first = row(10, amount="100.00", balance_after="100.00")
    second = row(20, amount="50.00", balance_after="170.00")

    validation = build_validation(
        rows=[first, second],
        control_totals={"currency": "RUB", "total_inflow": "150.00"},
    )

    assert validation.reason_code is ImportReviewValidationReasonCode.BALANCE_CHAIN_MISMATCH
    assert validation.balance_chain.mismatch_count == 1
    assert len(validation.row_problems) == 1
    problem = validation.row_problems[0]
    assert problem.item_id == second.id
    assert problem.previous_item_id == first.id
    assert problem.row_index == 20
    assert problem.previous_row_index == 10
    assert problem.expected_balance_after == Decimal("150.00")
    assert problem.actual_balance_after == Decimal("170.00")


def test_validation_uses_latest_parse_attempt_by_started_at() -> None:
    now = datetime.now(UTC)
    document = SimpleNamespace(
        raw_transactions=[row(1, amount="100.00")],
        parse_attempts=[
            SimpleNamespace(
                started_at=now - timedelta(minutes=1),
                control_totals_json={"currency": "RUB", "total_inflow": "90.00"},
            ),
            SimpleNamespace(
                started_at=now,
                control_totals_json={"currency": "RUB", "total_inflow": "100.00"},
            ),
        ],
    )

    validation = build_import_review_validation(
        cast(UploadedDocument, cast(Any, document)),
    )

    assert validation is not None
    assert validation.statement_total_inflow == Decimal("100.00")
    assert validation.status is StatementValidationStatus.VALID


def build_validation(
    *,
    rows: list[SimpleNamespace],
    control_totals: dict[str, object] | None,
):
    document = SimpleNamespace(
        raw_transactions=rows,
        parse_attempts=[
            SimpleNamespace(
                started_at=datetime.now(UTC),
                control_totals_json=control_totals,
            )
        ],
    )
    validation = build_import_review_validation(cast(UploadedDocument, cast(Any, document)))
    assert validation is not None
    return validation


def row(
    row_index: int,
    *,
    amount: str,
    status: RawTransactionStatus = RawTransactionStatus.MATCHED,
    balance_after: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        row_index=row_index,
        status=status,
        amount=Decimal(amount),
        currency="RUB",
        balance_after=(Decimal(balance_after) if balance_after is not None else None),
    )


@pytest.mark.parametrize(
    ("opening", "closing", "ignored", "expected", "difference", "status"),
    [
        ("0.00", "100.01", None, "100.01", "0.00", "match"),
        ("-150.00", "-49.99", None, "-49.99", "0.00", "match"),
        ("0.00", "100.00", None, "100.01", "0.01", "mismatch"),
        ("120000.00", "120090.01", "-10.00", "120100.01", "10.00", "explained"),
        ("0.00", "110.01", "10.00", "100.01", "-10.00", "explained"),
        ("0.00", "110.02", "10.00", "100.01", "-10.01", "mismatch"),
        (None, "100.01", None, None, None, "unavailable"),
        ("0.00", None, None, "100.01", None, "unavailable"),
    ],
)
def test_statement_balance_comparison(opening, closing, ignored, expected, difference, status):
    rows = [row(1, amount="100.01")]
    if ignored is not None:
        rows.append(row(2, amount=ignored, status=RawTransactionStatus.IGNORED))
    validation = build_validation(
        rows=rows,
        control_totals={"currency": "RUB", "opening_balance": opening, "closing_balance": closing},
    )
    assert validation.calculated_closing_balance == (Decimal(expected) if expected else None)
    assert validation.balance_difference == (Decimal(difference) if difference else None)
    assert validation.balance_status == status


@pytest.mark.parametrize("problem", ["review", "failed", "ignored_missing_amount", "currency"])
def test_statement_balance_does_not_claim_success_with_incomplete_rows(problem):
    item = row(1, amount="100.00")
    if problem == "review":
        item.status = RawTransactionStatus.NEEDS_REVIEW
    elif problem == "failed":
        item.status = RawTransactionStatus.FAILED
    elif problem == "ignored_missing_amount":
        item.status = RawTransactionStatus.IGNORED
        item.amount = None
    else:
        item.currency = "USD"
    validation = build_validation(
        rows=[item],
        control_totals={"currency": "RUB", "opening_balance": "0.00", "closing_balance": "100.00"},
    )
    assert validation.calculated_closing_balance is None
    assert validation.balance_difference is None
    assert validation.balance_status == ("unavailable" if problem == "currency" else "needs_review")
