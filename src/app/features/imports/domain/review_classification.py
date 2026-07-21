from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from app.features.ledger.domain.types import OperationType


class ReviewClassificationSource(StrEnum):
    EXPLICIT = "explicit"
    SUGGESTED = "suggested"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ReviewClassification:
    operation_type: OperationType | None
    source: ReviewClassificationSource


def resolve_review_classification(
    *,
    explicit_operation_type: OperationType | None,
    suggested_operation_type: OperationType | None,
    amount: Decimal | None,
) -> ReviewClassification:
    if explicit_operation_type is not None:
        return ReviewClassification(
            operation_type=explicit_operation_type,
            source=ReviewClassificationSource.EXPLICIT,
        )
    if suggested_operation_type is not None:
        return ReviewClassification(
            operation_type=suggested_operation_type,
            source=ReviewClassificationSource.SUGGESTED,
        )
    if amount is not None and amount > 0:
        return ReviewClassification(
            operation_type=OperationType.INCOME,
            source=ReviewClassificationSource.INFERRED,
        )
    if amount is not None and amount < 0:
        return ReviewClassification(
            operation_type=OperationType.EXPENSE,
            source=ReviewClassificationSource.INFERRED,
        )
    return ReviewClassification(
        operation_type=None,
        source=ReviewClassificationSource.UNKNOWN,
    )
