from dataclasses import dataclass

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


@dataclass(frozen=True)
class ManualLedgerApiErrorSpec:
    status_code: int
    code: str
    message: str
    field: str | None = None


MANUAL_LEDGER_API_ERRORS: dict[type[LedgerPostingError], ManualLedgerApiErrorSpec] = {
    ManualOperationNotFoundError: ManualLedgerApiErrorSpec(
        status_code=status.HTTP_404_NOT_FOUND,
        code="manual_operation_not_found",
        message="Ручная операция не найдена.",
    ),
    OperationVersionConflictError: ManualLedgerApiErrorSpec(
        status_code=status.HTTP_409_CONFLICT,
        code="operation_version_conflict",
        message="Операция уже изменилась в другом окне.",
    ),
    ManualOperationLifecycleConflictError: ManualLedgerApiErrorSpec(
        status_code=status.HTTP_409_CONFLICT,
        code="operation_state_conflict",
        message="Состояние операции уже изменилось. Обновите список.",
    ),
    OperationIdempotencyConflictError: ManualLedgerApiErrorSpec(
        status_code=status.HTTP_409_CONFLICT,
        code="idempotency_conflict",
        message="Этот ключ повтора уже использован для другой операции.",
    ),
    AccountUnavailableError: ManualLedgerApiErrorSpec(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="account_unavailable",
        message="Выбранный счёт недоступен в этом workspace.",
        field="accountId",
    ),
    CategoryUnavailableError: ManualLedgerApiErrorSpec(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="category_unavailable",
        message="Выбранная категория недоступна в этом workspace.",
        field="categoryId",
    ),
    PropertyUnavailableError: ManualLedgerApiErrorSpec(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="property_unavailable",
        message="Выбранный объект недоступен в этом workspace.",
        field="propertyId",
    ),
    InvalidAmountError: ManualLedgerApiErrorSpec(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="invalid_amount",
        message="Сумма должна быть больше нуля.",
        field="amount",
    ),
    SameTransferAccountError: ManualLedgerApiErrorSpec(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="same_transfer_account",
        message="Счета отправления и назначения должны отличаться.",
        field="destinationAccountId",
    ),
    TransferCurrencyMismatchError: ManualLedgerApiErrorSpec(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="transfer_currency_mismatch",
        message="Для перевода выберите счета в одной валюте.",
        field="destinationAccountId",
    ),
    ManualOperationNotEditableError: ManualLedgerApiErrorSpec(
        status_code=status.HTTP_409_CONFLICT,
        code="operation_not_editable",
        message="Операцию в текущем состоянии нельзя редактировать.",
    ),
}


def manual_operation_api_error(error: LedgerPostingError) -> ApiError:
    error_spec = MANUAL_LEDGER_API_ERRORS.get(type(error))
    if error_spec is None:
        raise error
    field_errors = (
        {error_spec.field: [error_spec.message]} if error_spec.field is not None else None
    )
    return ApiError(
        status_code=error_spec.status_code,
        code=error_spec.code,
        message=error_spec.message,
        field_errors=field_errors,
    )
