from fastapi import status

from app.api.errors import ApiError
from app.features.transaction_rules.errors import (
    TransactionRuleCreateReplayConflictError,
    TransactionRuleValidationError,
)


def transaction_rule_api_error(error: Exception) -> ApiError:
    if isinstance(error, TransactionRuleCreateReplayConflictError):
        return ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="transaction_rule_create_replay_conflict",
            message="Этот ключ повтора уже использован для другого правила.",
        )
    if isinstance(error, TransactionRuleValidationError):
        message = str(error)
        return ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="transaction_rule_validation_error",
            message=message,
            field_errors={error.field: [message]} if error.field else None,
        )
    raise error
