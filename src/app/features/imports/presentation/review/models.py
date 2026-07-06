from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from app.features.ledger.models import OperationType


@dataclass(frozen=True)
class BadgeVM:
    label: str
    tone: str


@dataclass(frozen=True)
class ProblemVM:
    message: str
    tone: str = "warning"


@dataclass(frozen=True)
class ActionVM:
    id: str
    label: str
    icon: str
    placement: str
    action_type: str
    url: str | None = None
    hidden_fields: Mapping[str, str] | None = None
    panel_id: str | None = None
    style: str = "default"
    confirm_message: str | None = None


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
class CategoryPanelPayload:
    action_url: str
    selected_category_id: UUID | None
    category_options: Sequence[CategoryOptionVM]
    property_options: Sequence[PropertyOptionVM]
    category_kind_options: Sequence[CategoryKindOptionVM]
    selected_property_id: UUID | None
    open_category_editor: bool
    category_dialog_error: str | None
    category_dialog_name: str


@dataclass(frozen=True)
class TransferPanelPayload:
    action_url: str
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
    is_open: bool
    payload: CategoryPanelPayload | TransferPanelPayload


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
class ReviewValidationSummaryVM:
    status_label: str
    message: str
    extracted_count: object
    needs_review_count: object
    currency: object
    calculated_total_inflow: object
    calculated_total_outflow: object
    statement_total_inflow: object
    statement_total_outflow: object
    inflow_difference: object
    outflow_difference: object
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
    row: object
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
