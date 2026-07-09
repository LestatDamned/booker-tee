from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from app.features.ledger.models import OperationType
from app.shared.ui.actions import ActionVM


@dataclass(frozen=True)
class BadgeVM:
    label: str
    tone: str


@dataclass(frozen=True)
class ProblemVM:
    message: str
    tone: str = "warning"


@dataclass(frozen=True)
class ActionSetVM:
    primary: ActionVM | None
    visible_secondary: ActionVM | None
    menu: Sequence[ActionVM]
    danger: Sequence[ActionVM]


@dataclass(frozen=True)
class CategoryOptionVM:
    id: UUID
    label: str
    selected: bool


@dataclass(frozen=True)
class PropertyOptionVM:
    id: UUID
    label: str
    selected: bool


@dataclass(frozen=True)
class CategoryKindOptionVM:
    value: str
    label: str
    selected: bool


@dataclass(frozen=True)
class TransferAccountOptionVM:
    id: UUID
    label: str


@dataclass(frozen=True)
class TransferMatchOptionVM:
    value: str
    label: str
    account_id: UUID | None


@dataclass(frozen=True)
class TransferPreviewVM:
    title: str
    route_label: str
    source_account_label: str
    destination_account_label: str


@dataclass(frozen=True)
class CategoryPanelPayload:
    action_url: str
    create_category_url: str
    selected_category_id: UUID | None
    category_options: Sequence[CategoryOptionVM]
    property_options: Sequence[PropertyOptionVM]
    category_kind_options: Sequence[CategoryKindOptionVM]
    selected_property_id: UUID | None
    open_category_editor: bool
    create_category_error: str | None
    create_category_initial_name: str


@dataclass(frozen=True)
class TransferPanelPayload:
    action_url: str
    transfer_preview: TransferPreviewVM
    account_options: Sequence[TransferAccountOptionVM]
    match_options: Sequence[TransferMatchOptionVM]
    empty_match_message: str | None
    manual_operation_note: str | None


@dataclass(frozen=True)
class ReviewPanelVM:
    id: str
    title: str
    summary_note: str
    role: str
    panel_type: str
    template_name: str
    load_url: str
    is_open: bool
    payload: CategoryPanelPayload | TransferPanelPayload | None


@dataclass(frozen=True)
class ReviewQueueVM:
    total: int
    remaining: int
    done: int
    first_remaining_id: UUID | None
    progress_percent: float
    title: str
    message: str
    document_filename: str
    primary_action: ActionVM
    secondary_url: str | None
    secondary_label: str | None
    workflow_upload: str
    workflow_extract: str
    workflow_mapping: str
    workflow_review: str
    workflow_ledger: str


@dataclass(frozen=True)
class ReviewPageHeaderVM:
    title: str
    status_label: str
    document_filename: str
    document_id_label: str
    actions_label: str
    technical_title: str
    apply_rules_action: ActionVM
    back_action: ActionVM
    open_document_action: ActionVM


@dataclass(frozen=True)
class ReviewWorkflowStepVM:
    index: int
    label: str
    state: str


@dataclass(frozen=True)
class ReviewWorkflowVM:
    title: str
    steps: Sequence[ReviewWorkflowStepVM]


@dataclass(frozen=True)
class ReviewRuleHintVM:
    title: str
    icon: str
    message: str
    open_rules_action: ActionVM
    apply_rules_action: ActionVM


@dataclass(frozen=True)
class ReviewPageToolsVM:
    rule_hint: ReviewRuleHintVM
    workflow: ReviewWorkflowVM


@dataclass(frozen=True)
class ReviewEmptyStateVM:
    title: str
    message: str
    primary_url: str
    primary_label: str
    primary_icon: str
    secondary_url: str
    secondary_label: str
    secondary_icon: str


@dataclass(frozen=True)
class ReviewPageVM:
    title: str
    header: ReviewPageHeaderVM
    queue: ReviewQueueVM
    tools: ReviewPageToolsVM
    validation: ReviewValidationSummaryVM | None
    empty_state: ReviewEmptyStateVM
    has_review_items: bool


@dataclass(frozen=True)
class ReviewValidationMetricVM:
    label: str
    value: object


@dataclass(frozen=True)
class ReviewControlTotalCellVM:
    label: str
    value: object
    tone: str | None = None


@dataclass(frozen=True)
class ReviewControlTotalRowVM:
    kind: str
    cells: Sequence[ReviewControlTotalCellVM]


@dataclass(frozen=True)
class ReviewValidationSummaryVM:
    status_label: str
    message: str
    metrics: Sequence[ReviewValidationMetricVM]
    extracted_count: object
    needs_review_count: object
    currency: object
    calculated_total_inflow: object
    calculated_total_outflow: object
    ignored_total_inflow: object
    ignored_total_outflow: object
    statement_total_inflow: object
    statement_total_outflow: object
    inflow_difference: object
    outflow_difference: object
    unexplained_inflow_difference: object
    unexplained_outflow_difference: object
    control_total_rows: Sequence[ReviewControlTotalRowVM]
    warning_message: str | None


@dataclass(frozen=True)
class OperationLinkVM:
    title: str
    detail: str
    operation_id: UUID
    type_value: str | None
    type_label: str | None
    tone: str = "confirmed"


@dataclass(frozen=True)
class ReviewOutcomeVM:
    title: str
    detail: str
    type_value: str | None
    type_label: str | None
    tone: str


@dataclass(frozen=True)
class ClassificationVM:
    operation_type: OperationType | None
    source: str


@dataclass(frozen=True)
class ReviewItemVM:
    id: UUID
    anchor_id: str
    row_index: int
    visual_state: str
    is_confirmable: bool
    is_next: bool
    status_label: str
    description: str
    date_label: object
    amount_label: object
    currency: str
    money_tone: str
    operation_type: str | None
    operation_type_label: str
    operation_type_source: str
    operation_type_source_label: str
    state_badge: BadgeVM | None
    classification_badge: BadgeVM | None
    classification_source_badge: BadgeVM | None
    account_label: str
    problems: Sequence[ProblemVM]
    primary_action: ActionVM | None
    visible_secondary_action: ActionVM | None
    menu_actions: Sequence[ActionVM]
    danger_actions: Sequence[ActionVM]
    initial_active_panel_id: str
    panels: Sequence[ReviewPanelVM]
    proposal_summary: str | None
    outcome_summary: ReviewOutcomeVM | None
    operation_link: OperationLinkVM | None
    oob: bool = False
