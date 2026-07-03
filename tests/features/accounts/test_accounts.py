from decimal import Decimal

import pytest

from app.features.accounts.service import AccountError, normalize_currency


def test_normalize_currency_uppercases_three_letter_code() -> None:
    assert normalize_currency("rub") == "RUB"


def test_normalize_currency_rejects_invalid_code() -> None:
    with pytest.raises(AccountError):
        normalize_currency("rouble")


def test_decimal_initial_balance_can_be_quantized_without_float() -> None:
    assert Decimal("10").quantize(Decimal("0.01")) == Decimal("10.00")
