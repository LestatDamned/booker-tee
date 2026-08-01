from datetime import date
from urllib.parse import urlencode
from uuid import UUID

from app.features.categories.models import Category, CategoryKind
from app.features.categories.presentation.models import (
    CategoryDetailHeaderVM,
    CategoryDetailPageVM,
    CategoryFormStateVM,
    CategoryIndexPageVM,
    CategoryLifecycleStateVM,
    CategoryRowVM,
    CategoryViewOptionVM,
)
from app.features.categories.service import (
    CategoryDetailView,
    CategoryError,
    CategoryManagementRow,
)
from app.features.ledger.domain.types import OperationType
from app.shared.ui.actions import ActionVM
from app.templating import ru_label

CATEGORY_VIEW_OPTIONS = [
    ("active", "активные"),
    ("archived", "архив"),
    ("system", "системные"),
    ("all", "все"),
]
CATEGORY_VIEW_VALUES = {value for value, _label in CATEGORY_VIEW_OPTIONS}


class CategoryPagePresenter:
    @staticmethod
    def build_index(
        category_rows: list[CategoryManagementRow],
        *,
        category_view: str,
        create_form: CategoryFormStateVM | None = None,
        recent_category_id: UUID | None = None,
    ) -> CategoryIndexPageVM:
        normalized_view = normalize_category_view(category_view)
        user_category_rows, system_category_rows = split_category_rows(
            category_rows,
            normalized_view,
        )
        visible_source_rows = [*user_category_rows, *system_category_rows]
        resolved_create_form = create_form or default_category_form_state()
        user_row_vms = [
            category_row_vm(
                row,
                is_recent=row.category.id == recent_category_id,
            )
            for row in user_category_rows
        ]
        system_row_vms = [
            category_row_vm(
                row,
                is_recent=row.category.id == recent_category_id,
            )
            for row in system_category_rows
        ]
        visible_row_vms = [*user_row_vms, *system_row_vms]
        recent_category = next((row for row in visible_row_vms if row.is_recent), None)
        has_visible_rows = bool(visible_source_rows)
        return CategoryIndexPageVM(
            view=normalized_view,
            view_options=category_view_options(normalized_view),
            user_category_rows=user_row_vms,
            system_category_rows=system_row_vms,
            recent_category=recent_category,
            recent_category_id=recent_category_id if recent_category is not None else None,
            kinds=list(CategoryKind),
            create_form=resolved_create_form,
            create_form_id="category-create-form",
            create_label="создать категорию",
            create_panel_open=bool(resolved_create_form.error or not has_visible_rows),
            create_submit_action=ActionVM(
                id="create-category",
                label="создать категорию",
                icon="plus",
                placement="primary",
                action_type="submit",
                form_id="category-create-form",
            ),
        )

    @staticmethod
    def build_detail(
        detail: CategoryDetailView,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        currency: str | None = None,
        operation_type: OperationType | None = None,
        return_to: str | None = None,
        edit_form: CategoryFormStateVM | None = None,
        lifecycle_error: str | None = None,
    ) -> CategoryDetailPageVM:
        resolved_edit_form = edit_form or CategoryFormStateVM(
            error=None,
            name=detail.category.name,
            kind=detail.category.kind,
            notes=detail.category.notes or "",
        )
        category = detail.category
        form_id = f"category-form-{category.id}"
        edit_summary_id = f"category-edit-toggle-{category.id}"
        is_editable = not category.is_system
        can_delete = (
            is_editable and not category.is_active and not detail.operations and not detail.rules
        )
        return CategoryDetailPageVM(
            detail=detail,
            header=category_detail_header_vm(detail),
            period_label=category_detail_period_label(date_from=date_from, date_to=date_to),
            has_period_filter=date_from is not None or date_to is not None,
            reset_period_url=category_detail_url(
                category.id,
                currency=currency,
                operation_type=operation_type,
                return_to=return_to,
            ),
            back_url=return_to or "/categories",
            back_label="вернуться в отчёт" if return_to else "категории",
            currency=currency,
            flow_label=category_detail_flow_label(operation_type),
            kinds=list(CategoryKind),
            edit_form=resolved_edit_form,
            edit_form_id=form_id,
            edit_summary_id=edit_summary_id,
            lifecycle=CategoryLifecycleStateVM(error=lifecycle_error),
            edit_panel_open=bool(resolved_edit_form.error or lifecycle_error),
            edit_toggle_action=ActionVM(
                id="edit-category",
                label="изменить категорию",
                icon="settings",
                placement="primary",
                action_type="panel_toggle",
                panel_id=edit_summary_id,
            )
            if is_editable
            else None,
            lifecycle_action=category_lifecycle_action(category) if is_editable else None,
            delete_action=ActionVM(
                id="delete-category",
                label="удалить",
                icon="trash",
                placement="danger",
                action_type="post",
                url=f"/categories/{category.id}/delete",
                style="danger",
                hidden_fields={"view": "archived"},
                confirm_message="Удалить архивную категорию безвозвратно?",
            )
            if can_delete
            else None,
            save_action=ActionVM(
                id="save-category",
                label="сохранить",
                icon="save",
                placement="primary",
                action_type="submit",
                form_id=form_id,
            ),
        )


def default_category_form_state() -> CategoryFormStateVM:
    return CategoryFormStateVM(
        error=None,
        name="",
        kind=CategoryKind.MIXED,
        notes="",
    )


def category_form_state(
    *,
    error: str | None,
    name: str,
    kind: CategoryKind,
    notes: str | None,
) -> CategoryFormStateVM:
    return CategoryFormStateVM(
        error=error,
        name=name,
        kind=kind,
        notes=notes or "",
    )


