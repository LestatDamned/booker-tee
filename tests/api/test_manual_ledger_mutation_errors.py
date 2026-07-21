import pytest
from fastapi import status

from app.api.v1.manual_ledger.mutation_errors import manual_operation_api_error
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
    ],
)
def test_expected_ledger_errors_have_stable_api_codes_and_fields(
    error: LedgerPostingError,
    code: str,
    field: str,
) -> None:
    api_error = manual_operation_api_error(error)

    assert api_error.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert api_error.code == code
    assert api_error.field_errors is not None
    assert field in api_error.field_errors


def test_not_editable_error_is_a_state_conflict() -> None:
    api_error = manual_operation_api_error(ManualOperationNotEditableError())

    assert api_error.status_code == status.HTTP_409_CONFLICT
    assert api_error.code == "operation_not_editable"
    assert api_error.field_errors is None


def test_unknown_ledger_error_is_not_masked_as_validation_error() -> None:
    with pytest.raises(LedgerPostingError, match="internal detail"):
        manual_operation_api_error(LedgerPostingError("internal detail"))
