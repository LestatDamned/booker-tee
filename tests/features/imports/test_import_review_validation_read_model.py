from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from app.features.import_review.application.validation_read_model import (
    ImportReviewValidationReasonCode,
    build_import_review_validation,
)
from app.features.imports.domain.types import RawTransactionStatus
from app.features.imports.domain.validation import StatementValidationStatus
from app.features.imports.models import UploadedDocument


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
