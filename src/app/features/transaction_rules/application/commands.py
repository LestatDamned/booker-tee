from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.features.ledger.models import OperationType
from app.features.transaction_rules.models import (
    MoneyDirection,
    TransactionRuleApplicationMode,
    TransactionRuleMatchType,
)


@dataclass(frozen=True)
class CreateTransactionRuleCommand:
    name: str | None
    pattern: str
    match_type: TransactionRuleMatchType
    category_id: UUID | None
    property_id: UUID | None
    target_operation_type: OperationType | None
    direction: MoneyDirection
    account_id: UUID | None = None
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    auto_description: str | None = None
    affects_profit: bool | None = True
    application_mode: TransactionRuleApplicationMode = TransactionRuleApplicationMode.SUGGEST


@dataclass(frozen=True)
class UpdateTransactionRuleCommand:
    rule_id: UUID
    name: str | None
    pattern: str
    match_type: TransactionRuleMatchType
    category_id: UUID | None
    property_id: UUID | None
    target_operation_type: OperationType | None
    direction: MoneyDirection
    application_mode: TransactionRuleApplicationMode
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
