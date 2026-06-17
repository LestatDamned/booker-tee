from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.features.imports.models import RawTransactionStatus
from app.features.ledger.models import OperationType
from app.features.transaction_rules.domain.text import normalized_text
from app.features.transaction_rules.models import (
    MoneyDirection,
    TransactionRuleApplicationMode,
    TransactionRuleMatchType,
)


class RuleMatchCandidate(Protocol):
    workspace_id: UUID
    account_id: UUID | None
    amount: Decimal | None
    description_normalized: str | None
    description_raw: str | None


class RuleSuggestion(Protocol):
    id: UUID
    name: str
    pattern: str
    application_mode: TransactionRuleApplicationMode
    match_type: TransactionRuleMatchType
    direction: MoneyDirection
    account_id: UUID | None
    amount_min: Decimal | None
    amount_max: Decimal | None
    workspace_id: UUID
    category_id: UUID | None
    property_id: UUID | None
    target_operation_type: OperationType | None


class RuleApplicationTarget(RuleMatchCandidate, Protocol):
    status: RawTransactionStatus
    linked_operation_id: UUID | None
    raw_payload: dict[str, object]
    suggested_category_id: UUID | None
    suggested_property_id: UUID | None
    suggested_operation_type: OperationType | None
    suggested_by_rule_id: UUID | None


RULE_SUGGESTABLE_STATUSES = {
    RawTransactionStatus.NORMALIZED,
    RawTransactionStatus.SUGGESTED,
    RawTransactionStatus.MATCHED,
    RawTransactionStatus.NEEDS_REVIEW,
    RawTransactionStatus.POSSIBLE_DUPLICATE,
}


def rule_matches_raw_transaction(
    rule: RuleSuggestion,
    raw_transaction: RuleMatchCandidate,
) -> bool:
    if raw_transaction.workspace_id != rule.workspace_id:
        return False
    if rule.account_id is not None and raw_transaction.account_id != rule.account_id:
        return False
    if not direction_matches(rule.direction, raw_transaction.amount):
        return False
    if not amount_matches(rule, raw_transaction.amount):
        return False

    description = normalized_text(
        raw_transaction.description_normalized or raw_transaction.description_raw
    )
    pattern = normalized_text(rule.pattern)
    if not description or not pattern:
        return False
    if rule.match_type == TransactionRuleMatchType.EXACT:
        return description == pattern
    return pattern in description


def can_suggest_raw_transaction(raw_transaction: RuleApplicationTarget) -> bool:
    return (
        raw_transaction.linked_operation_id is None
        and raw_transaction.status in RULE_SUGGESTABLE_STATUSES
    )


def direction_matches(direction: MoneyDirection, amount: Decimal | None) -> bool:
    if direction == MoneyDirection.ANY:
        return True
    if amount is None:
        return False
    if direction == MoneyDirection.INFLOW:
        return amount > Decimal("0.00")
    return amount < Decimal("0.00")


def amount_matches(rule: RuleSuggestion, amount: Decimal | None) -> bool:
    if amount is None:
        return rule.amount_min is None and rule.amount_max is None
    absolute_amount = abs(amount)
    if rule.amount_min is not None and absolute_amount < rule.amount_min:
        return False
    if rule.amount_max is not None and absolute_amount > rule.amount_max:
        return False
    return True


def direction_for_raw_transaction(raw_transaction: RuleMatchCandidate) -> MoneyDirection:
    if raw_transaction.amount is None:
        return MoneyDirection.ANY
    if raw_transaction.amount > Decimal("0.00"):
        return MoneyDirection.INFLOW
    if raw_transaction.amount < Decimal("0.00"):
        return MoneyDirection.OUTFLOW
    return MoneyDirection.ANY


def operation_type_for_raw_transaction(
    raw_transaction: RuleMatchCandidate,
) -> OperationType | None:
    if raw_transaction.amount is None:
        return None
    if raw_transaction.amount > Decimal("0.00"):
        return OperationType.INCOME
    if raw_transaction.amount < Decimal("0.00"):
        return OperationType.EXPENSE
    return None
