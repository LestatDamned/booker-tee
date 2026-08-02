from fastapi import status

from app.api.errors import ApiError
from app.features.transaction_rules.errors import (
    TransactionRuleActivationBlockedError,
    TransactionRuleCreateReplayConflictError,
    TransactionRuleLifecycleConflictError,
    TransactionRuleNotFoundError,
    TransactionRuleUpdateConflictError,
    TransactionRuleValidationError,
)


def transaction_rule_api_error(error: Exception) -> ApiError:
    if isinstance(error, TransactionRuleNotFoundError):
        return ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="transaction_rule_not_found",
            message="Правило не найдено.",
        )
    if isinstance(error, TransactionRuleUpdateConflictError):
        return ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="transaction_rule_update_conflict",
            message="Правило уже изменилось в другом окне.",
        )
    if isinstance(error, TransactionRuleLifecycleConflictError):
        return ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="transaction_rule_lifecycle_conflict",
            message=str(error),
        )
    if isinstance(error, TransactionRuleActivationBlockedError):
        reason_by_field = {
            "categoryId": "category_inactive",
            "propertyId": "property_archived",
            "accountId": "account_unavailable",
        }
        message = str(error)
        return ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="transaction_rule_activation_blocked",
            message=message,
            field_errors={error.field: [message]} if error.field else None,
            details={
                "blockedReasonCode": reason_by_field.get(error.field),
            },
        )
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
