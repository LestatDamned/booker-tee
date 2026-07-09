from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.features.ledger.models import OperationType
from app.features.transaction_rules.models import (
    MoneyDirection,
    TransactionRuleApplicationMode,
    TransactionRuleMatchType,
)
from app.shared.ui.actions import ActionVM


@dataclass(frozen=True)
class RuleMetaVM:
    label: str
    tone: str | None = None


@dataclass(frozen=True)
class RuleRowVM:
    id: UUID
    anchor_id: str
    form_id: str
    form_action: str
    title: str
    pattern: str
    status_label: str
    status_tone: str
    is_inactive: bool
    match_type: TransactionRuleMatchType
    application_mode: TransactionRuleApplicationMode
    direction: MoneyDirection
    target_operation_type: OperationType | None
    category_id: UUID | None
    property_id: UUID | None
    amount_min: Decimal | None
    amount_max: Decimal | None
    meta: list[RuleMetaVM]
    technical_label: str
    save_action: ActionVM
    toggle_action: ActionVM
    delete_action: ActionVM


@dataclass(frozen=True)
class RulesPageVM:
    rules: list[RuleRowVM]
    can_write: bool
    total_rule_count: int
    active_rule_count: int
    inactive_rule_count: int
