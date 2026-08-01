from dataclasses import dataclass
from decimal import Decimal

from app.shared.ui.actions import ActionVM


@dataclass(frozen=True)
class RuleFormOptionVM:
    value: str
    label: str
    selected: bool = False


@dataclass(frozen=True)
class RuleListFilterVM:
    action: str
    search: str
    category_options: list[RuleFormOptionVM]
    status_options: list[RuleFormOptionVM]
    is_active: bool
    result_label: str | None
    reset_url: str


@dataclass(frozen=True)
class RuleListPaginationVM:
    visible_count: int
    filtered_count: int
    has_more: bool
    next_url: str | None
    label: str


@dataclass(frozen=True)
class RuleFormVM:
    id: str
    action: str
    layout: str
    pattern: str
    show_name: bool
    name: str
    advanced_label: str
    operation_type_options: list[RuleFormOptionVM]
    category_options: list[RuleFormOptionVM]
    property_options: list[RuleFormOptionVM]
    match_type_options: list[RuleFormOptionVM]
    application_mode_options: list[RuleFormOptionVM]
    direction_options: list[RuleFormOptionVM]
    amount_min: Decimal | None
    amount_max: Decimal | None
    expected_updated_at: str | None
    submit_action: ActionVM


@dataclass(frozen=True)
class RuleRowVM:
    anchor_id: str
    title: str
    condition_label: str
    secondary_label: str
    status_label: str
    status_tone: str
    is_inactive: bool
    is_recent: bool
    edit_summary_id: str
    edit_panel_id: str
    edit_form_url: str
    edit_toggle_action: ActionVM
    toggle_action: ActionVM
    delete_action: ActionVM


@dataclass(frozen=True)
class RulesPageVM:
    rules: list[RuleRowVM]
    create_form: RuleFormVM
    seed_defaults_action: ActionVM
    create_rule_label: str
    rule_count_label: str
    filters: RuleListFilterVM
    pagination: RuleListPaginationVM
    recent_rule: RuleRowVM | None
    can_write: bool
    total_rule_count: int
    active_rule_count: int
    inactive_rule_count: int