def normalize_category_view(raw_view: str | None) -> str:
    if raw_view in CATEGORY_VIEW_VALUES:
        return raw_view
    return "active"


def categories_url(raw_view: str | None) -> str:
    category_view = normalize_category_view(raw_view)
    if category_view == "active":
        return "/categories"
    return f"/categories?view={category_view}"


def category_recent_url(category_id: UUID, raw_view: str | None) -> str:
    category_view = visible_category_view_after_create(raw_view)
    anchor_id = category_anchor_id(category_id)
    if category_view == "active":
        return f"/categories?recent_category_id={category_id}#{anchor_id}"
    return f"/categories?view={category_view}&recent_category_id={category_id}#{anchor_id}"


def category_anchor_id(category_id: UUID) -> str:
    return f"category-{category_id}"


def category_detail_url(
    category_id: UUID,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    currency: str | None = None,
    operation_type: OperationType | None = None,
    return_to: str | None = None,
) -> str:
    params = {
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "currency": currency,
        "type": operation_type.value if operation_type else None,
        "return_to": return_to,
    }
    query = urlencode({key: value for key, value in params.items() if value not in {None, ""}})
    return f"/categories/{category_id}?{query}" if query else f"/categories/{category_id}"


def category_detail_flow_label(operation_type: OperationType | None) -> str:
    if operation_type == OperationType.INCOME:
        return "только доходы"
    if operation_type == OperationType.EXPENSE:
        return "только расходы"
    return "все операции"


def category_detail_period_label(
    *,
    date_from: date | None,
    date_to: date | None,
) -> str:
    if date_from and date_to:
        return f"{format_category_date(date_from)} — {format_category_date(date_to)}"
    if date_from:
        return f"с {format_category_date(date_from)}"
    if date_to:
        return f"по {format_category_date(date_to)}"
    return "все время"


def format_category_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def category_row_vm(
    row: CategoryManagementRow,
    *,
    is_recent: bool = False,
) -> CategoryRowVM:
    category = row.category
    is_inactive = not category.is_active
    status_label = None
    status_tone = None
    if category.is_system:
        status_label = "системная"
        status_tone = "muted"
    if is_inactive:
        status_label = "архив"
        status_tone = "archived"
    return CategoryRowVM(
        category=category,
        anchor_id=category_anchor_id(category.id),
        title=category.name,
        kind_label=ru_label(category.kind),
        kind_tone=category.kind.value,
        status_label=status_label,
        status_tone=status_tone,
        is_inactive=is_inactive,
        is_system=category.is_system,
        is_recent=is_recent,
        operation_count_label=f"{row.operation_count} операций",
        rule_count_label=f"{row.rule_count} правил",
        system_key_label=category.system_key,
        notes_label=category.notes,
        detail_action=ActionVM(
            id="open-category",
            label="открыть категорию",
            icon="tag",
            placement="primary",
            action_type="link",
            url=f"/categories/{category.id}",
        ),
    )


def category_detail_header_vm(detail: CategoryDetailView) -> CategoryDetailHeaderVM:
    category = detail.category
    is_inactive = not category.is_active
    status_label = None
    status_tone = None
    if category.is_system:
        status_label = "системная"
        status_tone = "muted"
    if is_inactive:
        status_label = "архив"
        status_tone = "archived"
    return CategoryDetailHeaderVM(
        category=category,
        anchor_id=category_anchor_id(category.id),
        title=category.name,
        kind_label=ru_label(category.kind),
        kind_tone=category.kind.value,
        status_label=status_label,
        status_tone=status_tone,
        is_inactive=is_inactive,
        is_system=category.is_system,
        operation_count_label=f"{len(detail.operations)} операций",
        rule_count_label=f"{len(detail.rules)} правил",
        notes_label=category.notes,
    )


def category_lifecycle_action(category: Category) -> ActionVM:
    is_active = category.is_active
    return ActionVM(
        id="archive-category" if is_active else "restore-category",
        label="в архив" if is_active else "восстановить",
        icon="archive" if is_active else "rotate-ccw",
        placement="secondary",
        action_type="post",
        url=f"/categories/{category.id}/archive"
        if is_active
        else f"/categories/{category.id}/restore",
    )


def visible_category_view_after_create(raw_view: str | None) -> str:
    category_view = normalize_category_view(raw_view)
    if category_view in {"active", "all"}:
        return category_view
    return "active"


def category_view_options(category_view: str) -> list[CategoryViewOptionVM]:
    return [
        CategoryViewOptionVM(
            value=value,
            label=label,
            url=categories_url(value),
            is_active=category_view == value,
        )
        for value, label in CATEGORY_VIEW_OPTIONS
    ]


def category_form_error_message(error: CategoryError) -> str:
    message = str(error)
    if message == "Category name is required.":
        return "Введите название категории."
    return message


def split_category_rows(
    category_rows: list[CategoryManagementRow],
    category_view: str,
) -> tuple[list[CategoryManagementRow], list[CategoryManagementRow]]:
    if category_view == "active":
        return (
            [row for row in category_rows if not row.category.is_system and row.category.is_active],
            [],
        )
    if category_view == "archived":
        return (
            [
                row
                for row in category_rows
                if not row.category.is_system and not row.category.is_active
            ],
            [],
        )
    if category_view == "system":
        return ([], [row for row in category_rows if row.category.is_system])
    return (
        [row for row in category_rows if not row.category.is_system],
        [row for row in category_rows if row.category.is_system],
    )
