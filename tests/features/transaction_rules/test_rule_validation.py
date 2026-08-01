from decimal import Decimal

import pytest

from app.features.ledger.models import OperationType
from app.features.transaction_rules.domain.validation import (
    validate_transaction_rule_fields,
)
from app.features.transaction_rules.errors import TransactionRuleValidationError
from app.features.transaction_rules.models import TransactionRuleMatchType


def validate(
    *,
    name: str | None = None,
    pattern: str = "OZON",
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
):
    return validate_transaction_rule_fields(
        name=name,
        pattern=pattern,
        match_type=TransactionRuleMatchType.CONTAINS,
        category_name="Маркетплейсы",
        target_operation_type=OperationType.EXPENSE,
        amount_min=amount_min,
        amount_max=amount_max,
    )


def test_rule_fields_normalize_whitespace_and_build_bounded_name() -> None:
    fields = validate(pattern="  OZON   MARKET  ")

    assert fields.pattern == "OZON MARKET"
    assert fields.name == "OZON MARKET -> Маркетплейсы"


@pytest.mark.parametrize("pattern", ["", "   ", "12345", "*** 123 ***"])
def test_rule_pattern_requires_searchable_text(pattern: str) -> None:
    with pytest.raises(TransactionRuleValidationError):
        validate(pattern=pattern)


def test_rule_pattern_and_explicit_name_reject_oversize_values() -> None:
    with pytest.raises(TransactionRuleValidationError, match="pattern"):
        validate(pattern="x" * 256)
    with pytest.raises(TransactionRuleValidationError, match="name"):
        validate(name="x" * 256)


@pytest.mark.parametrize(
    ("amount_min", "amount_max"),
    [
        (Decimal("-0.01"), None),
        (None, Decimal("-0.01")),
        (Decimal("10.01"), Decimal("10.00")),
        (Decimal("NaN"), None),
        (None, Decimal("Infinity")),
        (Decimal("0.001"), None),
        (None, Decimal("1000000000000.00")),
    ],
)
def test_rule_amount_range_rejects_invalid_bounds(
    amount_min: Decimal | None,
    amount_max: Decimal | None,
) -> None:
    with pytest.raises(TransactionRuleValidationError):
        validate(amount_min=amount_min, amount_max=amount_max)


def test_rule_amount_range_accepts_non_negative_ordered_bounds() -> None:
    fields = validate(amount_min=Decimal("0.00"), amount_max=Decimal("100.00"))

    assert fields.amount_min == Decimal("0.00")
    assert fields.amount_max == Decimal("100.00")
