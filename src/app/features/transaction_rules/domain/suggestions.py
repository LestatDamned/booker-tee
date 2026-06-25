from app.features.imports.models import RawTransactionStatus
from app.features.transaction_rules.domain.matching import (
    RuleApplicationTarget,
    RuleSuggestion,
)
from app.features.transaction_rules.models import TransactionRuleApplicationMode


def apply_rule_suggestion(
    raw_transaction: RuleApplicationTarget,
    rule: RuleSuggestion,
) -> None:
    raw_transaction.suggested_category_id = rule.category_id
    raw_transaction.suggested_property_id = rule.property_id
    raw_transaction.suggested_operation_type = rule.target_operation_type
    raw_transaction.suggested_by_rule_id = rule.id
    raw_transaction.raw_payload = {
        **(raw_transaction.raw_payload or {}),
        "rule_suggestion": {
            "rule_id": str(rule.id),
            "rule_name": rule.name,
            "pattern": rule.pattern,
            "application_mode": rule.application_mode.value,
            "category_id": str(rule.category_id) if rule.category_id else None,
            "property_id": str(rule.property_id) if rule.property_id else None,
            "operation_type": rule.target_operation_type.value
            if rule.target_operation_type
            else None,
        },
    }
    if raw_transaction.status == RawTransactionStatus.NORMALIZED:
        raw_transaction.status = RawTransactionStatus.SUGGESTED


def clear_rule_suggestion(raw_transaction: RuleApplicationTarget) -> None:
    raw_transaction.suggested_category_id = None
    raw_transaction.suggested_property_id = None
    raw_transaction.suggested_operation_type = None
    raw_transaction.suggested_by_rule_id = None
    payload = dict(raw_transaction.raw_payload or {})
    payload.pop("rule_suggestion", None)
    raw_transaction.raw_payload = payload
    if raw_transaction.status == RawTransactionStatus.SUGGESTED:
        raw_transaction.status = RawTransactionStatus.NORMALIZED


def rule_suggestion_auto_applies(raw_transaction: RuleApplicationTarget) -> bool:
    suggestion = (raw_transaction.raw_payload or {}).get("rule_suggestion")
    if not isinstance(suggestion, dict):
        return False
    return suggestion.get("application_mode") == TransactionRuleApplicationMode.AUTO_APPLY.value
