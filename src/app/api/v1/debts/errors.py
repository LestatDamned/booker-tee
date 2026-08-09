from fastapi import status

from app.api.errors import ApiError
from app.features.accounts.service import AccountError
from app.features.debts.domain import DebtValidationError
from app.features.debts.errors import (
    DebtAccountUnavailableError,
    DebtCurrencyMismatchError,
    DebtDeleteBlockedError,
    DebtError,
    DebtIdempotencyConflictError,
    DebtLifecycleConflictError,
    DebtMaintenanceConflictError,
    DebtNotFoundError,
    DebtPaymentConflictError,
    DebtPaymentNotFoundError,
)
from app.features.ledger.errors import CategoryUnavailableError, LedgerPostingError

EXPECTED_DEBT_ERRORS = (DebtValidationError, DebtError, AccountError, LedgerPostingError)


class DebtApiErrors:
    @staticmethod
    def from_exception(error: Exception) -> ApiError:
        if isinstance(error, (DebtNotFoundError, DebtPaymentNotFoundError)):
            return ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="debt_not_found",
                message="Долг или платёж не найден.",
            )
        if isinstance(error, DebtIdempotencyConflictError):
            return ApiError(
                status_code=status.HTTP_409_CONFLICT,
                code="idempotency_conflict",
                message="Ключ повтора уже использован с другими данными.",
            )
        if isinstance(error, DebtPaymentConflictError):
            return ApiError(
                status_code=status.HTTP_409_CONFLICT,
                code="debt_payment_conflict",
                message="Платёж уже изменился. Обновите карточку долга.",
            )
        if isinstance(error, DebtLifecycleConflictError):
            return ApiError(
                status_code=status.HTTP_409_CONFLICT,
                code="debt_state_conflict",
                message="Состояние долга изменилось. Обновите карточку.",
            )
        if isinstance(error, DebtMaintenanceConflictError):
            return ApiError(
                status_code=status.HTTP_409_CONFLICT,
                code="debt_state_conflict",
                message="Долг изменился. Обновите карточку.",
            )
        if isinstance(error, DebtDeleteBlockedError):
            return ApiError(
                status_code=status.HTTP_409_CONFLICT,
                code="debt_has_financial_history",
                message="Долг с финансовой историей нельзя удалить. Перенесите его в архив.",
            )
        if isinstance(error, CategoryUnavailableError):
            message = "Категория процентов недоступна в этом workspace."
            return ApiError(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="interest_category_unavailable",
                message=message,
                field_errors={"interestCategoryId": [message]},
            )
        if isinstance(error, DebtAccountUnavailableError):
            return ApiError(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="debt_account_unavailable",
                message="Выбранный счёт недоступен в этом workspace.",
            )
        if isinstance(error, DebtCurrencyMismatchError):
            return ApiError(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="debt_currency_mismatch",
                message="Долг и денежный счёт должны иметь одну валюту.",
            )
        if isinstance(error, EXPECTED_DEBT_ERRORS):
            return ApiError(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="debt_validation_error",
                message="Проверьте параметры долга или платежа.",
            )
        raise error
