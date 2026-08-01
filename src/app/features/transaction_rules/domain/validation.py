from dataclasses import dataclass
from decimal import Decimal

from app.features.ledger.models import OperationType
from app.features.transaction_rules.domain.text import (
    build_rule_name,
    clean_description,
    clean_rule_name,
    normalized_text,
)
from app.features.transaction_rules.errors import TransactionRuleValidationError
from app.features.transaction_rules.models import TransactionRuleMatchType

RULE_TEXT_MAX_LENGTH = 255
RULE_AMOUNT_MAX = Decimal("999999999999.99")


@dataclass(frozen=True)
class ValidatedTransactionRuleFields:
    name: str
    pattern: str
    amount_min: Decimal | None
    amount_max: Decimal | None
    auto_description: str | None


def validate_transaction_rule_fields(
    *,
    name: str | None,
    pattern: str,
    match_type: TransactionRuleMatchType,
    category_name: str | None,
    target_operation_type: OperationType | None,
    amount_min: Decimal | None,
    amount_max: Decimal | None,
    auto_description: str | None = None,
) -> ValidatedTransactionRuleFields:
    cleaned_pattern = clean_rule_name(pattern)
    if cleaned_pattern is None:
        raise TransactionRuleValidationError("Rule pattern is required.")
    if len(cleaned_pattern) > RULE_TEXT_MAX_LENGTH:
        raise TransactionRuleValidationError("Rule pattern must be 255 characters or fewer.")
    if not normalized_text(cleaned_pattern):
        raise TransactionRuleValidationError("Rule pattern must contain searchable text.")

    cleaned_name = clean_rule_name(name)
    if cleaned_name is not None and len(cleaned_name) > RULE_TEXT_MAX_LENGTH:
        raise TransactionRuleValidationError("Rule name must be 255 characters or fewer.")
    if cleaned_name is None:
        cleaned_name = build_rule_name(
            pattern=cleaned_pattern,
            match_type=match_type,
            category_name=category_name,
            target_operation_type=target_operation_type,
        )[:RULE_TEXT_MAX_LENGTH]

    validate_amount_range(amount_min=amount_min, amount_max=amount_max)
    return ValidatedTransactionRuleFields(
        name=cleaned_name,
        pattern=cleaned_pattern,
        amount_min=amount_min,
        amount_max=amount_max,
        auto_description=clean_description(auto_description),
    )


def validate_amount_range(
    *,
    amount_min: Decimal | None,
    amount_max: Decimal | None,
) -> None:
    for label, amount in (("Minimum amount", amount_min), ("Maximum amount", amount_max)):
        if amount is None:
            continue
        if not amount.is_finite():
            raise TransactionRuleValidationError(f"{label} must be finite.")
        if amount < Decimal("0"):
            raise TransactionRuleValidationError(f"{label} cannot be negative.")
        if amount > RULE_AMOUNT_MAX:
            raise TransactionRuleValidationError(f"{label} is too large.")
        if amount != amount.quantize(Decimal("0.01")):
            raise TransactionRuleValidationError(
                f"{label} must have no more than two decimal places."
            )
    if amount_min is not None and amount_max is not None and amount_min > amount_max:
        raise TransactionRuleValidationError(
            "Minimum amount cannot be greater than maximum amount."
        )
