from fastapi import status

from app.api.errors import ApiError
from app.features.ledger.errors import (
    AccountUnavailableError,
    CategoryUnavailableError,
    InvalidAmountError,
    LedgerPostingError,
    ManualOperationLifecycleConflictError,
    ManualOperationNotEditableError,
    ManualOperationNotFoundError,
    OperationIdempotencyConflictError,
    OperationVersionConflictError,
    PropertyUnavailableError,
    SameTransferAccountError,
    TransferCurrencyMismatchError,
)


def manual_ledger_mutation_error(error: LedgerPostingError) -> ApiError:
    if isinstance(error, ManualOperationNotFoundError):
        return ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="manual_operation_not_found",
            message="Ручная операция не найдена.",
        )
    if isinstance(error, OperationVersionConflictError):
        return ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="operation_version_conflict",
            message="Операция уже изменилась в другом окне.",
        )
    if isinstance(error, ManualOperationLifecycleConflictError):
        return ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="operation_state_conflict",
            message="Состояние операции уже изменилось. Обновите список.",
        )
    if isinstance(error, OperationIdempotencyConflictError):
        return ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="idempotency_conflict",
            message="Этот ключ повтора уже использован для другой операции.",
        )
    details = {
        AccountUnavailableError: (
            "account_unavailable",
            "Выбранный счёт недоступен в этом workspace.",
            "accountId",
        ),
        CategoryUnavailableError: (
            "category_unavailable",
            "Выбранная категория недоступна в этом workspace.",
            "categoryId",
        ),
        PropertyUnavailableError: (
            "property_unavailable",
            "Выбранный объект недоступен в этом workspace.",
            "propertyId",
        ),
        InvalidAmountError: (
            "invalid_amount",
            "Сумма должна быть больше нуля.",
            "amount",
        ),
        SameTransferAccountError: (
            "same_transfer_account",
            "Счета отправления и назначения должны отличаться.",
            "destinationAccountId",
        ),
        TransferCurrencyMismatchError: (
            "transfer_currency_mismatch",
            "Для перевода выберите счета в одной валюте.",
            "destinationAccountId",
        ),
        ManualOperationNotEditableError: (
            "operation_not_editable",
            "Операцию в текущем состоянии нельзя редактировать.",
            "form",
        ),
    }.get(type(error))
    if details is None:
        return ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="manual_operation_rejected",
            message="Не удалось сохранить операцию. Проверьте значения и повторите.",
        )
    code, message, field = details
    return ApiError(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code=code,
        message=message,
        field_errors={field: [message]},
    )
