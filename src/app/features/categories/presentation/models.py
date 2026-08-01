from dataclasses import dataclass
from uuid import UUID

from app.features.categories.models import Category, CategoryKind
from app.features.categories.service import CategoryDetailView
from app.shared.ui.actions import ActionVM


@dataclass(frozen=True)
class CategoryViewOptionVM:
    value: str
    label: str
    url: str
    is_active: bool


@dataclass(frozen=True)
class CategoryFormStateVM:
    error: str | None
    name: str
    kind: CategoryKind
    notes: str


@dataclass(frozen=True)
class CategoryLifecycleStateVM:
    error: str | None


@dataclass(frozen=True)
class CategoryRowVM:
    category: Category
    anchor_id: str
    title: str
    kind_label: str
    kind_tone: str
    status_label: str | None
    status_tone: str | None
    is_inactive: bool
    is_system: bool
    is_recent: bool
    operation_count_label: str
    rule_count_label: str
    system_key_label: str | None
    notes_label: str | None
    detail_action: ActionVM


@dataclass(frozen=True)
class CategoryDetailHeaderVM:
    category: Category
    anchor_id: str
    title: str
    kind_label: str
    kind_tone: str
    status_label: str | None
    status_tone: str | None
    is_inactive: bool
    is_system: bool
    operation_count_label: str
    rule_count_label: str
    notes_label: str | None


@dataclass(frozen=True)
class CategoryIndexPageVM:
    view: str
    view_options: list[CategoryViewOptionVM]
    user_category_rows: list[CategoryRowVM]
    system_category_rows: list[CategoryRowVM]
    recent_category: CategoryRowVM | None
    recent_category_id: UUID | None
    kinds: list[CategoryKind]
    create_form: CategoryFormStateVM
    create_form_id: str
    create_label: str
    create_panel_open: bool
    create_submit_action: ActionVM


@dataclass(frozen=True)
class CategoryDetailPageVM:
    detail: CategoryDetailView
    header: CategoryDetailHeaderVM
    period_label: str
    has_period_filter: bool
    reset_period_url: str
    back_url: str
    back_label: str
    currency: str | None
    flow_label: str
    kinds: list[CategoryKind]
    edit_form: CategoryFormStateVM
    edit_form_id: str
    edit_summary_id: str
    lifecycle: CategoryLifecycleStateVM
    edit_panel_open: bool
    edit_toggle_action: ActionVM | None
    lifecycle_action: ActionVM | None
    delete_action: ActionVM | None
    save_action: ActionVM
