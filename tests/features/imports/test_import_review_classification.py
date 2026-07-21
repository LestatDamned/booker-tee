from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.features.imports.domain.review_classification import (
    ReviewClassificationSource,
    resolve_review_classification,
)
from app.features.imports.domain.review_confirmability import (
    ReviewBlockingReasonCode,
    ReviewConfirmabilityInput,
    evaluate_review_confirmability,
)
from app.features.imports.domain.types import RawTransactionStatus
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


def test_income_expense_requires_real_category() -> None:
    classification = resolve_review_classification(
        explicit_operation_type=OperationType.EXPENSE,
        suggested_operation_type=None,
        amount=Decimal("-10.00"),
    )

    missing = evaluate_review_confirmability(facts(classification, category_id=None))
    uncategorized = evaluate_review_confirmability(
        facts(classification, category_id=uuid4(), category_is_uncategorized=True)
    )
    categorized = evaluate_review_confirmability(facts(classification, category_id=uuid4()))

    assert missing.blocking_reason_codes == (ReviewBlockingReasonCode.MISSING_CATEGORY,)
    assert uncategorized.blocking_reason_codes == (ReviewBlockingReasonCode.UNCATEGORIZED_CATEGORY,)
    assert categorized.can_confirm is True


def test_rule_suggestion_status_does_not_block_but_possible_duplicate_does() -> None:
    classification = resolve_review_classification(
        explicit_operation_type=None,
        suggested_operation_type=OperationType.EXPENSE,
        amount=Decimal("-10.00"),
    )

    suggestion = evaluate_review_confirmability(
        facts(
            classification,
            category_id=uuid4(),
            status=RawTransactionStatus.SUGGESTED,
        )
    )
    duplicate = evaluate_review_confirmability(
        facts(
            classification,
            category_id=uuid4(),
            status=RawTransactionStatus.POSSIBLE_DUPLICATE,
        )
    )

    assert suggestion.can_confirm is True
    assert duplicate.blocking_reason_codes == (ReviewBlockingReasonCode.DUPLICATE_REVIEW_REQUIRED,)


def test_explicit_income_expense_must_match_normalized_amount_sign() -> None:
    income = resolve_review_classification(
        explicit_operation_type=OperationType.INCOME,
        suggested_operation_type=None,
        amount=Decimal("-10.00"),
    )

    result = evaluate_review_confirmability(facts(income, category_id=uuid4()))

    assert result.blocking_reason_codes == (
        ReviewBlockingReasonCode.OPERATION_TYPE_AMOUNT_MISMATCH,
    )


def facts(
    classification,
    *,
    category_id=None,
    category_is_uncategorized: bool = False,
    status: RawTransactionStatus = RawTransactionStatus.MATCHED,
) -> ReviewConfirmabilityInput:
    return ReviewConfirmabilityInput(
        status=status,
        normalization_error=None,
        operation_date=date(2026, 7, 21),
        operation_date_raw=None,
        amount=Decimal("-10.00"),
        currency="RUB",
        source_account_id=uuid4(),
        counterparty_account_id=None,
        classification=classification,
        category_id=category_id,
        category_is_uncategorized=category_is_uncategorized,
    )
