from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.features.import_review.domain.classification import (
    ReviewBlockingReasonCode,
    ReviewClassificationSource,
    ReviewConfirmabilityInput,
    evaluate_review_confirmability,
    resolve_review_classification,
)
from app.features.imports.statements.types import RawTransactionStatus
from app.features.ledger.domain.types import OperationType


@pytest.mark.parametrize(
    ("explicit", "suggested", "amount", "expected_type", "expected_source"),
    [
        (
            OperationType.INCOME,
            OperationType.EXPENSE,
            Decimal("-10.00"),
            OperationType.INCOME,
            ReviewClassificationSource.EXPLICIT,
        ),
        (
            None,
            OperationType.INCOME,
            Decimal("-10.00"),
            OperationType.INCOME,
            ReviewClassificationSource.SUGGESTED,
        ),
        (
            None,
            None,
            Decimal("10.00"),
            OperationType.INCOME,
            ReviewClassificationSource.INFERRED,
        ),
        (
            None,
            None,
            Decimal("-10.00"),
            OperationType.EXPENSE,
            ReviewClassificationSource.INFERRED,
        ),
        (None, None, Decimal("0.00"), None, ReviewClassificationSource.UNKNOWN),
    ],
)
def test_classification_priority(
    explicit: OperationType | None,
    suggested: OperationType | None,
    amount: Decimal,
    expected_type: OperationType | None,
    expected_source: ReviewClassificationSource,
) -> None:
    classification = resolve_review_classification(
        explicit_operation_type=explicit,
        suggested_operation_type=suggested,
        amount=amount,
    )

    assert classification.operation_type is expected_type
    assert classification.source is expected_source


@pytest.mark.parametrize(
    ("has_category", "is_uncategorized", "expected_reasons"),
    [
        (False, False, (ReviewBlockingReasonCode.MISSING_CATEGORY,)),
        (True, True, (ReviewBlockingReasonCode.UNCATEGORIZED_CATEGORY,)),
        (True, False, ()),
    ],
    ids=("missing", "uncategorized", "categorized"),
)
def test_income_expense_requires_real_category(
    has_category: bool,
    is_uncategorized: bool,
    expected_reasons: tuple[ReviewBlockingReasonCode, ...],
) -> None:
    classification = resolve_review_classification(
        explicit_operation_type=OperationType.EXPENSE,
        suggested_operation_type=None,
        amount=Decimal("-10.00"),
    )

    result = evaluate_review_confirmability(
        facts(
            classification,
            category_id=uuid4() if has_category else None,
            category_is_uncategorized=is_uncategorized,
        )
    )

    assert result.blocking_reason_codes == expected_reasons
    assert result.can_confirm is (not bool(expected_reasons))


@pytest.mark.parametrize(
    ("status", "expected_reasons"),
    [
        (RawTransactionStatus.SUGGESTED, ()),
        (
            RawTransactionStatus.POSSIBLE_DUPLICATE,
            (ReviewBlockingReasonCode.DUPLICATE_REVIEW_REQUIRED,),
        ),
    ],
    ids=("suggested", "possible-duplicate"),
)
def test_review_status_controls_confirmability(
    status: RawTransactionStatus,
    expected_reasons: tuple[ReviewBlockingReasonCode, ...],
) -> None:
    classification = resolve_review_classification(
        explicit_operation_type=None,
        suggested_operation_type=OperationType.EXPENSE,
        amount=Decimal("-10.00"),
    )

    result = evaluate_review_confirmability(
        facts(
            classification,
            category_id=uuid4(),
            status=status,
        )
    )

    assert result.blocking_reason_codes == expected_reasons
    assert result.can_confirm is (not bool(expected_reasons))


@pytest.mark.parametrize(
    ("operation_type", "amount"),
    [
        (OperationType.INCOME, Decimal("-10.00")),
        (OperationType.EXPENSE, Decimal("10.00")),
    ],
    ids=("income-with-outflow", "expense-with-inflow"),
)
def test_explicit_income_expense_must_match_normalized_amount_sign(
    operation_type: OperationType,
    amount: Decimal,
) -> None:
    classification = resolve_review_classification(
        explicit_operation_type=operation_type,
        suggested_operation_type=None,
        amount=amount,
    )

    result = evaluate_review_confirmability(
        facts(classification, category_id=uuid4(), amount=amount)
    )

    assert result.blocking_reason_codes == (
        ReviewBlockingReasonCode.OPERATION_TYPE_AMOUNT_MISMATCH,
    )


def facts(
    classification,
    *,
    category_id=None,
    category_is_uncategorized: bool = False,
    status: RawTransactionStatus = RawTransactionStatus.MATCHED,
    amount: Decimal = Decimal("-10.00"),
) -> ReviewConfirmabilityInput:
    return ReviewConfirmabilityInput(
        status=status,
        normalization_error=None,
        operation_date=date(2026, 7, 21),
        operation_date_raw=None,
        amount=amount,
        currency="RUB",
        source_account_id=uuid4(),
        counterparty_account_id=None,
        classification=classification,
        category_id=category_id,
        category_is_uncategorized=category_is_uncategorized,
    )
