import pytest
from fastapi import status

from app.api.v1.manual_ledger.mutation_errors import manual_ledger_mutation_error
from app.features.ledger.errors import (
    AccountUnavailableError,
    CategoryUnavailableError,
    InvalidAmountError,
    LedgerPostingError,
    ManualOperationNotEditableError,
    PropertyUnavailableError,
    SameTransferAccountError,
    TransferCurrencyMismatchError,
)


@pytest.mark.parametrize(
    ("error", "code", "field"),
    [
        (AccountUnavailableError(), "account_unavailable", "accountId"),
        (CategoryUnavailableError(), "category_unavailable", "categoryId"),
        (PropertyUnavailableError(), "property_unavailable", "propertyId"),
        (InvalidAmountError(), "invalid_amount", "amount"),
        (SameTransferAccountError(), "same_transfer_account", "destinationAccountId"),
        (
            TransferCurrencyMismatchError(),
            "transfer_currency_mismatch",
            "destinationAccountId",
        ),
        (ManualOperationNotEditableError(), "operation_not_editable", "form"),
    ],
)
def test_expected_ledger_errors_have_stable_api_codes_and_fields(
    error: LedgerPostingError,
    code: str,
    field: str,
) -> None:
    api_error = manual_ledger_mutation_error(error)

    assert api_error.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert api_error.code == code
    assert api_error.field_errors is not None
    assert field in api_error.field_errors


def test_unknown_ledger_error_uses_safe_fallback() -> None:
    api_error = manual_ledger_mutation_error(LedgerPostingError("internal detail"))

    assert api_error.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert api_error.code == "manual_operation_rejected"
    assert api_error.field_errors is None
