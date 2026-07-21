from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from app.features.imports.domain.review_classification import ReviewClassification
from app.features.imports.domain.review_queue import is_review_terminal
from app.features.imports.domain.types import RawTransactionStatus
from app.features.ledger.domain.types import OperationType


class ReviewBlockingReasonCode(StrEnum):
    TERMINAL_STATE = "terminal_state"
    FAILED_STATE = "failed_state"
    DUPLICATE_REVIEW_REQUIRED = "duplicate_review_required"
    NORMALIZATION_ERROR = "normalization_error"
    MISSING_OPERATION_DATE = "missing_operation_date"
    MISSING_AMOUNT = "missing_amount"
    MISSING_CURRENCY = "missing_currency"
    MISSING_SOURCE_ACCOUNT = "missing_source_account"
    MISSING_OPERATION_TYPE = "missing_operation_type"
    MISSING_CATEGORY = "missing_category"
    UNCATEGORIZED_CATEGORY = "uncategorized_category"
    TRANSFER_ACCOUNTS_REQUIRED = "transfer_accounts_required"
    SAME_TRANSFER_ACCOUNT = "same_transfer_account"
    UNSUPPORTED_OPERATION_TYPE = "unsupported_operation_type"


@dataclass(frozen=True)
class ReviewConfirmabilityInput:
    status: RawTransactionStatus
    normalization_error: str | None
    operation_date: date | None
    operation_date_raw: str | None
    amount: Decimal | None
    currency: str | None
    source_account_id: UUID | None
    counterparty_account_id: UUID | None
    classification: ReviewClassification
    category_id: UUID | None
    category_is_uncategorized: bool


@dataclass(frozen=True)
class ReviewConfirmability:
    can_confirm: bool
    blocking_reason_codes: tuple[ReviewBlockingReasonCode, ...]


def evaluate_review_confirmability(
    facts: ReviewConfirmabilityInput,
) -> ReviewConfirmability:
    reasons: list[ReviewBlockingReasonCode] = []
    if is_review_terminal(facts.status):
        reasons.append(ReviewBlockingReasonCode.TERMINAL_STATE)
    elif facts.status is RawTransactionStatus.FAILED:
        reasons.append(ReviewBlockingReasonCode.FAILED_STATE)
    elif facts.status is RawTransactionStatus.POSSIBLE_DUPLICATE:
        reasons.append(ReviewBlockingReasonCode.DUPLICATE_REVIEW_REQUIRED)

    if facts.normalization_error:
        reasons.append(ReviewBlockingReasonCode.NORMALIZATION_ERROR)
    if facts.operation_date is None and not facts.operation_date_raw:
        reasons.append(ReviewBlockingReasonCode.MISSING_OPERATION_DATE)
    if facts.amount is None:
        reasons.append(ReviewBlockingReasonCode.MISSING_AMOUNT)
    if not facts.currency:
        reasons.append(ReviewBlockingReasonCode.MISSING_CURRENCY)
    if facts.source_account_id is None:
        reasons.append(ReviewBlockingReasonCode.MISSING_SOURCE_ACCOUNT)

    operation_type = facts.classification.operation_type
    if operation_type is None:
        reasons.append(ReviewBlockingReasonCode.MISSING_OPERATION_TYPE)
    elif operation_type in {OperationType.INCOME, OperationType.EXPENSE}:
        if facts.category_id is None:
            reasons.append(ReviewBlockingReasonCode.MISSING_CATEGORY)
        elif facts.category_is_uncategorized:
            reasons.append(ReviewBlockingReasonCode.UNCATEGORIZED_CATEGORY)
    elif operation_type is OperationType.TRANSFER:
        if facts.source_account_id is None or facts.counterparty_account_id is None:
            reasons.append(ReviewBlockingReasonCode.TRANSFER_ACCOUNTS_REQUIRED)
        elif facts.source_account_id == facts.counterparty_account_id:
            reasons.append(ReviewBlockingReasonCode.SAME_TRANSFER_ACCOUNT)
    else:
        reasons.append(ReviewBlockingReasonCode.UNSUPPORTED_OPERATION_TYPE)

    unique_reasons = tuple(dict.fromkeys(reasons))
    return ReviewConfirmability(
        can_confirm=not unique_reasons,
        blocking_reason_codes=unique_reasons,
    )
