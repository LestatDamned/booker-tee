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
class RuleFormOptionVM:
    value: str
    label: str
    selected: bool = False


@dataclass(frozen=True)
class RuleFormVM:
    id: str
    action: str
    pattern: str
    show_name: bool
    name: str
    operation_type_options: list[RuleFormOptionVM]
    category_options: list[RuleFormOptionVM]
    property_options: list[RuleFormOptionVM]
    match_type_options: list[RuleFormOptionVM]
    application_mode_options: list[RuleFormOptionVM]
    direction_options: list[RuleFormOptionVM]
    amount_min: Decimal | None
    amount_max: Decimal | None
    submit_action: ActionVM


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
    form: RuleFormVM
    technical_label: str
    toggle_action: ActionVM
    delete_action: ActionVM


@dataclass(frozen=True)
class RulesPageVM:
    rules: list[RuleRowVM]
    create_form: RuleFormVM
    can_write: bool
    total_rule_count: int
    active_rule_count: int
    inactive_rule_count: int
