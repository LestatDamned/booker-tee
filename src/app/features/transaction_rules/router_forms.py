from decimal import Decimal
from uuid import UUID

from app.features.ledger.models import OperationType
from app.features.transaction_rules.application.commands import (
    CreateTransactionRuleCommand,
    UpdateTransactionRuleCommand,
)
from app.features.transaction_rules.models import (
    MoneyDirection,
    TransactionRuleApplicationMode,
    TransactionRuleMatchType,
)


def build_create_rule_command(
    *,
    name: str | None,
    pattern: str,
    match_type: TransactionRuleMatchType,
    category_id: str | None,
    property_id: str | None,
    target_operation_type: str | None,
    direction: MoneyDirection,
    application_mode: TransactionRuleApplicationMode,
    amount_min: Decimal | None,
    amount_max: Decimal | None,
) -> CreateTransactionRuleCommand:
    return CreateTransactionRuleCommand(
        name=name,
        pattern=pattern,
        match_type=match_type,
        category_id=parse_optional_uuid(category_id),
        property_id=parse_optional_uuid(property_id),
        target_operation_type=parse_optional_operation_type(target_operation_type),
        direction=direction,
        application_mode=application_mode,
        amount_min=amount_min,
        amount_max=amount_max,
    )


def build_update_rule_command(
    *,
    rule_id: UUID,
    name: str | None,
    pattern: str,
    match_type: TransactionRuleMatchType,
    category_id: str | None,
    property_id: str | None,
    target_operation_type: str | None,
    direction: MoneyDirection,
    application_mode: TransactionRuleApplicationMode,
    amount_min: Decimal | None,
    amount_max: Decimal | None,
) -> UpdateTransactionRuleCommand:
    return UpdateTransactionRuleCommand(
        rule_id=rule_id,
        name=name,
        pattern=pattern,
        match_type=match_type,
        category_id=parse_optional_uuid(category_id),
        property_id=parse_optional_uuid(property_id),
        target_operation_type=parse_optional_operation_type(target_operation_type),
        direction=direction,
        application_mode=application_mode,
        amount_min=amount_min,
        amount_max=amount_max,
    )


def parse_optional_uuid(raw_value: str | None) -> UUID | None:
    if not raw_value:
        return None
    return UUID(raw_value)


def parse_optional_operation_type(raw_value: str | None) -> OperationType | None:
    if not raw_value:
        return None
    return OperationType(raw_value)
