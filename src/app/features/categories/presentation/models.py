from dataclasses import dataclass
from uuid import UUID

from app.features.categories.models import CategoryKind
from app.features.categories.service import CategoryDetailView, CategoryManagementRow


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
class CategoryIndexPageVM:
    view: str
    view_options: list[CategoryViewOptionVM]
    user_category_rows: list[CategoryManagementRow]
    system_category_rows: list[CategoryManagementRow]
    recent_category: CategoryManagementRow | None
    recent_category_id: UUID | None
    kinds: list[CategoryKind]
    create_form: CategoryFormStateVM


@dataclass(frozen=True)
class CategoryDetailPageVM:
    detail: CategoryDetailView
    kinds: list[CategoryKind]
    edit_form: CategoryFormStateVM
    lifecycle: CategoryLifecycleStateVM
    edit_panel_open: bool
